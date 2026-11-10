#!/usr/bin/env python3
"""Build the public playlist from the channel tables in README.md and iptv-org."""
from __future__ import annotations

import json
import concurrent.futures
import os
import re
import socket
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PLAYLIST = ROOT / "docs/playlist.m3u"
STATUS = ROOT / "docs/status.json"
ERRORS = ROOT / "errors.md"
BASE = "https://iptv-org.github.io/api"
PROBE_TIMEOUT = 8
PROBE_WORKERS = 12
MAX_PLAYLIST_BYTES = 256 * 1024
MAX_SEGMENT_BYTES = 1024


@dataclass
class Target:
    name: str
    tvg_id: str
    group: str
    preference: str = ""
    priority: str = "B"
    candidate_ids: list[str] = field(default_factory=list)
    strict_candidates: bool = False


def markdown_cells(line: str) -> list[str]:
    return [x.strip() for x in line.strip().strip("|").split("|")]


def parse_m3u(text: str) -> list[dict]:
    """Parse generated M3U entries and reject incomplete records."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != "#EXTM3U":
        raise ValueError("M3U must start with #EXTM3U")
    entries = []
    i = 1
    while i < len(lines):
        line = lines[i]
        if not line.startswith("#EXTINF:"):
            raise ValueError(f"Unexpected M3U line: {line}")
        if i + 1 >= len(lines) or lines[i + 1].startswith("#"):
            raise ValueError("M3U entry has no stream URL")
        url = lines[i + 1]
        if not url.startswith(("http://", "https://")):
            raise ValueError("M3U stream URL must use HTTP(S)")
        entries.append({"extinf": line, "url": url})
        i += 2
    return entries


def parse_readme(text: str) -> list[Target]:
    """Read the three canonical channel tables; preserve their order and feed alternatives."""
    section = ""
    targets: list[Target] = []
    for line in text.splitlines():
        if line.startswith("## 1."):
            section = "A"
        elif line.startswith("## 2."):
            section = "B"
        elif line.startswith("## 3."):
            section = "C"
        elif line.startswith("## "):
            section = ""
        elif section in {"A", "B", "C"} and line.startswith("|"):
            cells = markdown_cells(line)
            if not cells or not cells[0].isdigit():
                continue
            if section == "A":
                num, name, pref, candidate, _note = cells
                ids = re.findall(r"`([^`]+)`", candidate)
                targets.append(Target(name, ids[0] if ids else "", "Избранное", pref, "A", ids, False))
            elif section == "B":
                _num, name, ident, group = cells
                ids = re.findall(r"`([^`]+)`", ident)
                targets.append(Target(name, ids[0] if ids else "", group, "", "B", ids, True))
            else:
                _num, name, candidates, language, _priority, _reason = cells
                ids = re.findall(r"`([^`]+)`", candidates)
                group = "Детские RU" if language == "RU" else "Kids EN"
                targets.append(Target(name, ids[0] if ids else "", group,
                                      f"{language} / HD preferred", "C", ids, True))
    if not targets:
        raise ValueError("No channel tables found in README.md")
    return targets


def fetch_json(path: str) -> list[dict]:
    req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": "my-iptv-playlist-updater/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        payload = json.load(response)
    if not isinstance(payload, list) or not payload or not all(isinstance(x, dict) for x in payload):
        raise ValueError(f"Invalid iptv-org response: {path}")
    return payload


def candidate_score(target: Target, channel: dict, feed: dict, stream: dict) -> int:
    cid = str(channel.get("id", ""))
    sid = str(stream.get("channel", ""))
    if not cid or sid != cid:
        return -1
    feed_id = str(feed.get("id", stream.get("feed", "")))
    full_id = f"{cid}@{feed_id}" if feed_id else cid
    ident = target.tvg_id
    score = 0
    if target.candidate_ids:
        if full_id in target.candidate_ids:
            score += 100 - target.candidate_ids.index(full_id) * 20
        elif target.strict_candidates or cid not in {value.split("@", 1)[0] for value in target.candidate_ids}:
            return -1
        else:
            # A-table IDs are examples; same-channel feeds may improve requested quality.
            score += 80
    else:
        # Channels without a snapshot tvg-id (notably CNN) match exact names only.
        names = {str(channel.get("name", "")).casefold()}
        names.update(str(value).casefold() for value in channel.get("alt_names", []))
        aliases = {"cnn international": {"cnn international", "cnn international europe"}}
        wanted = target.name.casefold().strip()
        wanted_names = aliases.get(wanted, {wanted})
        if not names.intersection(wanted_names):
            return -1
        score += 10
    languages = feed.get("languages", channel.get("languages", []))
    if "RU" in target.preference.upper() or target.group.endswith(" RU"):
        if "rus" not in languages:
            return -1
        score += 40
    elif "EN" in target.preference.upper() or target.group.endswith(" EN"):
        if "eng" not in languages:
            return -1
        score += 20
    if target.priority == "A" and "CEE" in target.name.upper():
        # Do not allow Polish feeds as a substitute for CEE, even if similarly named.
        if not re.search(r"(?:@|\.)CEE(?:$|\.)", full_id, re.I) and "CEE" not in str(stream.get("url", "")).upper():
            return -1
        if ".pl@" in cid.lower() or "polsat" in cid.lower():
            return -1
        score += 500
    quality = str(stream.get("quality") or feed.get("format", "")).upper()
    if "HD" in target.preference.upper():
        numbers = [int(value) for value in re.findall(r"\d+", quality)]
        score += 60 if "HD" in quality or any(value >= 720 for value in numbers) else 0
    return score


class ProbeError(Exception):
    def __init__(self, stage: str, reason: str, http_status: int | None = None):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason
        self.http_status = http_status


def fetch_probe_bytes(url: str, stage: str, limit: int) -> tuple[bytes, str, int]:
    """Fetch a small prefix without cookies, auth, referrer, or stream-specific headers."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "my-iptv-availability-check/1.0",
            "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as response:
            code = int(response.getcode() or 0)
            final_url = response.geturl()
            payload = response.read(limit)
    except urllib.error.HTTPError as exc:
        raise ProbeError(stage, str(exc.reason or "HTTP request rejected"), exc.code) from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            label = "request timed out"
        else:
            label = str(reason or "network request failed")
        raise ProbeError(stage, label) from exc
    except (socket.timeout, TimeoutError) as exc:
        raise ProbeError(stage, "request timed out") from exc
    except OSError as exc:
        raise ProbeError(stage, str(exc) or "network request failed") from exc
    if code < 200 or code >= 300:
        raise ProbeError(stage, f"unexpected HTTP {code}", code)
    if not payload:
        raise ProbeError(stage, "empty response", code)
    return payload, final_url, code


def looks_like_transport_stream(payload: bytes) -> bool:
    return len(payload) >= 188 * 3 and all(payload[offset] == 0x47 for offset in (0, 188, 376))


def _playlist_text(payload: bytes, stage: str, http_status: int | None = None) -> str:
    text = payload.decode("utf-8-sig", errors="replace").lstrip()
    if not text.startswith("#EXTM3U"):
        raise ProbeError(stage, "response is not an HLS playlist", http_status)
    return text


def _master_variant(text: str, base_url: str) -> str | None:
    lines = [line.strip() for line in text.splitlines()]
    variants = []
    for index, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue
        attrs = line.partition(":")[2]
        bandwidth_match = re.search(r"(?:^|,)BANDWIDTH=(\d+)", attrs)
        bandwidth = int(bandwidth_match.group(1)) if bandwidth_match else 0
        for candidate in lines[index + 1:]:
            if candidate and not candidate.startswith("#"):
                variants.append((bandwidth, urljoin(base_url, candidate)))
                break
    return max(variants, default=(0, None))[1]


def _media_resources(text: str, base_url: str) -> tuple[list[str], list[str]]:
    segments, keys = [], []
    for line in (line.strip() for line in text.splitlines()):
        if line.startswith("#EXT-X-KEY:"):
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                keys.append(urljoin(base_url, match.group(1)))
        elif line and not line.startswith("#"):
            segments.append(urljoin(base_url, line))
    selected_segments = segments[:2] if "#EXT-X-ENDLIST" in text else segments[-2:]
    selected_keys = keys[:1] if "#EXT-X-ENDLIST" in text else keys[-1:]
    return selected_segments, selected_keys


def _session_keys(text: str, base_url: str) -> list[str]:
    keys = []
    for line in text.splitlines():
        if line.startswith("#EXT-X-SESSION-KEY:"):
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                keys.append(urljoin(base_url, match.group(1)))
    return keys[:1]


def check_stream_access(url: str) -> dict:
    """Probe an HLS URL through its media playlist and two representative segments."""
    if url.lower().split("?", 1)[0].endswith(".mpd"):
        return {"state": "not_hls", "stage": "format", "reason": "DASH .mpd is not an HLS playlist"}
    try:
        first_limit = MAX_PLAYLIST_BYTES if urlsplit(url).path.lower().endswith(".m3u8") else MAX_SEGMENT_BYTES
        body, final_url, code = fetch_probe_bytes(url, "playlist", first_limit)
        if not body.lstrip().startswith(b"#EXTM3U"):
            if looks_like_transport_stream(body):
                return {"state": "accessible_non_hls", "stage": "direct stream",
                        "http_status": code, "reason": "accessible direct MPEG-TS stream; no HLS chain"}
            content = body.lstrip().lower()
            if content.startswith((b"<!doctype html", b"<html", b"{", b"<form")):
                raise ProbeError("playlist", "server returned an HTML/JSON page instead of video", code)
        text = _playlist_text(body, "playlist", code)
        keys = _session_keys(text, final_url)
        variant_url = _master_variant(text, final_url)
        if variant_url:
            body, final_url, code = fetch_probe_bytes(variant_url, "media playlist", MAX_PLAYLIST_BYTES)
            text = _playlist_text(body, "media playlist", code)
        segments, media_keys = _media_resources(text, final_url)
        keys.extend(key for key in media_keys if key not in keys)
        if not segments:
            raise ProbeError("media playlist", "playlist contains no media segments", code)
        for key_url in keys:
            key_body, _, key_code = fetch_probe_bytes(key_url, "encryption key", 64)
            if len(key_body) < 16:
                raise ProbeError("encryption key", "key response is shorter than 16 bytes", key_code)
        for segment_url in segments:
            segment_body, _, segment_code = fetch_probe_bytes(segment_url, "media segment", MAX_SEGMENT_BYTES)
            prefix = segment_body.lstrip().lower()
            if prefix.startswith((b"<!doctype html", b"<html", b"{", b"<form")):
                raise ProbeError("media segment", "server returned an error page instead of a segment", segment_code)
        return {"state": "accessible", "stage": "complete", "http_status": code,
                "reason": f"HLS playlist, {len(segments)} segment(s)"}
    except ProbeError as exc:
        failure = {"state": "restricted_or_unavailable", "stage": exc.stage, "reason": exc.reason}
        if exc.http_status is not None:
            failure["http_status"] = exc.http_status
        return failure
    except Exception as exc:
        return {"state": "check_error", "stage": "probe", "reason": str(exc) or type(exc).__name__}


def validate_found_streams(found: list[dict]) -> list[dict]:
    """Check each distinct selected URL once and copy its result to matching targets."""
    urls = list(dict.fromkeys(item["url"] for item in found))
    with concurrent.futures.ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
        checks = dict(zip(urls, pool.map(check_stream_access, urls)))
    for item in found:
        item["access_check"] = checks[item["url"]]
    failures = []
    for item in found:
        result = item["access_check"]
        if result["state"] not in {"accessible", "accessible_non_hls"}:
            failures.append({"name": item["name"], "tvg_id": item["tvg_id"],
                             "stage": result["stage"], "reason": result["reason"],
                             "http_status": result.get("http_status")})
    return failures


def append_errors(failures: list[dict], checked_at: str, environment: str) -> None:
    """Append this run's findings to the cumulative, human-readable report."""
    if not ERRORS.exists():
        ERRORS.write_text(
            "# IPTV: ошибки проверки доступности\n\n"
            "Накопительный журнал. Ошибки проверки не исключают канал из `docs/playlist.m3u`.\n",
            encoding="utf-8",
        )
    if not failures:
        return
    with ERRORS.open("a", encoding="utf-8") as report:
        report.write(f"\n## Проверка {checked_at} — {environment}\n\n")
        for failure in failures:
            status = f", HTTP {failure['http_status']}" if failure.get("http_status") else ""
            ident = f" (`{failure['tvg_id']}`)" if failure.get("tvg_id") else ""
            report.write(
                f"- **{failure['name']}**{ident} — этап `{failure['stage']}`{status}: "
                f"{failure['reason']}.\n"
            )


def build(targets: list[Target], channels: list[dict], streams: list[dict],
          feeds: list[dict] | None = None) -> tuple[str, dict]:
    by_id = {c.get("id"): c for c in channels}
    feed_map = {(f.get("channel"), f.get("id")): f for f in (feeds or [])}
    stream_map: dict[str, list[dict]] = {}
    for s in streams:
        if isinstance(s.get("url"), str) and s["url"].startswith(("http://", "https://")):
            stream_map.setdefault(s.get("channel", ""), []).append(s)

    lines = ["#EXTM3U"]
    results, missing, emitted_urls = [], [], set()
    for target in targets:
        options = []
        for cid, channel in by_id.items():
            for stream in stream_map.get(cid, []):
                feed_id = str(stream.get("feed") or "")
                feed = feed_map.get((cid, feed_id), {"channel": cid, "id": feed_id,
                                                      "languages": channel.get("languages", []), "format": ""})
                url = str(stream.get("url", ""))
                score = candidate_score(target, channel, feed, stream)
                if score < 0:
                    continue
                options.append((score, cid, feed_id, channel, feed, stream))
        options.sort(key=lambda x: (x[0], max([int(n) for n in re.findall(
            r"\d+", str(x[5].get("quality") or x[4].get("format", "")))] or [0]), x[1], x[2]), reverse=True)
        if not options:
            missing.append({"name": target.name, "tvg_id": target.tvg_id or None,
                            "priority": target.priority, "reason": "no matching iptv-org stream"})
            continue
        score, cid, feed_id, channel, feed, stream = options[0]
        url = stream["url"]
        full_id = f"{cid}@{feed_id}" if feed_id else cid
        result = {"name": target.name, "tvg_id": full_id, "priority": target.priority,
                  "url": url, "quality": stream.get("quality") or feed.get("format"), "matched": True}
        results.append(result)
        if url in emitted_urls:
            continue
        emitted_urls.add(url)
        group = target.group.replace('"', "'")
        title = target.name.replace('"', "'")
        lines.append(f'#EXTINF:-1 tvg-id="{full_id}" group-title="{group}",{title}')
        lines.append(url)
    return "\n".join(lines) + "\n", {"source": "iptv-org/iptv", "found": results, "missing": missing,
                                                "target_count": len(targets), "found_count": len(results),
                                                "playlist_entry_count": len(emitted_urls)}


def assert_no_mass_loss(previous_found: int, current_found: int) -> None:
    if previous_found >= 5 and current_found < max(5, previous_found // 2):
        raise RuntimeError(f"mass match loss: {current_found} vs previous {previous_found}; preserving playlist")


def main() -> int:
    targets: list[Target] = []
    status: dict | None = None
    try:
        targets = parse_readme(README.read_text(encoding="utf-8"))
        channels, feeds, streams = (fetch_json("channels.json"), fetch_json("feeds.json"),
                                    fetch_json("streams.json"))
        output, status = build(targets, channels, streams, feeds)
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        status["state"] = "ok"
        old_found = 0
        if STATUS.exists():
            try:
                old_found = int(json.loads(STATUS.read_text(encoding="utf-8")).get("found_count", 0))
            except (ValueError, TypeError):
                pass
        # A 50% drop is treated as an upstream outage/data accident; retain last good playlist.
        assert_no_mass_loss(old_found, status["found_count"])
        checked_at = datetime.now(timezone.utc).isoformat()
        failures = validate_found_streams(status["found"])
        environment = "GitHub Actions runner" if os.environ.get("GITHUB_ACTIONS") == "true" \
            else "local runner network"
        status["access_check"] = {
            "environment": environment,
            "checked_at": checked_at,
            "failed_count": len(failures),
        }
        status["access_failures"] = failures
        append_errors(failures, checked_at, environment)
        PLAYLIST.write_text(output, encoding="utf-8")
        STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Updated: {status['found_count']}/{status['target_count']} targets; {status['playlist_entry_count']} unique URLs")
        return 0
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError, RuntimeError) as exc:
        # Keep the last playlist byte-for-byte, while making the failure visible in status.
        try:
            previous = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
        except (OSError, ValueError):
            previous = {}
        if not targets:
            print(f"Update failed before reading the README target tables: {exc}", file=sys.stderr)
            return 1
        if status is not None:
            status["state"] = "error"
            status["error"] = str(exc)
            status["previous_found_count"] = previous.get("found_count", 0)
            status["candidate_found_count"] = status.get("found_count", 0)
            status["candidate_playlist_entry_count"] = status.get("playlist_entry_count", 0)
            status["playlist_entry_count"] = previous.get("playlist_entry_count", 0)
            status["previous_playlist_retained"] = True
        elif targets:
            found = previous.get("found", [])
            found_names = {item.get("name") for item in found}
            missing = [{"name": t.name, "tvg_id": t.tvg_id or None, "priority": t.priority,
                        "reason": "iptv-org API unavailable; previous playlist retained"}
                       for t in targets if t.name not in found_names]
            status = {"source": "iptv-org/iptv", "updated_at": datetime.now(timezone.utc).isoformat(),
                      "state": "error", "error": str(exc), "found": found, "missing": missing,
                      "target_count": len(targets), "found_count": len(found),
                      "playlist_entry_count": previous.get("playlist_entry_count", 0),
                      "previous_playlist_retained": True}
        else:
            status = None
        if status is not None:
            STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Update unavailable; keeping last playlist and publishing status: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

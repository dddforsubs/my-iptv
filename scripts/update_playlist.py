#!/usr/bin/env python3
"""Build the public playlist from the channel tables in README.md and iptv-org."""
from __future__ import annotations

import json
import concurrent.futures
import os
import re
import socket
import shutil
import subprocess
import tempfile
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from ai_candidates import (CSV_URL, CandidateError, fetch_candidates, _public_host,
                           redact_url, url_has_credentials)

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PLAYLIST = ROOT / "docs/playlist.m3u"
STATUS = ROOT / "docs/status.json"
VALIDATION = ROOT / "docs/candidate_validation.json"
ERRORS = ROOT / "errors.md"
BASE = "https://iptv-org.github.io/api"
PROBE_TIMEOUT = 8
PROBE_WORKERS = 12
MAX_PLAYLIST_BYTES = 256 * 1024
MAX_SEGMENT_BYTES = 1024
CINERAMA_DOMAIN = "cinerama.uz"
CINERAMA_MARKERS = ("cinerama", "cinerama.uz", "кинотеатр cinerama")


@dataclass
class Target:
    name: str
    tvg_id: str
    group: str
    preference: str = ""
    priority: str = "B"
    candidate_ids: list[str] = field(default_factory=list)
    strict_candidates: bool = False
    preferred_urls: list[str] = field(default_factory=list)


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
    preferred_urls: dict[str, list[str]] = {}
    in_url_preferences = False
    for line in text.splitlines():
        if line.startswith("### Предпочтительные URL внутри тех же feed"):
            in_url_preferences = True
            continue
        if line.startswith("## ") or line.startswith("### "):
            in_url_preferences = False
        if not in_url_preferences or not line.startswith("|"):
            continue
        cells = markdown_cells(line)
        ident = cells[0].strip("`") if cells else ""
        if len(cells) < 2 or not re.fullmatch(r"[A-Za-z0-9.@_-]+", ident):
            continue
        urls = re.findall(r"`(https?://[^`]+)`", cells[-1])
        if urls:
            preferred_urls[ident] = urls
    for target in targets:
        for ident in [target.tvg_id, *target.candidate_ids]:
            if ident in preferred_urls:
                target.preferred_urls = preferred_urls[ident]
                break
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
    if stream.get("url") in target.preferred_urls:
        score += 10_000 - target.preferred_urls.index(stream["url"]) * 100
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


class _ProbeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            _public_host(newurl)
        except CandidateError as exc:
            raise urllib.error.URLError(f"unsafe redirect: {exc}") from exc
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_probe_bytes(url: str, stage: str, limit: int) -> tuple[bytes, str, int]:
    """Fetch a small prefix without cookies, auth, referrer, or stream-specific headers."""
    try:
        _public_host(url)
    except CandidateError as exc:
        raise ProbeError(stage, str(exc)) from exc
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "my-iptv-availability-check/1.0",
            "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
        },
    )
    try:
        opener = urllib.request.build_opener(_ProbeRedirect())
        with opener.open(request, timeout=PROBE_TIMEOUT) as response:
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


def _uses_unsupported_encryption(text: str) -> bool:
    for line in text.splitlines():
        if line.startswith(("#EXT-X-KEY:", "#EXT-X-SESSION-KEY:")):
            match = re.search(r"(?:^|,)METHOD=([^,]+)", line.partition(":")[2], re.I)
            if match and match.group(1).strip('"').upper() not in {"AES-128", "NONE"}:
                return True
    return False


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
        if _uses_unsupported_encryption(text):
            raise ProbeError("encryption", "unsupported encrypted/DRM HLS method", code)
        keys = _session_keys(text, final_url)
        variant_url = _master_variant(text, final_url)
        if variant_url:
            body, final_url, code = fetch_probe_bytes(variant_url, "media playlist", MAX_PLAYLIST_BYTES)
            text = _playlist_text(body, "media playlist", code)
            if _uses_unsupported_encryption(text):
                raise ProbeError("encryption", "unsupported encrypted/DRM HLS method", code)
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


def is_cinerama_risk(url: str) -> bool:
    """Treat the domain as a content-review signal, not an automatic blocklist."""
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
        return host == CINERAMA_DOMAIN or host.endswith("." + CINERAMA_DOMAIN)
    except ValueError:
        return False


def inspect_cinerama_content(url: str) -> dict:
    """Decode a live frame and OCR it when runner tools are available."""
    if not shutil.which("ffmpeg") or not shutil.which("tesseract"):
        return {"state": "unverified", "reason": "ffmpeg/tesseract unavailable"}
    with tempfile.TemporaryDirectory(prefix="iptv-frame-") as temp_dir:
        frame = str(Path(temp_dir) / "frame.png")
        try:
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", url,
                            "-frames:v", "1", "-vf", "scale=640:-1", frame],
                           timeout=20, check=True, capture_output=True)
            result = subprocess.run(["tesseract", frame, "stdout", "-l", "eng+rus"],
                                    timeout=10, check=True, capture_output=True, text=True)
            detected = any(marker in result.stdout.casefold() for marker in CINERAMA_MARKERS)
            return {"state": "advertisement_detected" if detected else "content_checked",
                    "reason": "CINERAMA marker recognized" if detected else "no known CINERAMA marker"}
        except (OSError, subprocess.SubprocessError) as exc:
            return {"state": "unverified", "reason": type(exc).__name__}


def probe_candidate(url: str) -> dict:
    """Probe transport first; inspect risky sources twice before quarantining."""
    result = check_stream_access(url)
    if not is_cinerama_risk(url) or result.get("state") not in {"accessible", "accessible_non_hls"}:
        return result
    inspections = [inspect_cinerama_content(url), inspect_cinerama_content(url)]
    result["content_check"] = inspections
    states = [item["state"] for item in inspections]
    if states.count("advertisement_detected") >= 1:
        return {**result, "state": "advertisement_detected", "stage": "content",
                "reason": "CINERAMA promotional slate detected in sampled frame"}
    if states.count("content_checked") < 2:
        return {**result, "state": "content_unverified", "stage": "content",
                "reason": "could not verify content in two sampled frames"}
    return result


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
    existing = ERRORS.read_text(encoding="utf-8")
    additions = []
    for failure in failures:
        status = f", HTTP {failure['http_status']}" if failure.get("http_status") else ""
        ident = f" (`{failure['tvg_id']}`)" if failure.get("tvg_id") else ""
        line = (f"- **{failure['name']}**{ident} — этап `{failure['stage']}`{status}: "
                f"{failure['reason']}.")
        if line not in existing and line not in additions:
            additions.append(line)
    if additions:
        with ERRORS.open("a", encoding="utf-8") as report:
            report.write(f"\n## Новые отказы {checked_at} — {environment}\n\n")
            report.write("\n".join(additions) + "\n")


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


def _channel_key(value: str) -> str:
    value = re.sub(r"\s+(?:HD|SD|4K)$", "", value.strip(), flags=re.I)
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def _ai_language_allowed(target: Target, candidate: dict) -> bool:
    language = candidate.get("language", "").casefold()
    has_english = bool(re.search(r"\b(?:en|eng|english)\b", language))
    if "ru" in target.preference.casefold() or target.group.endswith(" RU"):
        return not has_english
    if "en" in target.preference.casefold() or target.group.endswith(" EN"):
        return has_english
    return True


def build_with_validation(targets: list[Target], channels: list[dict], streams: list[dict],
                          feeds: list[dict], ai_candidates: list[dict], previous: dict,
                          probe=probe_candidate) -> tuple[str, dict, list[dict]]:
    """Try the prior URL first, then exact iptv-org and exact-name sheet candidates."""
    by_id = {str(c.get("id", "")): c for c in channels}
    feed_map = {(str(f.get("channel", "")), str(f.get("id", ""))): f for f in feeds}
    stream_map: dict[str, list[dict]] = {}
    for stream in streams:
        if (isinstance(stream.get("url"), str) and stream["url"].startswith(("http://", "https://"))
                and not url_has_credentials(stream["url"])):
            stream_map.setdefault(str(stream.get("channel", "")), []).append(stream)
    previous_records = {item.get("name"): item for item in previous.get("found", [])
                        if isinstance(item, dict) and item.get("name") and item.get("url")}
    previous_map = {item.get("name"): item for item in previous.get("found", [])
                    if isinstance(item, dict) and item.get("name") and item.get("url")
                    and not url_has_credentials(item["url"])}
    lines, found, missing, validations, emitted = ["#EXTM3U"], [], [], [], set()
    checks: dict[str, dict] = {}

    # Probe a bounded, prioritized candidate set concurrently. This keeps the
    # scheduled run practical while still allowing fallback selection after failures.
    preflight: set[str] = {item["url"] for item in previous_map.values()}
    for target in targets:
        ranked: list[tuple[int, str]] = []
        for cid, channel in by_id.items():
            for stream in stream_map.get(cid, []):
                feed_id = str(stream.get("feed") or "")
                feed = feed_map.get((cid, feed_id), {"channel": cid, "id": feed_id,
                    "languages": channel.get("languages", []), "format": ""})
                score = candidate_score(target, channel, feed, stream)
                if score >= 0:
                    ranked.append((score + 1000, stream["url"]))
        for candidate in ai_candidates:
            if (_channel_key(candidate.get("name", "")) == _channel_key(target.name)
                    and _ai_language_allowed(target, candidate)):
                ranked.append((500, candidate["url"]))
        ranked.sort(reverse=True)
        preflight.update(url for _, url in ranked[:6])
    with concurrent.futures.ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
        checks.update(zip(preflight, pool.map(probe, preflight)))

    for target in targets:
        options = []
        prior = previous_records.get(target.name)
        old = previous_map.get(target.name)
        if old:
            old_id = str(old.get("tvg_id") or "")
            old_channel_id, _, old_feed_id = old_id.partition("@")
            old_channel = by_id.get(old_channel_id)
            old_feed = feed_map.get((old_channel_id, old_feed_id), {})
            old_stream = {"channel": old_channel_id, "feed": old_feed_id, "url": old["url"],
                          "quality": old.get("quality")}
            old_is_eligible = (candidate_score(target, old_channel, old_feed, old_stream) >= 0
                               if old_channel else not target.candidate_ids)
            if old_is_eligible:
                previous_score = candidate_score(target, old_channel, old_feed, old_stream) if old_channel else 0
                options.append({"url": old["url"], "source": "previous", "score": previous_score,
                                "tvg_id": old.get("tvg_id", target.tvg_id), "quality": old.get("quality"),
                                "repository": old.get("repository"),
                                "language_state": old.get("language_state", "language_unverified")})
            else:
                old = None
        for cid, channel in by_id.items():
            for stream in stream_map.get(cid, []):
                feed_id = str(stream.get("feed") or "")
                feed = feed_map.get((cid, feed_id), {"channel": cid, "id": feed_id,
                    "languages": channel.get("languages", []), "format": ""})
                score = candidate_score(target, channel, feed, stream)
                if score < 0:
                    continue
                options.append({"url": stream["url"], "source": "iptv-org",
                    "score": score, "tvg_id": f"{cid}@{feed_id}" if feed_id else cid,
                    "quality": stream.get("quality") or feed.get("format"),
                    "repository": "iptv-org/iptv",
                    "language_state": "language_verified" if "rus" in feed.get("languages", [])
                        or "eng" in feed.get("languages", []) else "language_unverified"})
        for candidate in ai_candidates:
            if _channel_key(candidate.get("name", "")) != _channel_key(target.name):
                continue
            if not _ai_language_allowed(target, candidate):
                continue
            try:
                age_days = max(0, (datetime.now(timezone.utc).date() -
                                   datetime.fromisoformat(candidate["source_date"]).date()).days)
            except (KeyError, TypeError, ValueError):
                age_days = 180
            recency_bonus = max(0, 20 - age_days // 9)
            priority_bonus = {"P1": 5, "P2": 3, "P3": 1}.get(candidate.get("priority"), 0)
            options.append({"url": candidate["url"], "source": "ai_google_sheets",
                "score": 10 + (10 if candidate.get("language_state") == "language_inferred" else 0)
                    + recency_bonus + priority_bonus,
                "tvg_id": target.tvg_id, "quality": None,
                "repository": candidate.get("repository"),
                "source_file": candidate.get("source_file"),
                "source_date": candidate.get("source_date"),
                "language_state": candidate.get("language_state", "language_unverified"),
                })
        unique, seen = [], set()
        for option in sorted(options, key=lambda item: (item["score"], item["source"] == "previous"), reverse=True):
            if option["url"] in seen:
                continue
            seen.add(option["url"])
            unique.append(option)

        chosen, target_checked = None, []
        for option in unique[:12]:
            if option["url"] not in checks:
                checks[option["url"]] = probe(option["url"])
            check = checks[option["url"]]
            row = {"name": target.name, "url": redact_url(option["url"]), "source": option["source"],
                   "repository": option.get("repository"), "source_file": option.get("source_file"),
                   "source_date": option.get("source_date"), "result": check,
                   "quarantined": check.get("state") in {"advertisement_detected", "content_unverified"},
                   "quarantine_reason": check.get("reason") if check.get("state") in {
                       "advertisement_detected", "content_unverified"} else None,
                   "checked_at": datetime.now(timezone.utc).isoformat()}
            validations.append(row)
            target_checked.append(row)
            if check.get("state") in {"accessible", "accessible_non_hls"}:
                chosen = (option, check)
                break
        # Failed streams must never be republished as fallback. They remain in
        # validation history and are retried on the next scheduled run.
        if chosen is None:
            missing.append({"name": target.name, "tvg_id": target.tvg_id or None,
                            "priority": target.priority, "reason": "no exact eligible candidate"})
            continue
        option, access = chosen
        result = {"name": target.name, "tvg_id": option.get("tvg_id") or target.tvg_id,
            "priority": target.priority, "url": option["url"], "source": option["source"],
            "repository": option.get("repository"), "quality": option.get("quality"),
            "quality_state": "reported" if option.get("quality") else "unknown",
            "matched": True, "access_check": access,
            "language_state": option.get("language_state", "language_unverified"),
            "previous_url_replaced": bool(prior and prior.get("url") != option["url"]),
            "replacement_reason": ("previous URL failed technical check or eligibility policy"
                                   if prior and prior.get("url") != option["url"] else None),
            "candidates_checked": len(target_checked), "checked_at": datetime.now(timezone.utc).isoformat()}
        found.append(result)
        if option["url"] not in emitted:
            emitted.add(option["url"])
            group, name = target.group.replace('"', "'"), target.name.replace('"', "'")
            lines.extend([f'#EXTINF:-1 tvg-id="{result["tvg_id"]}" group-title="{group}",{name}', option["url"]])
    status = {"source": "iptv-org + ai_google_sheets", "found": found, "missing": missing,
        "target_count": len(targets), "found_count": len(found), "playlist_entry_count": len(emitted),
        "ai_candidates_loaded": len(ai_candidates),
        "ai_candidates_checked": sum(row["source"] == "ai_google_sheets" for row in validations),
        "automatic_replacements": sum(item["previous_url_replaced"] for item in found),
        "quarantined_urls": [{"name": row["name"], "url": row["url"],
            "reason": row["result"].get("reason"), "state": row["result"].get("state"),
            "checked_at": row["checked_at"]} for row in validations
            if row["result"].get("state") in {"advertisement_detected", "content_unverified"}]}
    return "\n".join(lines) + "\n", status, validations


def assert_no_mass_loss(previous_found: int, current_found: int) -> None:
    if previous_found >= 5 and current_found < max(5, previous_found // 2):
        raise RuntimeError(f"mass match loss: {current_found} vs previous {previous_found}; preserving playlist")


def should_retain_previous_playlist(previous_found: int, verified_count: int, has_playlist: bool) -> bool:
    return has_playlist and previous_found >= 5 and verified_count < max(5, previous_found // 2)


def main() -> int:
    targets: list[Target] = []
    status: dict | None = None
    try:
        targets = parse_readme(README.read_text(encoding="utf-8"))
        try:
            previous = json.loads(STATUS.read_text(encoding="utf-8")) if STATUS.exists() else {}
        except (OSError, ValueError):
            previous = {}
        candidates_url = os.environ.get("AI_CANDIDATES_CSV_URL", CSV_URL)
        candidates, sheet_state = fetch_candidates(candidates_url)
        channels, feeds, streams = (fetch_json("channels.json"), fetch_json("feeds.json"),
                                    fetch_json("streams.json"))
        output, status, candidate_validation = build_with_validation(
            targets, channels, streams, feeds, candidates, previous)
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        status["state"] = "ok"
        status["candidate_sheet"] = sheet_state
        old_found = int(previous.get("found_count", 0) or 0)
        # A 50% drop is treated as an upstream outage/data accident; retain last good playlist.
        assert_no_mass_loss(old_found, status["found_count"])
        checked_at = datetime.now(timezone.utc).isoformat()
        failures = []
        for item in status["found"]:
            result = item.get("access_check", {})
            if result.get("state") not in {"accessible", "accessible_non_hls"}:
                failures.append({"name": item["name"], "tvg_id": item["tvg_id"],
                    "stage": result.get("stage", "probe"), "reason": result.get("reason", "not checked"),
                    "http_status": result.get("http_status")})
        failures.extend({"name": item["name"], "tvg_id": item.get("tvg_id"),
                         "stage": "candidate matching", "reason": item["reason"]}
                        for item in status["missing"])
        if failures or status["missing"]:
            status["state"] = "partial"
        environment = "GitHub Actions runner" if os.environ.get("GITHUB_ACTIONS") == "true" \
            else "local runner network"
        status["access_check"] = {
            "environment": environment,
            "checked_at": checked_at,
            "failed_count": len(failures),
        }
        status["access_failures"] = failures
        status["verified_count"] = sum(item["access_check"].get("state") in {"accessible", "accessible_non_hls"}
                                       for item in status["found"])
        append_errors(failures, checked_at, environment)
        if should_retain_previous_playlist(old_found, status["verified_count"], PLAYLIST.exists()):
            status["previous_playlist_retained"] = True
            status["state"] = "degraded_mass_probe_failure"
        else:
            PLAYLIST.write_text(output, encoding="utf-8")
        STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validation_doc = {"checked_at": checked_at, "candidate_sheet": sheet_state,
                          "candidates_checked": len(candidate_validation), "candidates": candidate_validation}
        VALIDATION.write_text(json.dumps(validation_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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

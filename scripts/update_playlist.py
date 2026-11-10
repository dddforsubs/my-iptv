#!/usr/bin/env python3
"""Build the public playlist from the channel tables in README.md and iptv-org."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PLAYLIST = ROOT / "docs/playlist.m3u"
STATUS = ROOT / "docs/status.json"
BASE = "https://iptv-org.github.io/api"


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
        geo_blocked = False
        unsupported_format = False
        not_24_7 = False
        for cid, channel in by_id.items():
            for stream in stream_map.get(cid, []):
                feed_id = str(stream.get("feed") or "")
                feed = feed_map.get((cid, feed_id), {"channel": cid, "id": feed_id,
                                                      "languages": channel.get("languages", []), "format": ""})
                url = str(stream.get("url", ""))
                score = candidate_score(target, channel, feed, stream)
                if score < 0:
                    continue
                if "Geo-blocked" in stream.get("labels", []):
                    geo_blocked = True
                    continue
                if "Not 24/7" in stream.get("labels", []):
                    not_24_7 = True
                    continue
                if url.lower().split("?", 1)[0].endswith(".mpd"):
                    unsupported_format = True
                    continue
                options.append((score, cid, feed_id, channel, feed, stream))
        options.sort(key=lambda x: (x[0], max([int(n) for n in re.findall(
            r"\d+", str(x[5].get("quality") or x[4].get("format", "")))] or [0]), x[1], x[2]), reverse=True)
        if not options:
            reason = "geo_blocked" if geo_blocked else (
                "unsupported_format" if unsupported_format else (
                    "not_24_7" if not_24_7 else "no matching iptv-org stream"))
            missing.append({"name": target.name, "tvg_id": target.tvg_id or None, "priority": target.priority,
                            "reason": reason})
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

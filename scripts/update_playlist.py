#!/usr/bin/env python3
"""Build the public playlist from the channel tables in README.md and iptv-org."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
import urllib.error
import urllib.request
from dataclasses import dataclass
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
    """Read only the two canonical channel tables; preserve their order."""
    section = ""
    targets: list[Target] = []
    for line in text.splitlines():
        if line.startswith("## 1."):
            section = "A"
        elif line.startswith("## 2."):
            section = "B"
        elif line.startswith("## "):
            section = ""
        elif section in {"A", "B"} and line.startswith("|"):
            cells = markdown_cells(line)
            if not cells or not cells[0].isdigit():
                continue
            if section == "A":
                num, name, pref, candidate, _note = cells
                ids = re.findall(r"`([^`]+)`", candidate)
                targets.append(Target(name, ids[0] if ids else "", "Избранное", pref, "A"))
            else:
                _num, name, ident, group = cells
                ids = re.findall(r"`([^`]+)`", ident)
                targets.append(Target(name, ids[0] if ids else "", group, "", "B"))
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


def candidate_score(target: Target, channel: dict, stream: dict) -> int:
    cid = str(channel.get("id", ""))
    sid = str(stream.get("channel", ""))
    if not cid or sid != cid:
        return -1
    ident = target.tvg_id
    score = 0
    if ident and cid == ident:
        score += 1000
    elif ident and cid.split("@", 1)[0] == ident.split("@", 1)[0]:
        score += 100
    else:
        # Channels without a snapshot tvg-id (notably CNN) match exact names only.
        names = {str(channel.get(k, "")).casefold() for k in ("name", "alt_names")}
        aliases = {"cnn international": {"cnn international", "cnn international europe"}}
        wanted = target.name.casefold().strip()
        names |= aliases.get(wanted, set())
        if wanted not in names and not any(wanted in str(n).casefold() for n in channel.get("alt_names", [])):
            return -1
        score += 10
    if "CEE" in target.name.upper():
        # Do not allow Polish feeds as a substitute for CEE, even if similarly named.
        if not re.search(r"(?:@|\.)CEE(?:$|\.)", cid, re.I) and "CEE" not in str(stream.get("url", "")).upper():
            return -1
        if ".pl@" in cid.lower() or "polsat" in cid.lower():
            return -1
        score += 500
    elif target.priority == "A" and "RU" in target.preference.upper():
        langs = channel.get("languages", [])
        country = str(channel.get("country", ""))
        if country != "RU" and not cid.lower().endswith(".ru") and ".ru@" not in cid.lower():
            return -1
        if langs and "rus" not in langs:
            return -1
        score += 40 if "rus" in langs or country == "RU" or ".ru@" in cid.lower() else 0
    elif "EN" in target.preference.upper() or target.group.endswith(" EN"):
        score += 20 if "eng" in channel.get("languages", []) else 0
    quality = str(stream.get("quality", "")).upper()
    if "HD" in target.preference.upper():
        score += 15 if "HD" in quality or "1080" in quality else 0
    return score


def build(targets: list[Target], channels: list[dict], streams: list[dict]) -> tuple[str, dict]:
    by_id = {c.get("id"): c for c in channels}
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
                score = candidate_score(target, channel, stream)
                if score >= 0:
                    options.append((score, cid, channel, stream))
        options.sort(key=lambda x: (x[0], "1080" in str(x[3].get("quality", "")), x[1]), reverse=True)
        if not options:
            missing.append({"name": target.name, "tvg_id": target.tvg_id or None, "priority": target.priority,
                            "reason": "no matching iptv-org stream"})
            continue
        score, cid, channel, stream = options[0]
        url = stream["url"]
        result = {"name": target.name, "tvg_id": cid, "priority": target.priority,
                  "url": url, "quality": stream.get("quality"), "matched": True}
        results.append(result)
        if url in emitted_urls:
            continue
        emitted_urls.add(url)
        group = target.group.replace('"', "'")
        title = target.name.replace('"', "'")
        lines.append(f'#EXTINF:-1 tvg-id="{cid}" group-title="{group}",{title}')
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
        channels, streams = fetch_json("channels.json"), fetch_json("streams.json")
        output, status = build(targets, channels, streams)
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
        if status is not None:
            status["state"] = "error"
            status["error"] = str(exc)
        elif targets:
            found = previous.get("found", [])
            found_ids = {item.get("tvg_id") for item in found}
            missing = [{"name": t.name, "tvg_id": t.tvg_id or None, "priority": t.priority,
                        "reason": "iptv-org API unavailable; previous playlist retained"}
                       for t in targets if not t.tvg_id or t.tvg_id not in found_ids]
            status = {"source": "iptv-org/iptv", "updated_at": datetime.now(timezone.utc).isoformat(),
                      "state": "error", "error": str(exc), "found": found, "missing": missing,
                      "target_count": len(targets), "found_count": len(found),
                      "playlist_entry_count": previous.get("playlist_entry_count", 0)}
        else:
            status = None
        if status is not None:
            STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Update failed; keeping last playlist: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read an anonymously accessible Google Sheets CSV and verify a Task-written marker."""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

MAX_CSV_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 15
MAX_ROWS = 50_000
EXPECTED_COLUMN_C = "ChatGPT Scheduled Task"
EXPECTED_COLUMN_A = "TASK_WRITE_PROBE"


@dataclass
class ProbeFailure(Exception):
    message: str
    http_status: int | None = None
    details: dict | None = None

    def __str__(self) -> str:
        return self.message


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not let an HTTPS CSV request downgrade to HTTP during redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme.lower() != "https":
            raise ProbeFailure("redirect to a non-HTTPS URL was refused", code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_https_url(csv_url: str) -> None:
    parsed = urlsplit(csv_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ProbeFailure("csv_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ProbeFailure("csv_url must not contain embedded credentials")


def download_csv(csv_url: str) -> tuple[bytes, int, str]:
    validate_https_url(csv_url)
    request = urllib.request.Request(
        csv_url,
        headers={
            "Accept": "text/csv, application/csv, application/octet-stream;q=0.9, */*;q=0.1",
            "User-Agent": "chatgpt-sheets-probe/1.0",
        },
    )
    opener = urllib.request.build_opener(HttpsOnlyRedirectHandler())
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            http_status = int(response.getcode() or 0)
            content_type = response.headers.get("Content-Type", "")
            if http_status < 200 or http_status >= 300:
                raise ProbeFailure(f"CSV request returned HTTP {http_status}", http_status)
            payload = response.read(MAX_CSV_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            message = f"anonymous CSV access denied by Google (HTTP {exc.code}); publish or share the sheet for anonymous reading"
        else:
            message = f"CSV request returned HTTP {exc.code}"
        raise ProbeFailure(message, exc.code) from None
    except ProbeFailure:
        raise
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            message = f"CSV request timed out after {REQUEST_TIMEOUT_SECONDS} seconds"
        else:
            message = "CSV request failed before receiving an HTTP response"
        raise ProbeFailure(message) from None
    except TimeoutError:
        raise ProbeFailure(f"CSV request timed out after {REQUEST_TIMEOUT_SECONDS} seconds") from None
    except OSError:
        raise ProbeFailure("CSV request failed before receiving an HTTP response") from None

    if len(payload) > MAX_CSV_BYTES:
        raise ProbeFailure(f"CSV response exceeded the {MAX_CSV_BYTES}-byte size limit", http_status)
    return payload, http_status, content_type


def parse_utc_timestamp(value: str) -> datetime:
    """Accept an ISO 8601 timestamp with an explicit UTC offset only."""
    value = value.strip()
    if not value or "T" not in value:
        raise ValueError("timestamp must include an ISO 8601 date and time")
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamp is not a valid ISO 8601 date/time") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp must include the UTC timezone (Z or +00:00)")
    return parsed.astimezone(timezone.utc)


def validate_csv_bytes(payload: bytes, content_type: str, expected_marker: str) -> dict:
    if not expected_marker.strip():
        raise ProbeFailure("expected_marker must not be empty")

    prefix = payload.lstrip()[:256].lower()
    if "text/html" in content_type.lower() or prefix.startswith((b"<!doctype html", b"<html", b"<head")):
        raise ProbeFailure("Google returned an HTML page instead of CSV; the sheet may require sign-in")
    try:
        text = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ProbeFailure("CSV response is not valid UTF-8") from None
    if not text.strip():
        raise ProbeFailure("CSV response is empty")

    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error:
        raise ProbeFailure("CSV response is malformed") from None
    if len(rows) > MAX_ROWS:
        raise ProbeFailure(f"CSV contained more than the {MAX_ROWS}-row limit")
    rows_read = sum(1 for row in rows if any(cell.strip() for cell in row))
    if not rows_read:
        raise ProbeFailure("CSV contains no non-empty rows")

    exact_rows = [
        row for row in rows
        if len(row) >= 3
        and row[0].strip() == EXPECTED_COLUMN_A
        and row[1].strip() == expected_marker
        and row[2].strip() == EXPECTED_COLUMN_C
    ]
    if len(exact_rows) > 1:
        raise ProbeFailure(f"marker row is duplicated: found {len(exact_rows)} matching rows", details={
            "rows_read": rows_read, "matches": len(exact_rows)
        })
    if not exact_rows:
        marker_rows = [
            row for row in rows
            if len(row) >= 2 and row[0].strip() == EXPECTED_COLUMN_A and row[1].strip() == expected_marker
        ]
        if marker_rows:
            actual_c = marker_rows[0][2].strip() if len(marker_rows[0]) >= 3 else "<missing>"
            raise ProbeFailure(
                f"marker row has unexpected column C: expected {EXPECTED_COLUMN_C!r}, found {actual_c!r}",
                details={"rows_read": rows_read, "matches": 0},
            )
        raise ProbeFailure("marker row was not found", details={"rows_read": rows_read, "matches": 0})

    row = exact_rows[0]
    if len(row) < 4:
        raise ProbeFailure("matching marker row has no timestamp in column D", details={
            "rows_read": rows_read, "matches": 1
        })
    try:
        timestamp = parse_utc_timestamp(row[3])
    except ValueError as exc:
        raise ProbeFailure(f"matching marker row has an invalid column D timestamp: {exc}", details={
            "rows_read": rows_read, "matches": 1
        }) from None

    return {
        "rows_read": rows_read,
        "matches": 1,
        "written_at": timestamp.isoformat().replace("+00:00", "Z"),
    }


def write_job_summary(result: dict, summary_path: str | None) -> None:
    if not summary_path:
        return
    status = result.get("status", "FAIL")
    http_status = result.get("http_status")
    http_label = str(http_status) if http_status is not None else "not received"
    rows_read = result.get("rows_read")
    rows_label = str(rows_read) if rows_read is not None else "not parsed"
    marker = result.get("expected_marker", "")
    written_at = result.get("written_at") or "—"
    error = result.get("error") or "—"
    marker_state = "found" if result.get("found_marker") else "not found"
    summary = (
        "# ChatGPT Task → Google Sheets probe\n\n"
        f"- **Status:** {status}\n"
        f"- **CSV HTTP status:** {http_label}\n"
        f"- **Rows read (non-empty):** {rows_label}\n"
        f"- **Marker:** `{marker}` — {marker_state}\n"
        f"- **Write time (UTC):** {written_at}\n"
        f"- **Reason:** {error}\n"
    )
    with open(summary_path, "a", encoding="utf-8") as summary_file:
        summary_file.write(summary)


def run(csv_url: str, expected_marker: str, result_path: Path, summary_path: str | None) -> int:
    result = {
        "status": "FAIL",
        "http_status": None,
        "rows_read": None,
        "expected_marker": expected_marker,
        "found_marker": False,
        "written_at": None,
        "error": None,
        "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    try:
        payload, http_status, content_type = download_csv(csv_url)
        result["http_status"] = http_status
        validated = validate_csv_bytes(payload, content_type, expected_marker)
        result.update(validated)
        result["found_marker"] = True
        result["status"] = "PASS"
    except ProbeFailure as exc:
        result["error"] = exc.message
        if exc.http_status is not None:
            result["http_status"] = exc.http_status
        if exc.details:
            result.update(exc.details)
            result["found_marker"] = exc.details.get("matches", 0) > 0
    except Exception:
        result["error"] = "unexpected internal validation error"

    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_job_summary(result, summary_path)
    print(json.dumps({key: result[key] for key in (
        "status", "http_status", "rows_read", "expected_marker", "found_marker", "written_at", "error"
    )}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


def main() -> int:
    csv_url = os.environ.get("CSV_URL", "")
    expected_marker = os.environ.get("EXPECTED_MARKER", "")
    result_path = Path(os.environ.get("RESULT_PATH", "probe_result.json"))
    return run(csv_url, expected_marker, result_path, os.environ.get("GITHUB_STEP_SUMMARY"))


if __name__ == "__main__":
    raise SystemExit(main())

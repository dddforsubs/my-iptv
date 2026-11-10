#!/usr/bin/env python3
"""Verify a ChatGPT Task marker in an anonymously published Google Sheets CSV."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 20
MAX_ROWS = 50_000
EXPECTED_COLUMN_A = "TASK_WRITE_PROBE"
EXPECTED_COLUMN_C = "ChatGPT Scheduled Task"
RESULT_SOURCE = "google_sheets_published_csv"


class ProbeError(Exception):
    def __init__(self, code: str, message: str, http_status: int | None = None,
                 details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details


class HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme.lower() != "https":
            raise ProbeError("https_downgrade", "redirect to a non-HTTPS URL was refused", code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_csv(csv_url: str) -> tuple[bytes, int, str]:
    parsed = urlsplit(csv_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ProbeError("invalid_csv_url", "csv_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password:
        raise ProbeError("embedded_credentials", "csv_url must not contain embedded credentials")

    request = urllib.request.Request(
        csv_url,
        headers={
            "Accept": "text/csv, application/csv, application/octet-stream;q=0.9, */*;q=0.1",
            "User-Agent": "sheets-transport-probe/1.0",
        },
    )
    opener = urllib.request.build_opener(HttpsOnlyRedirectHandler())
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            http_status = int(response.getcode() or 0)
            content_type = response.headers.get("Content-Type", "")
            if http_status != 200:
                raise ProbeError("http_status", f"CSV endpoint returned HTTP {http_status}", http_status)
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ProbeError("http_status", f"CSV endpoint returned HTTP {exc.code}", exc.code) from None
    except ProbeError:
        raise
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            raise ProbeError("request_timeout", f"CSV request timed out after {REQUEST_TIMEOUT_SECONDS} seconds") from None
        raise ProbeError("network_error", "CSV request failed before receiving an HTTP response") from None
    except TimeoutError:
        raise ProbeError("request_timeout", f"CSV request timed out after {REQUEST_TIMEOUT_SECONDS} seconds") from None
    except OSError:
        raise ProbeError("network_error", "CSV request failed before receiving an HTTP response") from None

    if len(payload) > MAX_RESPONSE_BYTES:
        raise ProbeError("response_too_large", f"CSV response exceeded {MAX_RESPONSE_BYTES} bytes", http_status)
    return payload, http_status, content_type


def parse_utc_timestamp(value: str) -> str:
    value = value.strip()
    if not value or "T" not in value:
        raise ValueError("expected an ISO 8601 date/time with UTC timezone")
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        raise ValueError("invalid ISO 8601 date/time") from None
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC (Z or +00:00)")
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_csv(payload: bytes, content_type: str, expected_marker: str) -> dict:
    if not expected_marker.strip():
        raise ProbeError("invalid_expected_marker", "expected_marker must not be empty")
    prefix = payload.lstrip()[:512].lower()
    if "text/html" in content_type.lower() or prefix.startswith((b"<!doctype html", b"<html", b"<head")):
        raise ProbeError("html_response", "Google returned HTML instead of CSV; the response may be a sign-in page")
    if not payload:
        raise ProbeError("empty_csv", "CSV response is empty")
    try:
        text = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ProbeError("invalid_encoding", "CSV response is not valid UTF-8") from None
    if not text.strip():
        raise ProbeError("empty_csv", "CSV response is empty")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error:
        raise ProbeError("invalid_csv", "CSV response is malformed") from None
    if len(rows) > MAX_ROWS:
        raise ProbeError("too_many_rows", f"CSV exceeds the {MAX_ROWS}-row limit")

    rows_read = sum(1 for row in rows if any(cell.strip() for cell in row))
    matching_rows = [
        row for row in rows
        if len(row) >= 3
        and row[0].strip() == EXPECTED_COLUMN_A
        and row[1].strip() == expected_marker
        and row[2].strip() == EXPECTED_COLUMN_C
    ]
    if not matching_rows:
        raise ProbeError("marker_not_found", "no row matched columns A, B, and C", details={
            "rows_read": rows_read, "matches": 0
        })
    if len(matching_rows) != 1:
        raise ProbeError("marker_duplicated", f"expected one marker row, found {len(matching_rows)}", details={
            "rows_read": rows_read, "matches": len(matching_rows)
        })
    row = matching_rows[0]
    if len(row) < 4:
        raise ProbeError("invalid_timestamp", "matching marker row has no column D timestamp", details={
            "rows_read": rows_read, "matches": 1
        })
    try:
        task_timestamp = parse_utc_timestamp(row[3])
    except ValueError as exc:
        raise ProbeError("invalid_timestamp", str(exc), details={
            "rows_read": rows_read, "matches": 1
        }) from None
    return {"rows_read": rows_read, "matches": 1, "task_timestamp_utc": task_timestamp}


def base_result(expected_marker: str) -> dict:
    return {
        "status": "FAIL",
        "source": RESULT_SOURCE,
        "expected_marker": expected_marker,
        "rows_read": 0,
        "matches": 0,
        "task_timestamp_utc": None,
        "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "http_status": None,
        "csv_available": False,
        "error": None,
    }


def write_summary(result: dict, summary_path: str | None) -> None:
    if not summary_path:
        return
    status = result["status"]
    available = "yes" if result["csv_available"] else "no"
    http_status = result["http_status"] if result["http_status"] is not None else "not received"
    timestamp = result["task_timestamp_utc"] or "—"
    error = result["error"] or "—"
    summary = (
        "# ChatGPT Task → Google Sheets transport probe\n\n"
        f"- **Status:** {status}\n"
        f"- **CSV available:** {available}; HTTP `{http_status}`\n"
        f"- **Rows read:** {result['rows_read']}\n"
        f"- **Marker:** `{result['expected_marker']}`; matches: {result['matches']}\n"
        f"- **Task timestamp (UTC):** {timestamp}\n"
        f"- **Reason:** {error}\n"
    )
    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(summary)


def run_probe(csv_url: str, expected_marker: str, result_path: Path,
              summary_path: str | None = None) -> dict:
    result = base_result(expected_marker)
    try:
        payload, http_status, content_type = download_csv(csv_url)
        result["http_status"] = http_status
        result["csv_available"] = True
        result.update(validate_csv(payload, content_type, expected_marker))
        result["status"] = "PASS"
    except ProbeError as exc:
        result["error"] = exc.code
        result["diagnostic"] = exc.message
        if exc.http_status is not None:
            result["http_status"] = exc.http_status
            result["csv_available"] = exc.http_status == 200
        if exc.details:
            result.update(exc.details)
    except Exception:
        result["error"] = "internal_error"
        result["diagnostic"] = "unexpected internal validation error"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary(result, summary_path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-url", required=True)
    parser.add_argument("--expected-marker", required=True)
    args = parser.parse_args(argv)
    result = run_probe(args.csv_url, args.expected_marker, Path("probe_result.json"),
                       summary_path=os.environ.get("GITHUB_STEP_SUMMARY"))
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

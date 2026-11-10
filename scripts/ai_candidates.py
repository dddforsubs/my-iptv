"""Read and validate untrusted IPTV candidates from the published Google Sheet."""
from __future__ import annotations

import csv
import datetime as dt
import io
import ipaddress
import re
import socket
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit

CSV_URL = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vS8Dh4EbkkHr69fdhrBTHO3T5-"
           "db90GFag1VGfHVgOcuhDSVyLj-2txOcjfSj40_zyHaEUZSTsYqVxB/pub?gid=1796945403"
           "&single=true&output=csv")
TIMEOUT = 20
MAX_BYTES = 2 * 1024 * 1024
MAX_AGE_DAYS = 180
REQUIRED_COLUMNS = ("Канал", "Полный URL", "Репозиторий", "Ссылка на исходный файл",
                    "Дата исходного файла", "Приоритет", "Язык", "Совпадение",
                    "Техпроверка", "RU-аудио проверено", "Комментарий", "Дата поиска", "Статус")
SENSITIVE_NAMES = {"token", "access_token", "auth", "authorization", "password", "passwd",
                   "secret", "signature", "sig", "api_key", "apikey", "jwt", "key"}


class CandidateError(ValueError):
    pass


def _public_host(url: str) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise CandidateError("unsafe_url") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise CandidateError("unsafe_url")
    if port is not None and not 1 <= port <= 65535:
        raise CandidateError("unsafe_url")
    if url_has_credentials(url):
        raise CandidateError("credential_in_url")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".localhost", ".local", ".internal")):
        raise CandidateError("private_host")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in
                         socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                         type=socket.SOCK_STREAM)]
        except OSError as exc:
            raise CandidateError("dns_failure") from exc
    if not addresses or any(not addr.is_global for addr in addresses):
        raise CandidateError("private_host")


def url_has_credentials(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        return bool(parsed.username or parsed.password or any(
            name.casefold() in SENSITIVE_NAMES for name, _ in parse_qsl(parsed.query, keep_blank_values=True)))
    except ValueError:
        return True


def redact_url(url: str) -> str:
    """Keep a useful public location while stripping embedded credentials and secrets."""
    try:
        parsed = urlsplit(url)
        query = [(name, "REDACTED" if name.casefold() in SENSITIVE_NAMES else value)
                 for name, value in parse_qsl(parsed.query, keep_blank_values=True)]
        host = parsed.hostname or "invalid-host"
        netloc = host + (f":{parsed.port}" if parsed.port else "")
        return parsed._replace(netloc=netloc, query=urlencode(query)).geturl()
    except ValueError:
        return "[invalid URL redacted]"


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _public_host(newurl)
        if urlsplit(req.full_url).scheme == "https" and urlsplit(newurl).scheme != "https":
            raise CandidateError("https_downgrade_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def parse_csv(payload: bytes, today: dt.date | None = None) -> list[dict]:
    if len(payload) > MAX_BYTES:
        raise CandidateError("csv_too_large")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CandidateError("invalid_utf8") from exc
    if text.lstrip().lower().startswith(("<!doctype html", "<html", "<form")):
        raise CandidateError("html_instead_of_csv")
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or any(col not in headers for col in REQUIRED_COLUMNS):
            raise CandidateError("invalid_csv_schema")
        rows = list(reader)
    except (csv.Error, UnicodeError) as exc:
        raise CandidateError("invalid_csv") from exc
    if not rows and text.strip():
        raise CandidateError("invalid_csv")
    day = today or dt.datetime.now(dt.timezone.utc).date()
    unique, seen = [], set()
    for row in rows:
        if None in row or any(row.get(key) is None for key in REQUIRED_COLUMNS):
            continue
        title, url = row["Канал"].strip(), row["Полный URL"].strip()
        repo = row["Репозиторий"].strip()
        if not title or not url or not repo:
            continue
        source_file = row["Ссылка на исходный файл"].strip()
        source_parts = urlsplit(source_file)
        repo_parts = repo.split("/", 1)
        path_parts = [part for part in source_parts.path.split("/") if part]
        valid_github_source = (source_parts.scheme == "https" and source_parts.hostname in
            {"github.com", "raw.githubusercontent.com"} and len(repo_parts) == 2
            and not source_parts.username and not source_parts.password and not source_parts.query
            and len(path_parts) >= 3 and path_parts[0].casefold() == repo_parts[0].casefold()
            and path_parts[1].casefold() == repo_parts[1].casefold()
            and (source_parts.hostname == "raw.githubusercontent.com" or path_parts[2] in {"blob", "tree"}))
        if not valid_github_source:
            continue
        try:
            source_date = dt.date.fromisoformat(row["Дата исходного файла"].strip())
        except ValueError:
            continue
        if (day - source_date).days < 0 or (day - source_date).days > MAX_AGE_DAYS:
            continue
        try:
            _public_host(url)
        except CandidateError:
            continue
        key = (title.casefold(), url)
        if key in seen:
            continue
        seen.add(key)
        source_path = urlsplit(source_file).path.casefold()
        source_is_russian = bool(re.search(r"(?:^|/)ru(?:ssian)?(?:\.m3u8?)?$", source_path))
        unique.append({"name": title, "url": url, "repository": repo,
                       "source_file": source_file,
                       "source_date": source_date.isoformat(), "priority": row["Приоритет"].strip(),
                       "language": row["Язык"].strip(), "match": row["Совпадение"].strip(),
                       "comment": row["Комментарий"].strip(),
                       "language_state": "language_inferred" if source_is_russian and "RU" in row["Язык"].upper()
                       else "language_unverified"})
    return unique


def fetch_candidates(url: str = CSV_URL) -> tuple[list[dict], dict]:
    """Fetch anonymous published CSV. Failures are soft so iptv-org remains available."""
    try:
        _public_host(url)
        opener = urllib.request.build_opener(_SafeRedirect())
        request = urllib.request.Request(url, headers={"User-Agent": "my-iptv-candidate-reader/1.0"})
        with opener.open(request, timeout=TIMEOUT) as response:
            status = int(response.getcode() or 0)
            if status != 200:
                raise CandidateError(f"http_{status}")
            payload = response.read(MAX_BYTES + 1)
        candidates = parse_csv(payload)
        return candidates, {"available": True, "http_status": status, "rows_loaded": len(candidates)}
    except (OSError, urllib.error.URLError, CandidateError, csv.Error) as exc:
        status = getattr(exc, "code", None)
        return [], {"available": False, "http_status": status,
                    "error": str(exc) or type(exc).__name__, "rows_loaded": 0}

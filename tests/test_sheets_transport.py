import io
import importlib.util
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sheets_transport_impl", ROOT / "scripts" / "test_sheets_transport.py"
)
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


FIXTURES = ROOT / "tests" / "fixtures" / "chatgpt_sheets_probe"
MARKER = "IPTV-PROBE-20261110-X1"


def fixture(name):
    return (FIXTURES / name).read_bytes()


class SheetsTransportTests(unittest.TestCase):
    def test_valid_csv_and_marker_pass(self):
        result = transport.validate_csv(fixture("pass.csv"), "text/csv", MARKER)
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["rows_read"], 2)
        self.assertEqual(result["task_timestamp_utc"], "2026-11-10T19:15:19.999134Z")

    def test_missing_marker_fails(self):
        with self.assertRaisesRegex(transport.ProbeError, "no row matched") as caught:
            transport.validate_csv(fixture("missing_marker.csv"), "text/csv", MARKER)
        self.assertEqual(caught.exception.code, "marker_not_found")

    def test_duplicate_marker_fails(self):
        with self.assertRaisesRegex(transport.ProbeError, "found 2") as caught:
            transport.validate_csv(fixture("duplicate_marker.csv"), "text/csv", MARKER)
        self.assertEqual(caught.exception.code, "marker_duplicated")

    def test_html_login_page_fails(self):
        with self.assertRaisesRegex(transport.ProbeError, "HTML instead of CSV") as caught:
            transport.validate_csv(fixture("html_login.csv"), "text/html; charset=utf-8", MARKER)
        self.assertEqual(caught.exception.code, "html_response")

    def test_invalid_timestamp_fails(self):
        with self.assertRaises(transport.ProbeError) as caught:
            transport.validate_csv(fixture("invalid_timestamp.csv"), "text/csv", MARKER)
        self.assertEqual(caught.exception.code, "invalid_timestamp")

    def test_http_403_fails_with_status(self):
        self.assert_http_error(403)

    def test_http_404_fails_with_status(self):
        self.assert_http_error(404)

    def test_empty_csv_fails(self):
        with self.assertRaises(transport.ProbeError) as caught:
            transport.validate_csv(fixture("empty.csv"), "text/csv", MARKER)
        self.assertEqual(caught.exception.code, "empty_csv")

    def assert_http_error(self, status):
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://example.test/export.csv", status, "blocked", {}, io.BytesIO(b"")
        )
        with patch.object(transport.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(transport.ProbeError) as caught:
                transport.download_csv("https://example.test/export.csv")
        self.assertEqual(caught.exception.code, "http_status")
        self.assertEqual(caught.exception.http_status, status)


if __name__ == "__main__":
    unittest.main()

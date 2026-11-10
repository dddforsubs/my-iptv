import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_chatgpt_sheets_probe as probe


FIXTURES = ROOT / "tests" / "fixtures" / "chatgpt_sheets_probe"
MARKER = "IPTV-PROBE-20261110-X1"


def read_fixture(name):
    return (FIXTURES / name).read_bytes()


class SheetsProbeTests(unittest.TestCase):
    def test_correct_marker_passes(self):
        result = probe.validate_csv_bytes(read_fixture("pass.csv"), "text/csv", MARKER)
        self.assertEqual(result["matches"], 1)
        self.assertEqual(result["rows_read"], 2)
        self.assertEqual(result["written_at"], "2026-11-10T19:15:19.999134Z")

    def test_missing_marker_fails(self):
        with self.assertRaisesRegex(probe.ProbeFailure, "marker row was not found"):
            probe.validate_csv_bytes(read_fixture("missing_marker.csv"), "text/csv", MARKER)

    def test_duplicate_marker_fails(self):
        with self.assertRaisesRegex(probe.ProbeFailure, "duplicated"):
            probe.validate_csv_bytes(read_fixture("duplicate_marker.csv"), "text/csv", MARKER)

    def test_html_login_page_fails(self):
        with self.assertRaisesRegex(probe.ProbeFailure, "HTML page instead of CSV"):
            probe.validate_csv_bytes(read_fixture("html_login.csv"), "text/html; charset=utf-8", MARKER)

    def test_invalid_timestamp_fails(self):
        with self.assertRaisesRegex(probe.ProbeFailure, "invalid column D timestamp"):
            probe.validate_csv_bytes(read_fixture("invalid_timestamp.csv"), "text/csv", MARKER)


if __name__ == "__main__":
    unittest.main()

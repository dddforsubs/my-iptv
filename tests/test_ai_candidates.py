import csv
import importlib.util
import io
import sys
import unittest
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ai_candidates as ai

spec = importlib.util.spec_from_file_location("update_playlist_ai_test", ROOT / "scripts/update_playlist.py")
updater = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = updater
spec.loader.exec_module(updater)


class CandidateCsvTests(unittest.TestCase):
    def setUp(self):
        self.payload = (ROOT / "tests/fixtures/ai_candidates_valid.csv").read_bytes()

    def test_valid_csv_deduplicates_and_drops_stale_rows(self):
        with mock.patch.object(ai, "_public_host"):
            rows = ai.parse_csv(b"\xef\xbb\xbf" + self.payload, today=date(2026, 11, 10))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["repository"], "public/example")
        self.assertEqual(rows[0]["comment"], "fixture, quoted note")
        self.assertEqual(rows[0]["language_state"], "language_unverified")

    def test_russian_language_is_only_inferred_from_a_russian_playlist(self):
        payload = self.payload.replace(b"main/list.m3u", b"main/ru.m3u")
        with mock.patch.object(ai, "_public_host"):
            rows = ai.parse_csv(payload, today=date(2026, 11, 10))
        self.assertEqual(rows[0]["language_state"], "language_inferred")

    def test_schema_and_utf8_are_required(self):
        with self.assertRaisesRegex(ai.CandidateError, "invalid_csv_schema"):
            ai.parse_csv(b"Channel,URL\na,b\n")
        with self.assertRaisesRegex(ai.CandidateError, "invalid_utf8"):
            ai.parse_csv(b"\xff")

    def test_html_and_malformed_csv_are_rejected(self):
        with self.assertRaisesRegex(ai.CandidateError, "html_instead_of_csv"):
            ai.parse_csv(b"<html><body>Sign in</body></html>")
        broken = self.payload + b'"unclosed\n'
        with self.assertRaisesRegex(ai.CandidateError, "invalid_csv"):
            ai.parse_csv(broken)

    def test_unsafe_urls_are_not_accepted(self):
        for url in ("file:///etc/passwd", "https://user:pass@media.example/x.m3u8",
                    "http://127.0.0.1/private", "http://localhost/a.m3u8",
                    "https://media.example/live.m3u8?token=private"):
            with self.subTest(url=url), self.assertRaises(ai.CandidateError):
                ai._public_host(url)

    def test_sheet_failure_is_soft(self):
        with mock.patch.object(ai, "_public_host"), \
             mock.patch.object(ai.urllib.request, "build_opener", side_effect=urllib.error.URLError("offline")):
            rows, state = ai.fetch_candidates("https://media.example/sheet.csv")
        self.assertEqual(rows, [])
        self.assertFalse(state["available"])

    def test_http_403_and_404_are_reported(self):
        with mock.patch.object(ai, "_public_host"):
            for code in (403, 404):
                error = urllib.error.HTTPError("https://media.example/sheet.csv", code, "blocked", {}, None)
                with mock.patch.object(ai.urllib.request, "build_opener") as opener:
                    opener.return_value.open.side_effect = error
                    rows, state = ai.fetch_candidates("https://media.example/sheet.csv")
                error.close()
                self.assertEqual(rows, [])
                self.assertFalse(state["available"])
                self.assertEqual(state["http_status"], code)

    def test_https_downgrade_redirect_is_rejected(self):
        handler = ai._SafeRedirect()
        request = urllib.request.Request("https://media.example/source.csv")
        with mock.patch.object(ai, "_public_host"):
            with self.assertRaisesRegex(ai.CandidateError, "https_downgrade_redirect"):
                handler.redirect_request(request, None, 302, "Found", {}, "http://media.example/next.csv")

    def test_private_redirect_is_rejected_and_url_secrets_are_redacted(self):
        handler = ai._SafeRedirect()
        request = urllib.request.Request("https://media.example/source.csv")
        with mock.patch.object(ai, "_public_host", side_effect=ai.CandidateError("private_host")):
            with self.assertRaisesRegex(ai.CandidateError, "private_host"):
                handler.redirect_request(request, None, 302, "Found", {}, "https://127.0.0.1/next.csv")
        self.assertEqual(ai.redact_url("https://media.example/live.m3u8?token=secret"),
                         "https://media.example/live.m3u8?token=REDACTED")


class CandidateSelectionTests(unittest.TestCase):
    def test_second_candidate_replaces_failed_previous_stream(self):
        target = updater.Target("Discovery Channel HD", "DiscoveryChannel.ru@SD", "Избранное",
                                "RU / HD", "A", ["DiscoveryChannel.ru@SD"], False)
        channels = [{"id": "DiscoveryChannel.ru", "name": "Discovery Channel", "languages": ["rus"]}]
        feeds = [{"channel": "DiscoveryChannel.ru", "id": "SD", "languages": ["rus"], "format": "576i"}]
        streams = [{"channel": "DiscoveryChannel.ru", "feed": "SD", "url": "https://iptv.example/fail.m3u8"}]
        candidate = {"name": "Discovery Channel", "url": "https://ai.example/good.m3u8",
                     "repository": "public/iptv", "language": "RU — предполагается",
                     "language_state": "language_inferred", "source_date": "2026-10-31"}
        previous = {"found": [{"name": target.name, "tvg_id": target.tvg_id,
                               "url": "https://previous.example/fail.m3u8"}]}
        outcomes = {"https://previous.example/fail.m3u8": {"state": "restricted_or_unavailable", "reason": "timeout"},
                    "https://iptv.example/fail.m3u8": {"state": "restricted_or_unavailable", "reason": "404"},
                    "https://ai.example/good.m3u8": {"state": "accessible", "stage": "complete"}}
        output, status, validation = updater.build_with_validation(
            [target], channels, streams, feeds, [candidate], previous, lambda url: outcomes[url])
        self.assertIn("https://ai.example/good.m3u8", output)
        self.assertEqual(status["automatic_replacements"], 1)
        self.assertEqual(status["found"][0]["source"], "ai_google_sheets")
        self.assertEqual(status["found"][0]["language_state"], "language_inferred")
        self.assertEqual(len(validation), 3)

    def test_wrong_channel_and_wrong_language_are_rejected(self):
        target = updater.Target("Nat Geo Wild", "NationalGeographicWild.ru@SD", "Избранное", "RU", "A")
        similar_wrong_channel = {"name": "National Geographic", "url": "https://x.example/a.m3u8",
                                 "language": "RU", "language_state": "language_inferred"}
        english = {"name": "Nat Geo Wild", "url": "https://x.example/en.m3u8",
                   "language": "EN — original", "language_state": "language_unverified"}
        output, status, _ = updater.build_with_validation([target], [], [], [],
            [similar_wrong_channel, english], {}, lambda _url: {"state": "accessible"})
        self.assertEqual(status["found_count"], 0)
        self.assertEqual(status["missing"][0]["name"], target.name)
        self.assertEqual(output, "#EXTM3U\n")

    def test_previous_polish_feed_is_not_kept_for_cee_target(self):
        target = updater.Target("Viasat History CEE HD", "", "Избранное", "CEE / HD", "A",
                                ["ViasatHistory.cz@SD", "ViasatHistory.bg@SD"], False)
        channel = {"id": "PolsatViasatHistory.pl", "name": "Viasat History", "languages": ["pol"]}
        feeds = [{"channel": channel["id"], "id": "SD", "languages": ["pol"]}]
        previous = {"found": [{"name": target.name, "tvg_id": "PolsatViasatHistory.pl@SD",
                               "url": "https://stream.example/live.m3u8"}]}
        output, status, _ = updater.build_with_validation([target], [channel], [], feeds, [], previous,
            lambda _url: {"state": "accessible"})
        self.assertEqual(status["found_count"], 0)
        self.assertEqual(output, "#EXTM3U\n")

    def test_failed_probe_is_not_published(self):
        target = updater.Target("Discovery Channel", "DiscoveryChannel.ru@SD", "RU", "RU", "A")
        candidate = {"name": target.name, "url": "https://ai.example/fail.m3u8", "language": "RU",
                     "language_state": "language_inferred", "repository": "public/iptv"}
        output, status, _ = updater.build_with_validation([target], [], [], [], [candidate], {},
            lambda _url: {"state": "restricted_or_unavailable", "reason": "403"})
        self.assertEqual(status["found_count"], 0)
        self.assertEqual(status["missing"][0]["name"], target.name)
        self.assertEqual(output, "#EXTM3U\n")

    def test_ambiguous_failure_does_not_republish_previous_source(self):
        target = updater.Target("Discovery Channel", "DiscoveryChannel.ru@SD", "RU", "RU", "A")
        old = {"found": [{"name": target.name, "tvg_id": target.tvg_id,
                          "url": "https://previous.example/live.m3u8"}]}
        output, status, _ = updater.build_with_validation([target], [], [], [], [], old,
            lambda _url: {"state": "restricted_or_unavailable", "reason": "timeout"})
        self.assertEqual(status["found_count"], 0)
        self.assertEqual(status["missing"][0]["name"], target.name)
        self.assertEqual(output, "#EXTM3U\n")

    def test_confirmed_hd_feed_can_improve_working_sd_stream(self):
        target = updater.Target("Discovery Channel HD", "DiscoveryChannel.ru@SD", "Избранное",
                                "RU / HD", "A", ["DiscoveryChannel.ru@SD"], False)
        channel = {"id": "DiscoveryChannel.ru", "name": "Discovery Channel", "languages": ["rus"]}
        feeds = [
            {"channel": channel["id"], "id": "SD", "languages": ["rus"], "format": "576i"},
            {"channel": channel["id"], "id": "HD", "languages": ["rus"], "format": "1080i"},
        ]
        streams = [{"channel": channel["id"], "feed": "HD", "url": "https://iptv.example/hd.m3u8",
                    "quality": "1080p"}]
        previous = {"found": [{"name": target.name, "tvg_id": "DiscoveryChannel.ru@SD",
                               "url": "https://previous.example/sd.m3u8", "quality": "576i"}]}
        _, status, _ = updater.build_with_validation([target], [channel], streams, feeds, [], previous,
            lambda _url: {"state": "accessible"})
        self.assertEqual(status["found"][0]["url"], "https://iptv.example/hd.m3u8")
        self.assertTrue(status["found"][0]["previous_url_replaced"])

    def test_hls_chain_passes_and_http_200_html_fails(self):
        master = b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nmedia.m3u8\n"
        media = b"#EXTM3U\n#EXTINF:5,\nseg.ts\n#EXT-X-ENDLIST\n"
        def fetch(url, stage, limit):
            body = master if url.endswith("master.m3u8") else media if url.endswith("media.m3u8") else b"\x47" * 564
            final = url.rsplit("/", 1)[0] + "/" + ("media.m3u8" if body == master else "seg.ts") if body == master else url
            return body[:limit], final, 200
        with mock.patch.object(updater, "_public_host", create=True), \
             mock.patch.object(updater, "fetch_probe_bytes", side_effect=fetch):
            result = updater.check_stream_access("https://stream.example/master.m3u8")
            self.assertEqual(result["state"], "accessible")
            with mock.patch.object(updater, "fetch_probe_bytes", return_value=(b"<html>error</html>",
                    "https://stream.example/master.m3u8", 200)):
                html = updater.check_stream_access("https://stream.example/master.m3u8")
        self.assertEqual(html["state"], "restricted_or_unavailable")

    def test_drm_hls_is_not_probed_for_keys(self):
        sample_aes = b"#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,URI=\"key.bin\"\n#EXTINF:5,\nseg.ts\n"
        with mock.patch.object(updater, "_public_host", create=True), \
             mock.patch.object(updater, "fetch_probe_bytes", return_value=(sample_aes,
                    "https://stream.example/media.m3u8", 200)) as fetch:
            result = updater.check_stream_access("https://stream.example/media.m3u8")
        self.assertEqual(result["state"], "restricted_or_unavailable")
        self.assertEqual(result["stage"], "encryption")
        fetch.assert_called_once()


if __name__ == "__main__":
    unittest.main()

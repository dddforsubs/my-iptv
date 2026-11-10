import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("update_playlist", ROOT / "scripts/update_playlist.py")
updater = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = updater
spec.loader.exec_module(updater)


class PlaylistTests(unittest.TestCase):
    def test_readme_tables(self):
        targets = updater.parse_readme((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertEqual(len(targets), 73)
        self.assertEqual(targets[0].name, "Discovery Channel HD")
        self.assertEqual(sum(t.priority == "A" for t in targets), 17)
        self.assertEqual(sum(t.priority == "B" for t in targets), 47)
        children = [t for t in targets if t.priority == "C"]
        self.assertEqual(len(children), 9)
        self.assertEqual(children[0].candidate_ids, ["O.ru@SD", "O.ru@International"])
        self.assertEqual(children[0].group, "Детские RU")
        self.assertEqual(children[-1].group, "Kids EN")

    def test_m3u_output_and_deduplication(self):
        target = updater.Target("Example", "Example.ru@HD", "RU", "RU / HD", "A")
        channels = [{"id": "Example.ru@HD", "name": "Example", "country": "RU", "languages": ["rus"]}]
        streams = [{"channel": "Example.ru@HD", "url": "https://iptv-org.example/a.m3u8", "quality": "1080p"}]
        m3u, status = updater.build([target, target], channels, streams)
        self.assertEqual(m3u.count("#EXTINF"), 1)
        self.assertIn("#EXTM3U", m3u)
        self.assertEqual(status["found_count"], 2)
        self.assertEqual(status["playlist_entry_count"], 1)
        self.assertEqual(len(updater.parse_m3u(m3u)), 1)

    def test_rejects_malformed_m3u(self):
        with self.assertRaises(ValueError):
            updater.parse_m3u("#EXTM3U\n#EXTINF:-1,Missing URL\n")

    def test_polish_viasat_is_not_cee(self):
        target = updater.Target("Viasat History CEE HD", "", "Избранное", "CEE / HD", "A")
        channels = [{"id": "PolsatViasatHistory.pl", "name": "Viasat History CEE HD", "country": "PL"}]
        feeds = [{"channel": channels[0]["id"], "id": "SD", "languages": ["pol"]}]
        streams = [{"channel": channels[0]["id"], "feed": "SD", "url": "https://iptv-org.example/pl.m3u8"}]
        m3u, status = updater.build([target], channels, streams, feeds)
        self.assertEqual(status["found_count"], 0)
        self.assertEqual(status["missing"][0]["name"], target.name)
        self.assertEqual(m3u, "#EXTM3U\n")

    def test_non_cee_history2_not_relabelled(self):
        target = updater.Target("H2 CEE", "History2LatinAmerica.us@Panregional", "Избранное", "CEE", "A")
        channels = [{"id": "History2LatinAmerica.us@Panregional", "name": "History 2", "country": "US", "languages": ["eng"]}]
        streams = [{"channel": channels[0]["id"], "url": "https://iptv-org.example/h2.m3u8"}]
        self.assertEqual(updater.build([target], channels, streams)[1]["found_count"], 0)

    def test_children_match_only_allowed_feed_and_language(self):
        target = updater.Target("О!", "O.ru@SD", "Детские RU", "RU / HD preferred", "C",
                                ["O.ru@SD", "O.ru@International"], True)
        channel = {"id": "O.ru", "name": "О!", "languages": []}
        feeds = [
            {"channel": "O.ru", "id": "SD", "languages": ["rus"], "format": "576i"},
            {"channel": "O.ru", "id": "International", "languages": ["rus"], "format": "576i"},
            {"channel": "O.ru", "id": "HD", "languages": ["rus"], "format": "1080i"},
        ]
        streams = [
            {"channel": "O.ru", "feed": "SD", "url": "https://iptv-org.example/sd.m3u8"},
            {"channel": "O.ru", "feed": "International", "url": "https://iptv-org.example/int.m3u8"},
            {"channel": "O.ru", "feed": "HD", "url": "https://iptv-org.example/unlisted.m3u8"},
        ]
        output, status = updater.build([target], [channel], streams, feeds)
        self.assertEqual(status["found_count"], 1)
        self.assertIn('tvg-id="O.ru@SD"', output)
        self.assertNotIn("unlisted.m3u8", output)

    def test_children_do_not_accept_wrong_audio_language(self):
        target = updater.Target("О!", "O.ru@SD", "Детские RU", "RU / HD preferred", "C",
                                ["O.ru@SD"], True)
        channel = {"id": "O.ru", "name": "О!", "languages": []}
        feeds = [{"channel": "O.ru", "id": "SD", "languages": ["eng"], "format": "576i"}]
        streams = [{"channel": "O.ru", "feed": "SD", "url": "https://iptv-org.example/eng.m3u8"}]
        self.assertEqual(updater.build([target], [channel], streams, feeds)[1]["found_count"], 0)

    def test_a_priority_can_upgrade_same_channel_feed_quality(self):
        target = updater.Target("Discovery Channel HD", "DiscoveryChannel.ru@SD", "Избранное",
                                "RU / HD", "A", ["DiscoveryChannel.ru@SD"], False)
        channel = {"id": "DiscoveryChannel.ru", "name": "Discovery Channel", "languages": []}
        feeds = [
            {"channel": channel["id"], "id": "SD", "languages": ["rus"], "format": "576i"},
            {"channel": channel["id"], "id": "HD", "languages": ["rus"], "format": "1080i"},
        ]
        streams = [
            {"channel": channel["id"], "feed": "SD", "url": "https://iptv-org.example/sd.m3u8"},
            {"channel": channel["id"], "feed": "HD", "url": "https://iptv-org.example/hd.m3u8"},
        ]
        output, status = updater.build([target], [channel], streams, feeds)
        self.assertEqual(status["found"][0]["tvg_id"], "DiscoveryChannel.ru@HD")
        self.assertIn("hd.m3u8", output)

    def test_name_fallback_does_not_relabel_unrelated_channel_as_cnn(self):
        target = updater.Target("CNN International", "", "World News EN", "", "B")
        channel = {"id": "Univision.us", "name": "Univision", "alt_names": []}
        feed = {"channel": "Univision.us", "id": "SD", "languages": ["eng"]}
        stream = {"channel": "Univision.us", "feed": "SD", "url": "https://iptv-org.example/univision.m3u8"}
        self.assertEqual(updater.candidate_score(target, channel, feed, stream), -1)

    def test_mass_loss_guard(self):
        with self.assertRaises(RuntimeError):
            updater.assert_no_mass_loss(40, 10)
        updater.assert_no_mass_loss(40, 20)


if __name__ == "__main__":
    unittest.main()

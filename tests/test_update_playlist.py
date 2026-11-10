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
        self.assertEqual(len(targets), 64)
        self.assertEqual(targets[0].name, "Discovery Channel HD")
        self.assertEqual(sum(t.priority == "B" for t in targets), 47)

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
        channels = [{"id": "PolsatViasatHistory.pl@SD", "name": "Polsat Viasat History", "country": "PL", "languages": ["pol"]}]
        streams = [{"channel": channels[0]["id"], "url": "https://iptv-org.example/pl.m3u8"}]
        m3u, status = updater.build([target], channels, streams)
        self.assertEqual(status["found_count"], 0)
        self.assertEqual(status["missing"][0]["name"], target.name)
        self.assertEqual(m3u, "#EXTM3U\n")

    def test_non_cee_history2_not_relabelled(self):
        target = updater.Target("H2 CEE", "History2LatinAmerica.us@Panregional", "Избранное", "CEE", "A")
        channels = [{"id": "History2LatinAmerica.us@Panregional", "name": "History 2", "country": "US", "languages": ["eng"]}]
        streams = [{"channel": channels[0]["id"], "url": "https://iptv-org.example/h2.m3u8"}]
        self.assertEqual(updater.build([target], channels, streams)[1]["found_count"], 0)

    def test_mass_loss_guard(self):
        with self.assertRaises(RuntimeError):
            updater.assert_no_mass_loss(40, 10)
        updater.assert_no_mass_loss(40, 20)


if __name__ == "__main__":
    unittest.main()

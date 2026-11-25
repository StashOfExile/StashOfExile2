"""Patch Notes: only patch posts from Steam's news, newest first, with their version."""
import unittest

from soe2 import patchnotes as PN


class Pick(unittest.TestCase):
    def test_patch_posts_only(self):
        items = [{"title": "0.5.5d Patch Notes", "date": 200, "url": "https://store.steampowered.com/news/a"},
                 {"title": "Hotfix 1.0.0b", "date": 300, "url": "https://store.steampowered.com/news/b"},
                 {"title": "Twitch Drops for 1.0.0", "date": 400, "url": "https://store.steampowered.com/news/c"},
                 {"title": "Mystery Box sale", "date": 500, "url": "https://store.steampowered.com/news/d"},
                 {"title": "Patch Notes", "date": 100, "url": "http://not-https"}]
        got = PN.pick(items)
        self.assertEqual([g["version"] for g in got], ["1.0.0b", "0.5.5d"])

    def test_version_of(self):
        self.assertEqual(PN.version_of("Content Update 1.0.0 Patch Notes"), "1.0.0")
        self.assertEqual(PN.version_of("Patch Notes"), "")


if __name__ == "__main__":
    unittest.main()

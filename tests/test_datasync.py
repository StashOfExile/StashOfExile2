"""New game data from main without a release: only shipped data files and snapshots, newer ones, checked."""
import gzip
import hashlib
import json
import os
import unittest

from soe2 import datasync as DS
from soe2.config import BUNDLED_DATA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Plan(unittest.TestCase):
    def test_only_newer_shipped_files(self):
        m = {"files": {"modlists.json": {"version": 99, "sha256": "a" * 64},
                       "gamedb.json": {"version": 1, "sha256": "b" * 64},
                       "soe2/app.py": {"version": 99, "sha256": "c" * 64}},
             "snapshots": {"poe2-1.0.0.1.json.gz": "d" * 64, "../evil.json.gz": "e" * 64}}
        files, snaps = DS.plan(m, {"gamedb.json": 5}, set())
        self.assertEqual([f[0] for f in files], ["modlists.json"])
        self.assertEqual([s[0] for s in snaps], ["poe2-1.0.0.1.json.gz"])

    def test_bad_download_is_refused(self):
        blob = b'{"a": 1}'
        self.assertTrue(DS._good("x.json", blob, hashlib.sha256(blob).hexdigest()))
        self.assertFalse(DS._good("x.json", blob, "0" * 64))
        broken = b"{not json"
        self.assertFalse(DS._good("x.json", broken, hashlib.sha256(broken).hexdigest()))
        gz = gzip.compress(b"{}")
        self.assertTrue(DS._good("poe2-1.json.gz", gz, hashlib.sha256(gz).hexdigest()))


class Manifest(unittest.TestCase):
    def test_manifest_matches_the_files(self):
        """Run py tools/build_data_manifest.py after changing a data file or BUNDLED_DATA."""
        with open(os.path.join(ROOT, "data_manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        for name, e in m["files"].items():
            self.assertEqual(e["version"], BUNDLED_DATA[name], name)
            with open(os.path.join(ROOT, name), "rb") as f:
                self.assertEqual(e["sha256"], hashlib.sha256(f.read()).hexdigest(), name)


if __name__ == "__main__":
    unittest.main()

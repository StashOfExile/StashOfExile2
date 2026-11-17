"""3.0.6 (owner: "an install method ... so it comes up in the windows search as an installed program ... I still want
the portable option"): Setup-StashOfExile2-<version>.exe next to the portable exe on every release.

  * The updater never takes the installer - the portable exe stays the one it swaps in (old apps too: the installer's
    name doesn't start with "StashOfExile2", which they sort first).
  * The installer is per user (no admin), shows in Start / Settings > Apps, keeps the data folder, and marks its copy
    (installed.txt) so the app can keep the version in Settings > Apps current.
  * The release builds it, checks it and lists it."""
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from soe2 import updates  # noqa: E402


def read(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


def asset(name):
    return {"name": name, "browser_download_url": f"https://github.com/{updates.REPO}/releases/download/v3.0.6/{name}"}


class Updater(unittest.TestCase):
    def test_never_the_installer(self):
        rel = {"assets": [asset("Setup-StashOfExile2-3.0.6.exe"), asset("StashOfExile2.exe"),
                          asset("StashOfExile2_build_kit_3.0.6.zip")]}
        orig = sys.platform
        try:
            sys.platform = "win32"
            self.assertEqual(updates.pick_asset(rel, frozen=True)["name"], "StashOfExile2.exe")
        finally:
            sys.platform = orig

    def test_old_apps_sort_the_portable_first(self):
        """Their rule: .exe files whose name starts with "stashofexile2" first."""
        self.assertFalse("Setup-StashOfExile2-3.0.6.exe".lower().startswith("stashofexile2"))

    def test_installed_marker(self):
        self.assertFalse(updates.installed())               # (tests don't run frozen)
        self.assertFalse(updates.note_installed_version("9.9.9"))


class Script(unittest.TestCase):
    def setUp(self):
        self.iss = read("installer", "StashOfExile2.iss")

    def test_per_user_no_admin(self):
        self.assertIn("PrivilegesRequired=lowest", self.iss)
        self.assertIn(r"{localappdata}\Programs\{#Dir}", self.iss)

    def test_start_menu_and_uninstall(self):
        self.assertIn("{autoprograms}", self.iss)
        self.assertIn("UninstallDisplayName", self.iss)

    def test_marks_its_copy_and_keeps_data(self):
        self.assertIn('Source: "installed.txt"', self.iss)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "installer", "installed.txt")))
        self.assertNotIn("APPDATA", self.iss.split("[UninstallDelete]")[1])   # (your data is never removed)

    def test_same_id_as_the_app_reads(self):
        m = re.search(r'#define Id "\{(\{[0-9A-F-]+\})"\n#endif', self.iss)
        self.assertIsNotNone(m)
        self.assertIn(m.group(1) + "_is1", updates.INSTALL_KEY)

    def test_name_not_like_the_portable(self):
        self.assertIn("OutputBaseFilename=Setup-{#Dir}-{#AppVersion}", self.iss)


class Release(unittest.TestCase):
    def test_built_checked_and_listed(self):
        y = read(".github", "workflows", "release.yml")
        self.assertIn(r"installer\StashOfExile2.iss", y)
        self.assertIn('sha256sum StashOfExile2.exe "Setup-StashOfExile2-$V.exe"', y)
        self.assertIn("dist/Setup-StashOfExile2-*.exe", y)

    def test_local_script(self):
        self.assertIn("winget install JRSoftware.InnoSetup", read("build_installer.bat"))


if __name__ == "__main__":
    unittest.main()

"""3.0.6 (owner): a bug report says the OS and the app version - never a build number or a user name.

    python3.12 -m unittest tests.test_bug_report_os          (or tests/runall.sh)"""
import os
import sys
import tempfile
import unittest
from unittest import mock

HOME = tempfile.mkdtemp(prefix="soe2-os-")
os.environ["HOME"] = os.environ["APPDATA"] = HOME
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from soe2 import feedback_page as F                 # noqa: E402


class OsLine(unittest.TestCase):
    def test_windows(self):
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(F.platform, "version", lambda: "10.0.22631"), \
                mock.patch.object(F.platform, "release", lambda: "10"):
            self.assertEqual(F.os_line(), "Windows 11")
        with mock.patch.object(sys, "platform", "win32"), \
                mock.patch.object(F.platform, "version", lambda: "10.0.19045"), \
                mock.patch.object(F.platform, "release", lambda: "10"):
            self.assertEqual(F.os_line(), "Windows 10")

    def test_linux(self):
        from soe2 import linsys
        with mock.patch.object(sys, "platform", "linux"), mock.patch.object(linsys, "distro", lambda: "arch"), \
                mock.patch.object(linsys, "desktop", lambda: "Hyprland"), \
                mock.patch.object(linsys, "session_type", lambda: "wayland"):
            self.assertEqual(F.os_line(), "Linux (arch) · Hyprland · wayland")

    def test_in_the_report(self):
        src = open(os.path.join(ROOT, "soe2", "feedback_page.py"), encoding="utf-8").read()
        self.assertIn('f"**App** {APP_VERSION} · {os_line()}', src)


if __name__ == "__main__":
    unittest.main()

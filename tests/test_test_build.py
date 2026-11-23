"""3.3.0 owner: a test build updated itself to the GitHub release. StashOfExile2-Test.exe never checks.

    python3.12 -m unittest tests.test_test_build          (or tests/runall.sh)"""
import importlib
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


class TestBuild(unittest.TestCase):
    def test_the_test_exe_is_a_test_build(self):
        from soe2 import config
        try:
            with mock.patch.object(sys, "executable", r"C:\Builds\soe2\dist\StashOfExile2-Test.exe"):
                importlib.reload(config)
                self.assertTrue(config.TEST_BUILD)
            with mock.patch.object(sys, "executable", r"C:\Apps\StashOfExile2.exe"):
                importlib.reload(config)
                self.assertFalse(config.TEST_BUILD)
        finally:
            importlib.reload(config)

    def test_no_update_check_in_a_test_build(self):
        from soe2 import app as A
        host = mock.Mock()
        with mock.patch("soe2.config.TEST_BUILD", True):
            A.App.startup_update_check(host)
        host.check_updates.assert_not_called()
        with mock.patch("soe2.config.TEST_BUILD", False), mock.patch.dict(A.SETTINGS, {"auto_update": True}):
            A.App.startup_update_check(host)
        host.check_updates.assert_called_once_with(mode="auto")


if __name__ == "__main__":
    unittest.main()

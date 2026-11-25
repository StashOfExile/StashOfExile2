"""Count me as a user is asked once on the Dashboard, beside data sharing."""
import unittest
from unittest import mock

from soe2 import dashboard_page as D
from soe2.config import SETTINGS


class UsageAsk(unittest.TestCase):
    def setUp(self):
        self.keep = {k: SETTINGS.get(k) for k in ("usage_ping", "dash_usage_asked")}

    def tearDown(self):
        for k, v in self.keep.items():
            SETTINGS.pop(k, None) if v is None else SETTINGS.__setitem__(k, v)

    def test_asked_once(self):
        SETTINGS["usage_ping"] = False
        SETTINGS.pop("dash_usage_asked", None)
        self.assertTrue(D.usage_prompt_due())
        with mock.patch("soe2.usage.save_json"):
            D.usage_prompt_answer(False)
        self.assertFalse(D.usage_prompt_due())
        self.assertFalse(SETTINGS["usage_ping"])

    def test_yes_turns_it_on(self):
        SETTINGS["usage_ping"] = False
        SETTINGS.pop("dash_usage_asked", None)
        with mock.patch("soe2.usage.save_json"):
            D.usage_prompt_answer(True)
        self.assertTrue(SETTINGS["usage_ping"])
        self.assertFalse(D.usage_prompt_due())


if __name__ == "__main__":
    unittest.main()

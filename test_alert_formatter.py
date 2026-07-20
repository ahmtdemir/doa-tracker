import unittest

from alert_formatter import change_title, safe_apply_simultaneous_emptying


class AlertLogicTests(unittest.TestCase):
    def test_stale_critical_band_does_not_alert_at_76(self):
        item = {
            "_changed": True,
            "_previousState": True,
            "confirmedState": True,
            "rawState": True,
            "_previousBand": "critical",
            "confirmedBand": "critical",
            "_previousLevel": 98,
            "filteredLevel": 76,
        }
        self.assertIsNone(change_title(item))

    def test_real_critical_transition(self):
        item = {
            "_changed": True,
            "_previousState": True,
            "confirmedState": True,
            "rawState": True,
            "_previousBand": "nearly_full",
            "confirmedBand": "critical",
            "_previousLevel": 88,
            "filteredLevel": 92,
        }
        self.assertIn("KRITIK", change_title(item).replace("İ", "I"))

    def test_unsuitable_is_independent_from_percentage(self):
        item = {
            "_changed": True,
            "_previousState": True,
            "confirmedState": False,
            "rawState": False,
            "_previousBand": "filling",
            "confirmedBand": "nearly_full",
            "_previousLevel": 65,
            "filteredLevel": 82,
        }
        self.assertIn("UYGUN DEGIL", change_title(item).replace("Ğ", "G").replace("İ", "I"))

    def test_emptying_preserves_suitability(self):
        state = {"bins": {
            "pet": {"level": 0, "confirmedState": False},
            "aluminum": {"level": 12, "confirmedState": True},
        }}
        old = {"bins": {
            "pet": {"filteredLevel": 92, "confirmedBand": "critical"},
            "aluminum": {"filteredLevel": 94, "confirmedBand": "critical"},
        }}
        self.assertTrue(safe_apply_simultaneous_emptying(state, old))
        self.assertFalse(state["bins"]["pet"]["confirmedState"])
        self.assertTrue(state["bins"]["aluminum"]["confirmedState"])


if __name__ == "__main__":
    unittest.main()

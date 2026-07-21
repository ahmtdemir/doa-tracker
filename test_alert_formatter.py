import unicodedata
import unittest

from alarm_level_fix import confirm_boolean_two_way as safe_confirm_boolean
from alert_formatter import (
    change_title,
    command_card,
    safe_apply_simultaneous_emptying,
)


def searchable(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


class AlertLogicTests(unittest.TestCase):
    def test_stale_critical_state_does_not_alert_at_76(self):
        item = {
            "_previousState": True,
            "confirmedState": True,
            "rawState": True,
            "_previousLevel": 98,
            "level": 76,
        }
        self.assertIsNone(change_title(item))

    def test_real_critical_crossing(self):
        item = {
            "_previousState": True,
            "confirmedState": True,
            "rawState": True,
            "_previousLevel": 88,
            "level": 92,
        }
        self.assertIn("kritik", searchable(change_title(item)))

    def test_unsuitable_is_immediate(self):
        item = {
            "_previousState": True,
            "confirmedState": False,
            "rawState": False,
            "_previousLevel": 65,
            "level": 82,
        }
        self.assertIn("uygun degil", searchable(change_title(item)))

    def test_return_to_suitable_needs_two_samples(self):
        old = {"confirmedState": False, "stateCandidate": None, "stateCandidateCount": 0}
        confirmed, candidate, count, changed = safe_confirm_boolean(True, old)
        self.assertFalse(confirmed)
        self.assertTrue(candidate)
        self.assertEqual(count, 1)
        self.assertFalse(changed)

        old = {"confirmedState": False, "stateCandidate": True, "stateCandidateCount": 1}
        confirmed, candidate, count, changed = safe_confirm_boolean(True, old)
        self.assertTrue(confirmed)
        self.assertIsNone(candidate)
        self.assertEqual(count, 0)
        self.assertTrue(changed)

    def test_single_bin_emptying_is_detected(self):
        state = {"bins": {"pet": {"level": 20, "confirmedState": True}}}
        old = {"bins": {"pet": {"level": 83, "confirmedState": True}}}
        self.assertTrue(safe_apply_simultaneous_emptying(state, old))
        self.assertTrue(state["bins"]["pet"]["_definiteEmptying"])

    def test_hard_drop_is_reported(self):
        item = {
            "_previousState": True,
            "confirmedState": True,
            "rawState": True,
            "_previousLevel": 83,
            "level": 38,
        }
        self.assertIn("sert", searchable(change_title(item)))

    def test_card_order_is_glass_pet_aluminum(self):
        state = {
            "name": "Test",
            "operationPriority": "DÜŞÜK",
            "bins": {
                "aluminum": {"level": 10, "rawState": True},
                "pet": {"level": 20, "rawState": True},
                "glass": {"level": 30, "rawState": True},
            },
        }
        text = command_card(state)
        self.assertLess(text.index("CAM"), text.index("PET"))
        self.assertLess(text.index("PET"), text.index("ALÜMİNYUM"))


if __name__ == "__main__":
    unittest.main()

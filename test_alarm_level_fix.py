import unittest

from alarm_level_fix import use_previous_raw_level
from alert_formatter import change_title


class RawLevelAlarmTests(unittest.TestCase):
    @staticmethod
    def original(raw, old=None, checked_at=None):
        return {
            "level": raw["level"],
            "filteredLevel": 88,
            "confirmedState": False,
            "rawState": False,
            "_previousLevel": 88,
            "_previousState": False,
        }

    def test_same_raw_level_ignores_filtered_difference(self):
        wrapped = use_previous_raw_level(self.original)
        item = wrapped({"level": 91}, {"level": 91, "filteredLevel": 88})
        self.assertEqual(item["_previousLevel"], 91)
        self.assertIsNone(change_title(item))

    def test_real_raw_threshold_crossing_is_kept(self):
        wrapped = use_previous_raw_level(self.original)
        item = wrapped({"level": 91}, {"level": 88, "filteredLevel": 88})
        self.assertEqual(item["_previousLevel"], 88)
        self.assertIsNotNone(change_title(item))

    def test_general_levels_use_previous_raw_value(self):
        wrapped = use_previous_raw_level(self.original)
        scenarios = [(24, 24), (39, 39), (79, 80), (89, 90), (83, 38), (97, 97)]
        for before, current in scenarios:
            with self.subTest(before=before, current=current):
                item = wrapped({"level": current}, {"level": before, "filteredLevel": max(0, before - 3)})
                self.assertEqual(item["_previousLevel"], before)


if __name__ == "__main__":
    unittest.main()

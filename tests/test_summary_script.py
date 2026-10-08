import unittest
from datetime import date, datetime

from scripts.send_monthly_summary import parse_month, target_month


class TestMonthArguments(unittest.TestCase):
    def test_parse_month(self):
        self.assertEqual(parse_month("2026-09"), (2026, 9))

    def test_invalid_month(self):
        with self.assertRaises(ValueError):
            parse_month("2026-13")

    def test_default_is_previous_month(self):
        self.assertEqual(target_month(None, datetime(2026, 11, 1, 12, 17)), (2026, 10))
        self.assertEqual(target_month(None, datetime(2027, 1, 1)), (2026, 12))

    def test_explicit_month_wins(self):
        self.assertEqual(target_month("2026-09", datetime(2026, 11, 1)), (2026, 9))

    def test_until_is_an_iso_date(self):
        # argparse turns the flag into a date with date.fromisoformat
        self.assertEqual(date.fromisoformat("2026-10-09"), date(2026, 10, 9))


if __name__ == "__main__":
    unittest.main()

"""Tests for the CSV parsing in scripts/import_csv.py, using the demo CSV."""

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

# The script reads these at import time; create_engine() never connects here.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")
os.environ.setdefault("OMDB_API_KEY", "test-key")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import import_csv  # noqa: E402

DEMO_CSV = ROOT / "examples" / "demo_ratings.csv"


class TestReadDemoCsv(unittest.TestCase):
    def setUp(self):
        self.rows = import_csv.read_csv(DEMO_CSV)

    def test_finds_every_rating_and_skips_blank_rows(self):
        self.assertEqual(len(self.rows), 6)

    def test_maps_french_headers(self):
        first = self.rows[0]
        self.assertEqual(first["contributor"], "Alice")
        self.assertEqual(first["title"], "Amélie")
        self.assertEqual(first["director"], "Jean-Pierre Jeunet")
        self.assertEqual(first["score_raw"], "8.5")
        self.assertEqual(first["comment"], "Pure charm. The soundtrack alone is worth it.")


class TestParsers(unittest.TestCase):
    def test_parse_score(self):
        self.assertEqual(import_csv.parse_score("8.5"), 8.5)
        self.assertEqual(import_csv.parse_score("6,5"), 6.5)
        self.assertIsNone(import_csv.parse_score("45000"))  # Excel serial date
        self.assertIsNone(import_csv.parse_score(""))

    def test_parse_watch_date_formats(self):
        cases = {
            "12/03/2026": datetime(2026, 3, 12),
            "04/2026": datetime(2026, 4, 1),
            "mars 2026": datetime(2026, 3, 1),
            "11.2025": datetime(2025, 11, 1),
            "2025": datetime(2025, 1, 1),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(import_csv.parse_watch_date(raw), expected)
        self.assertIsNone(import_csv.parse_watch_date("n/a"))

    def test_parse_mom_compatible(self):
        self.assertTrue(import_csv.parse_mom_compatible("Oui"))
        self.assertFalse(import_csv.parse_mom_compatible("Non"))
        self.assertIsNone(import_csv.parse_mom_compatible("bof"))


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import date, datetime

from summary.facts import RatingRow, compute_facts, month_before, month_bounds_utc, round1, tier_for


def row(film, who, score, genres="Drama", comment=None):
    return RatingRow(film=film, year="2020", genres=genres, who=who, score=score, comment=comment)


class TestMonths(unittest.TestCase):
    def test_month_before(self):
        self.assertEqual(month_before(2026, 10), (2026, 9))
        self.assertEqual(month_before(2027, 1), (2026, 12))

    def test_summer_month_bounds(self):
        # Paris is UTC+2 in summer
        self.assertEqual(
            month_bounds_utc(2026, 9),
            (datetime(2026, 8, 31, 22, 0), datetime(2026, 9, 30, 22, 0)),
        )

    def test_month_with_daylight_saving_change(self):
        # Clocks go back on 25 Oct 2026: the month ends at UTC+1
        self.assertEqual(
            month_bounds_utc(2026, 10),
            (datetime(2026, 9, 30, 22, 0), datetime(2026, 10, 31, 23, 0)),
        )

    def test_december_rolls_into_next_year(self):
        self.assertEqual(month_bounds_utc(2026, 12)[1], datetime(2026, 12, 31, 23, 0))

    def test_until_extends_the_end(self):
        # September plus the first days of October, up to 9 Oct 00:00 Paris
        self.assertEqual(
            month_bounds_utc(2026, 9, until=date(2026, 10, 9)),
            (datetime(2026, 8, 31, 22, 0), datetime(2026, 10, 8, 22, 0)),
        )


class TestRounding(unittest.TestCase):
    def test_halves_round_up(self):
        self.assertEqual(round1(6.25), 6.3)
        self.assertEqual(round1(7.75), 7.8)
        self.assertEqual(round1(7.666), 7.7)


class TestTiers(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(tier_for(0), "aucun")
        self.assertEqual(tier_for(1), "leger")
        self.assertEqual(tier_for(5), "leger")
        self.assertEqual(tier_for(6), "complet")


class TestComputeFacts(unittest.TestCase):
    def test_empty_month(self):
        facts = compute_facts(2026, 9, [], [row("A", "Bob", 8)])
        self.assertEqual(facts.tier, "aucun")
        self.assertEqual(facts.count, 0)
        self.assertIsNone(facts.average)
        self.assertEqual(facts.best, [])
        self.assertEqual(facts.previous_count, 1)

    def test_counts_average_and_ranking(self):
        rows = [row("A", "Bob", 8), row("B", "Bob", 6), row("A", "Alice", 9)]
        facts = compute_facts(2026, 9, rows, [])
        self.assertEqual(facts.count, 3)
        self.assertEqual(facts.average, 7.7)
        self.assertEqual(facts.ranking, [("Bob", 2), ("Alice", 1)])
        self.assertEqual(facts.films, {"A", "B"})
        self.assertEqual(facts.people, {"Bob", "Alice"})

    def test_best_and_worst_use_film_averages_and_never_overlap(self):
        rows = [row(f, "Bob", s) for f, s in [("A", 9), ("B", 8), ("C", 7), ("D", 4)]]
        facts = compute_facts(2026, 9, rows, [])
        self.assertEqual([s.film for s in facts.best], ["A", "B", "C"])
        self.assertEqual([s.film for s in facts.worst], ["D"])

    def test_ties_are_broken_by_title(self):
        rows = [row("Zorro", "Bob", 8), row("Amélie", "Bob", 8)]
        facts = compute_facts(2026, 9, rows, [])
        self.assertEqual([s.film for s in facts.best], ["Amélie", "Zorro"])

    def test_favourite_genre_splits_multi_genre_strings(self):
        rows = [row("A", "Bob", 8, "Comedy, Romance"), row("B", "Bob", 7, "Comedy"), row("C", "Bob", 7, "Drama")]
        self.assertEqual(compute_facts(2026, 9, rows, []).favourite_genre, "Comedy")

    def test_no_genres(self):
        self.assertIsNone(compute_facts(2026, 9, [row("A", "Bob", 8, None)], []).favourite_genre)

    def test_absent_lists_family_members_without_ratings_in_family_order(self):
        rows = [row("A", "Bob", 8)]
        facts = compute_facts(2026, 9, rows, [], family=["Alice", "Bob", "Chloé"])
        self.assertEqual(facts.absent, ["Alice", "Chloé"])

    def test_until_is_kept_on_the_facts(self):
        self.assertEqual(compute_facts(2026, 9, [], [], until=date(2026, 10, 9)).until, date(2026, 10, 9))


if __name__ == "__main__":
    unittest.main()

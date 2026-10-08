import unittest
from datetime import date

from summary.facts import RatingRow, compute_facts
from summary.render import (
    MONTH_ABBR, assemble, fallback_colour, period_label, render_facts, subject, title,
)


def row(film, who, score, genres="Comedy"):
    return RatingRow(film=film, year="2020", genres=genres, who=who, score=score, comment=None)


class TestLabels(unittest.TestCase):
    def test_subject(self):
        self.assertEqual(subject(2026, 9), "Résumé Perrin-rama: Sept'26")
        self.assertEqual(subject(2027, 1), "Résumé Perrin-rama: Janv'27")

    def test_subject_for_extended_period(self):
        self.assertEqual(subject(2026, 9, until=date(2026, 10, 9)), "Résumé Perrin-rama: Sept-Oct'26")

    def test_twelve_abbreviations(self):
        self.assertEqual(
            MONTH_ABBR,
            ["Janv", "Févr", "Mars", "Avr", "Mai", "Juin", "Juil", "Août", "Sept", "Oct", "Nov", "Déc"],
        )

    def test_period_label(self):
        self.assertEqual(period_label(2026, 8), "août 2026")
        self.assertEqual(period_label(2026, 9, until=date(2026, 10, 9)), "septembre et début octobre 2026")
        self.assertEqual(period_label(2026, 12, until=date(2027, 1, 5)), "décembre 2026 et début janvier 2027")

    def test_until_on_the_next_first_is_just_the_month(self):
        self.assertEqual(period_label(2026, 9, until=date(2026, 10, 1)), "septembre 2026")


class TestRenderFacts(unittest.TestCase):
    def test_empty_month_has_no_bullets(self):
        self.assertEqual(render_facts(compute_facts(2026, 9, [], [])), "")

    def test_light_month_lists_each_rating(self):
        text = render_facts(compute_facts(2026, 9, [row("Le Daim", "Chloé", 8.5)], []))
        self.assertIn("1 note", text)
        self.assertIn("«Le Daim» — Chloé 8,5", text)

    def test_full_month(self):
        rows = [row(f"Film {c}", who, s) for c, who, s in [
            ("A", "Bob", 9), ("B", "Bob", 8), ("C", "Alice", 7.5),
            ("D", "Alice", 6), ("E", "Chloé", 4), ("F", "Bob", 3),
        ]]
        text = render_facts(compute_facts(2026, 9, rows, []))
        self.assertIn("6 notes · moyenne 6,3/10", text)
        self.assertIn("Bob (3)", text)
        self.assertIn("🥇 «Film A» — 9,0", text)
        self.assertIn("«Film F» — 3,0", text)
        self.assertIn("Comédie", text)  # genres are translated


class TestFallbackAndAssemble(unittest.TestCase):
    def test_fallback_exists_for_every_tier(self):
        for tier in ("aucun", "leger", "complet"):
            self.assertIn("septembre 2026", fallback_colour(tier, "septembre 2026"))

    def test_assemble_skips_empty_parts(self):
        self.assertEqual(assemble("*T*", "Salut 🎬", ""), "*T*\n\nSalut 🎬")
        self.assertEqual(assemble("*T*", "Salut", "• x"), "*T*\n\nSalut\n\n• x")

    def test_title_names_the_period_in_whatsapp_bold(self):
        self.assertEqual(title(2026, 11), "*Résumé Perrin-rama — novembre 2026*")
        self.assertEqual(title(2026, 9, date(2026, 10, 9)),
                         "*Résumé Perrin-rama — septembre et début octobre 2026*")


if __name__ == "__main__":
    unittest.main()

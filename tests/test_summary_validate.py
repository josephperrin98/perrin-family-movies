import unittest
from dataclasses import dataclass, field

from summary.facts import RatingRow, compute_facts
from summary.validate import quoted_titles, validate


@dataclass
class FakeColour:
    message: str
    titles_mentioned: list = field(default_factory=list)
    names_mentioned: list = field(default_factory=list)


def light_month():
    rows = [RatingRow("Blade Runner 2049", "2017", "Sci-Fi", "Chloé", 8.5, "Trop long"),
            RatingRow("Le Daim", "2019", "Comedy", "Bob", 6.0, None)]
    return compute_facts(2026, 9, rows, [])


GOOD = ("Ce mois-ci, Chloé a plongé dans «Blade Runner 2049» pendant que Bob "
        "se battait avec «Le Daim» et son blouson 🧥. Spoiler : personne n'a compris "
        "la fin. Qui ose le revoir avec lui ?")


class TestQuotedTitles(unittest.TestCase):
    def test_extracts_titles_and_trims_spaces(self):
        self.assertEqual(quoted_titles("Vu « Le Daim » et «Tenet»"), ["Le Daim", "Tenet"])


class TestValidate(unittest.TestCase):
    def check(self, message, titles=None, names=None, facts=None, previous=()):
        colour = FakeColour(message, titles if titles is not None else quoted_titles(message), names or [])
        return validate(colour, facts or light_month(), list(previous))

    def test_good_message_passes(self):
        self.assertEqual(self.check(GOOD, names=["Chloé", "Bob"]), [])

    def test_unknown_title_fails(self):
        errors = self.check(GOOD.replace("«Le Daim»", "«Le Cerf»"))
        self.assertTrue(any("Le Cerf" in e for e in errors))

    def test_titles_compared_case_insensitively(self):
        self.assertEqual(self.check(GOOD.replace("«Le Daim»", "«le daim»")), [])

    def test_unknown_name_fails(self):
        errors = self.check(GOOD, names=["Chloé", "Mamie"])
        self.assertTrue(any("Mamie" in e for e in errors))

    def test_self_declared_titles_must_match_text(self):
        errors = self.check(GOOD, titles=["Blade Runner 2049"])
        self.assertTrue(any("titles_mentioned" in e for e in errors))

    def test_digits_inside_titles_are_allowed_but_not_outside(self):
        errors = self.check(GOOD.replace("Ce mois-ci", "Avec 2 films"))
        self.assertTrue(any("chiffre" in e for e in errors))

    def test_length_range(self):
        errors = self.check("Trop court 🎬 ?")
        self.assertTrue(any("Longueur" in e for e in errors))

    def test_needs_emoji_and_question(self):
        errors = self.check(GOOD.replace("🧥", "").replace("?", "."))
        self.assertTrue(any("emoji" in e for e in errors))
        self.assertTrue(any("question" in e for e in errors))

    def test_near_copy_of_previous_summary_fails(self):
        errors = self.check(GOOD, previous=[GOOD.replace("Bob", "Bobby")])
        self.assertTrue(any("précédent" in e for e in errors))

    def test_different_previous_summary_passes(self):
        other = "Rien à voir : un mois de comédies musicales et de pop-corn brûlé 🍿, qui chante ?"
        self.assertEqual(self.check(GOOD, previous=[other]), [])

    def test_empty_month_must_not_quote_titles(self):
        empty = compute_facts(2026, 9, [], [])
        message = "Septembre sans film ? La télé a fait grève 📺 ! Racontez-nous ce que vous avez regardé, même «Tenet»."
        errors = self.check(message, facts=empty)
        self.assertTrue(any("Tenet" in e for e in errors))

    def test_family_member_without_ratings_must_not_be_named(self):
        # Checked in the text itself, even if the model leaves the name out of names_mentioned
        facts = compute_facts(2026, 9, light_month().rows, [], family=["Chloé", "Bob", "Mamie"])
        message = GOOD.replace("Qui ose le revoir avec lui ?", "Et Mamie, qui ose le revoir ?")
        errors = self.check(message, names=["Chloé", "Bob"], facts=facts)
        self.assertTrue(any("Mamie" in e for e in errors))

    def test_at_most_two_people_are_named(self):
        rows = light_month().rows + [RatingRow("Le Daim", "2019", "Comedy", "Alice", 7.0, None)]
        facts = compute_facts(2026, 9, rows, [])
        message = GOOD.replace("Qui ose", "Alice, qui ose")
        errors = self.check(message, names=["Chloé", "Bob", "Alice"], facts=facts)
        self.assertTrue(any("personnes" in e for e in errors))

    def test_big_month_is_capped_at_six_hundred_characters(self):
        rows = [RatingRow(f"Film {i}", "2020", "Drama", "Bob", 7.0, None) for i in range(6)]
        facts = compute_facts(2026, 9, rows, [])
        message = "Un mois chargé 🎬 " + "bla " * 150 + "?"
        self.assertTrue(any("Longueur" in e for e in self.check(message, facts=facts)))

    def test_family_classics_may_be_quoted_any_month(self):
        empty = compute_facts(2026, 9, [], [])
        message = ("Pas un film noté ce mois-ci 📺 Comme dirait «OSS 117», ça ne serait pas "
                   "une bonne situation, ça. Qui se lance en premier ?")
        self.assertEqual(self.check(message, facts=empty), [])


if __name__ == "__main__":
    unittest.main()

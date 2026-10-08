import unittest

from summary.titles import (
    choose_display_title,
    is_latin,
    parse_tmdb_find,
    resolve_display_title,
)


class TestIsLatin(unittest.TestCase):
    def test_english(self):
        self.assertTrue(is_latin("Inception"))

    def test_french_accents(self):
        self.assertTrue(is_latin("Le Fabuleux Destin d'Amélie Poulain"))

    def test_digits_and_punctuation_are_ignored(self):
        self.assertTrue(is_latin("Blade Runner 2049"))
        self.assertTrue(is_latin("2001: A Space Odyssey"))

    def test_japanese(self):
        self.assertFalse(is_latin("千と千尋の神隠し"))

    def test_korean(self):
        self.assertFalse(is_latin("기생충"))

    def test_cyrillic(self):
        self.assertFalse(is_latin("Сталкер"))


class TestChooseDisplayTitle(unittest.TestCase):
    def test_latin_original_is_kept(self):
        self.assertEqual(
            choose_display_title("Le Fabuleux Destin d'Amélie Poulain", "Le Fabuleux Destin d'Amélie Poulain"),
            "Le Fabuleux Destin d'Amélie Poulain",
        )

    def test_english_original_is_kept_over_french(self):
        self.assertEqual(choose_display_title("The Shining", "Shining"), "The Shining")

    def test_non_latin_original_uses_french(self):
        self.assertEqual(choose_display_title("千と千尋の神隠し", "Le Voyage de Chihiro"), "Le Voyage de Chihiro")

    def test_non_latin_without_french_falls_back_to_original(self):
        self.assertEqual(choose_display_title("기생충", None), "기생충")
        self.assertEqual(choose_display_title("기생충", ""), "기생충")


class TestParseTmdbFind(unittest.TestCase):
    def test_returns_original_and_french_titles(self):
        data = {"movie_results": [{"original_title": "기생충", "title": "Parasite", "original_language": "ko"}]}
        self.assertEqual(parse_tmdb_find(data), ("기생충", "Parasite"))

    def test_no_movie_results(self):
        self.assertIsNone(parse_tmdb_find({"movie_results": []}))
        self.assertIsNone(parse_tmdb_find({}))

    def test_missing_original_title(self):
        self.assertIsNone(parse_tmdb_find({"movie_results": [{"title": "Parasite"}]}))


class TestResolveDisplayTitle(unittest.TestCase):
    def test_manual_movie_keeps_typed_title_without_lookup(self):
        def fetch(imdb_id):
            raise AssertionError("manual movies must not call TMDB")

        self.assertEqual(resolve_display_title("manual_les-bronzes", "Les Bronzés", fetch), "Les Bronzés")

    def test_found_on_tmdb(self):
        def fetch(imdb_id):
            return ("千と千尋の神隠し", "Le Voyage de Chihiro")

        self.assertEqual(resolve_display_title("tt0245429", "Spirited Away", fetch), "Le Voyage de Chihiro")

    def test_not_found_returns_none(self):
        self.assertIsNone(resolve_display_title("tt0000000", "Unknown", lambda imdb_id: None))


if __name__ == "__main__":
    unittest.main()

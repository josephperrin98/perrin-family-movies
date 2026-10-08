import unittest
from unittest import mock

import requests

from summary.titles import (
    TmdbAuthError,
    choose_display_title,
    fetch_tmdb_titles,
    parse_tmdb_find,
    resolve_display_title,
)


class TestChooseDisplayTitle(unittest.TestCase):
    def test_french_keeps_original(self):
        self.assertEqual(choose_display_title("Le Daim", "fr", "Deerskin"), "Le Daim")

    def test_italian_and_spanish_keep_original(self):
        self.assertEqual(choose_display_title("La grande bellezza", "it", "The Great Beauty"), "La grande bellezza")
        self.assertEqual(choose_display_title("Amores perros", "es", "Amores Perros"), "Amores perros")

    def test_english_keeps_original(self):
        self.assertEqual(choose_display_title("GoodFellas", "en", "Goodfellas"), "GoodFellas")

    def test_non_latin_original_uses_english_even_if_language_matches(self):
        # TMDB lists It Must Be Heaven as French, but its original title is Arabic
        self.assertEqual(
            choose_display_title("إن شئت كما في السماء", "fr", "It Must Be Heaven"), "It Must Be Heaven"
        )

    def test_digits_and_accents_count_as_latin(self):
        self.assertEqual(choose_display_title("Blade Runner 2049", "en", "Blade Runner 2049"), "Blade Runner 2049")
        self.assertEqual(choose_display_title("Les Choses de la vie", "fr", "The Things of Life"), "Les Choses de la vie")

    def test_other_languages_use_english_title(self):
        self.assertEqual(choose_display_title("Das Leben der Anderen", "de", "The Lives of Others"), "The Lives of Others")
        self.assertEqual(choose_display_title("Affeksjonsverdi", "no", "Sentimental Value"), "Sentimental Value")
        self.assertEqual(choose_display_title("기생충", "ko", "Parasite"), "Parasite")


class TestParseTmdbFind(unittest.TestCase):
    def test_movie(self):
        data = {"movie_results": [{"original_title": "기생충", "original_language": "ko", "title": "Parasite"}]}
        self.assertEqual(parse_tmdb_find(data), ("기생충", "ko"))

    def test_tv_series_are_found_too(self):
        data = {"movie_results": [], "tv_results": [{"original_name": "Fleabag", "original_language": "en"}]}
        self.assertEqual(parse_tmdb_find(data), ("Fleabag", "en"))

    def test_no_results(self):
        self.assertIsNone(parse_tmdb_find({"movie_results": [], "tv_results": []}))
        self.assertIsNone(parse_tmdb_find({}))

    def test_incomplete_result(self):
        self.assertIsNone(parse_tmdb_find({"movie_results": [{"original_title": "기생충"}]}))


class TestFetchTmdbTitles(unittest.TestCase):
    def _response(self, status, body=None):
        response = mock.Mock(status_code=status)
        response.json.return_value = body or {}
        return response

    def test_rejected_token_raises_instead_of_looking_like_not_found(self):
        with mock.patch("summary.titles.requests.get", return_value=self._response(401)):
            with self.assertRaises(TmdbAuthError):
                fetch_tmdb_titles("tt0211915", "bad-token")

    def test_found(self):
        body = {"movie_results": [{"original_title": "기생충", "original_language": "ko"}]}
        with mock.patch("summary.titles.requests.get", return_value=self._response(200, body)):
            self.assertEqual(fetch_tmdb_titles("tt6751668", "token"), ("기생충", "ko"))

    def test_network_error_is_not_found_for_now(self):
        with mock.patch("summary.titles.requests.get", side_effect=requests.ConnectionError):
            self.assertIsNone(fetch_tmdb_titles("tt6751668", "token"))


class TestResolveDisplayTitle(unittest.TestCase):
    def _no_lookup(self, imdb_id):
        raise AssertionError("placeholder IDs must not call TMDB")

    def test_manual_placeholder_keeps_typed_title(self):
        self.assertEqual(resolve_display_title("manual_les-bronzes", "Les Bronzés", self._no_lookup), "Les Bronzés")

    def test_csv_import_placeholder_keeps_typed_title(self):
        self.assertEqual(resolve_display_title("csv_tapie_2023", "Tapie", self._no_lookup), "Tapie")

    def test_found_on_tmdb(self):
        fetch = lambda imdb_id: ("La grande bellezza", "it")
        self.assertEqual(resolve_display_title("tt2358891", "The Great Beauty", fetch), "La grande bellezza")

    def test_not_found_returns_none(self):
        self.assertIsNone(resolve_display_title("tt0000000", "Unknown", lambda imdb_id: None))


if __name__ == "__main__":
    unittest.main()

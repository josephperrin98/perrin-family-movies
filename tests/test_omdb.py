import os
import unittest
from unittest import mock

import requests

os.environ.setdefault("OMDB_API_KEY", "secret-key")

import omdb


def http_error(status):
    response = requests.Response()
    response.status_code = status
    response.url = "https://www.omdbapi.com/?apikey=secret-key&s=x"
    return requests.HTTPError(f"{status} Client Error for url: {response.url}", response=response)


class TestErrorsHideTheKey(unittest.TestCase):
    # The API key travels in the URL, and requests puts the URL in its errors
    def test_search_error_does_not_show_the_key(self):
        with mock.patch("omdb.requests.get") as get:
            get.return_value.raise_for_status.side_effect = http_error(401)
            error = omdb.search_movies("Le Prénom")["error"]
        self.assertNotIn("secret-key", error)
        self.assertIn("OMDB_API_KEY", error)  # 401 means a bad key: say which setting

    def test_details_error_does_not_show_the_key(self):
        with mock.patch("omdb.requests.get") as get:
            get.return_value.raise_for_status.side_effect = http_error(503)
            error = omdb.get_movie_details("tt1")["error"]
        self.assertNotIn("secret-key", error)
        self.assertIn("503", error)

    def test_network_error_does_not_show_the_key(self):
        with mock.patch("omdb.requests.get",
                        side_effect=requests.ConnectionError("failed: apikey=secret-key")):
            error = omdb.search_movies("x")["error"]
        self.assertNotIn("secret-key", error)


if __name__ == "__main__":
    unittest.main()

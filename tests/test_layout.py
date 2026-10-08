import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestLayout(unittest.TestCase):
    def test_no_streamlit_pages_folder(self):
        # Streamlit turns a top-level pages/ folder into extra pages: a sidebar
        # menu and URLs that skip film_app.py's routing and family PIN. Screens
        # live in views/ and are called by film_app.py instead.
        self.assertFalse((ROOT / "pages").exists())


if __name__ == "__main__":
    unittest.main()

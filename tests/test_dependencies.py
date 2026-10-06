"""
Regression test: the installed Postgres driver must match what SQLAlchemy expects.

SQLAlchemy 2.1 changed its default driver for postgresql:// URLs from psycopg2
to psycopg (v3), which silently broke the app and the weekly backup.
create_engine() imports the driver without opening a connection, so this
catches the mismatch with no network and no real database.
"""

import unittest

from sqlalchemy import create_engine


class TestPostgresDriver(unittest.TestCase):
    def test_default_postgres_driver_is_installed(self):
        engine = create_engine("postgresql://user:pass@localhost/db")
        self.assertEqual(engine.dialect.driver, "psycopg")


if __name__ == "__main__":
    unittest.main()

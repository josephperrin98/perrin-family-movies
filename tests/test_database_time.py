import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import database


class TestUtcNow(unittest.TestCase):
    # Timestamps are stored without a time zone and read as UTC (summary/facts.py),
    # so they must not depend on the clock of the machine running the app
    def test_naive_utc(self):
        now = database.utc_now()
        self.assertIsNone(now.tzinfo)
        utc = datetime.now(timezone.utc).replace(tzinfo=None)
        self.assertLess(abs(now - utc), timedelta(seconds=5))


if __name__ == "__main__":
    unittest.main()

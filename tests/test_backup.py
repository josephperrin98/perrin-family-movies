import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")
sys.path.insert(0, str(ROOT / "scripts"))

import backup_database  # noqa: E402


class TestBackupCoversEveryTable(unittest.TestCase):
    def test_every_table_in_the_schema_is_backed_up(self):
        schema = (ROOT / "database.py").read_text()
        tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", schema))
        backed_up = {name.removesuffix(".csv") for name in backup_database.BACKUP_QUERIES}
        self.assertEqual(backed_up, tables)


if __name__ == "__main__":
    unittest.main()

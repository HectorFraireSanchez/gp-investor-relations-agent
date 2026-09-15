"""Deterministic investor enumeration and literal name lookup."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend import create_database, domain


class InvestorTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.database = Path(temporary) / "investors.db"
        with closing(sqlite3.connect(self.database)) as connection:
            connection.executescript(create_database.SCHEMA_AND_DATA)
        self.enterContext(patch.object(domain, "DB_PATH", self.database))

    def test_lists_all_seeded_records_in_name_order(self):
        expected = [
            {"investor_id": "INV-003", "name": "Atlas Pension Fund", "investor_type": "Pension Fund"},
            {"investor_id": "INV-002", "name": "Beacon University Endowment", "investor_type": "Endowment"},
            {"investor_id": "INV-001", "name": "Redwood Family Office", "investor_type": "Family Office"},
        ]
        self.assertEqual(domain.list_investors(), expected)
        self.assertEqual(domain.list_investors(), expected)

    def test_enumeration_tracks_database_contents_and_handles_empty_table(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO investors VALUES (?, ?, ?)", ("INV-004", "Aardvark Test", "Test"))
            connection.commit()
        self.assertEqual(len(domain.list_investors()), 4)
        self.assertEqual(domain.list_investors()[0]["investor_id"], "INV-004")
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("DELETE FROM investors")
            connection.commit()
        self.assertEqual(domain.list_investors(), [])

    def test_find_still_returns_one_record_or_none(self):
        self.assertEqual(domain.find_investor("Beacon"), {
            "investor_id": "INV-002", "name": "Beacon University Endowment", "investor_type": "Endowment",
        })
        self.assertIsNone(domain.find_investor("No such investor"))

    def test_blank_names_do_not_select_an_arbitrary_investor(self):
        for name in ("", " \n "):
            with self.subTest(name=name):
                self.assertIsNone(domain.find_investor(name))

    def test_name_search_is_literal_case_insensitive_and_trims_whitespace(self):
        self.assertEqual(domain.find_investor("  rEdWoOd  ")["investor_id"], "INV-001")
        for name in ("%", "_", "Red%", "Redwood' OR 1=1 --"):
            with self.subTest(name=name):
                self.assertIsNone(domain.find_investor(name))
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO investors VALUES (?, ?, ?)",
                               ("INV-004", "100% Fund_Name", "Test"))
            connection.commit()
        self.assertEqual(domain.find_investor("% Fund_")["investor_id"], "INV-004")

"""Document-tool input validation and investor scoping without API requests."""

import importlib
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch


class DocumentToolTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "offline-test", "OPENAI_VECTOR_STORE_ID": "offline-test",
        }):
            self.server = importlib.import_module("backend.mcp_server")
        self.client = self.enterContext(patch.object(self.server, "openai_client"))

    def test_blank_investor_is_rejected_before_search(self):
        for name in ("", " \n "):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "must not be blank"):
                self.server.search_investor_documents(name, "reporting")
        self.client.vector_stores.search.assert_not_called()

    def test_returns_only_matching_documents_with_actual_provenance(self):
        self.client.vector_stores.search.return_value.data = [
            SimpleNamespace(filename=filename, file_id=f"file-{index}", score=0.9,
                            content=[SimpleNamespace(text="Retrieved passage")])
            for index, filename in enumerate([
                "beacon_side_letter.md", "redwood_side_letter.md",
                "redwood_meeting_notes_2026_08_14.md",
            ])
        ]
        results = self.server.search_investor_documents(" Redwood Family Office ", "reporting")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["data"]["text"], "Retrieved passage")
        self.assertEqual(results[0]["sources"], [{
            "source_id": "doc:redwood_side_letter.md", "source_type": "document",
            "filename": "redwood_side_letter.md", "file_id": "file-1",
        }])
        self.assertEqual(self.client.vector_stores.search.call_args.kwargs["query"],
                         "Redwood Family Office: reporting")

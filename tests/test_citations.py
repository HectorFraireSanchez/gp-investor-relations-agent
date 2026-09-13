import copy
import json
import unittest
from dataclasses import asdict

from citations import render_citations
from mcp_agent import AgentResponse


class CitationRenderingTests(unittest.TestCase):
    def setUp(self):
        self.database = {
            "source_id": "db:positions:INV-001:Fund II",
            "source_type": "database",
            "database": "northstar.db",
            "schema": "main",
            "table": "positions",
            "record_key": {"investor_id": "INV-001", "fund": "Fund II"},
        }
        self.document = {
            "source_id": "doc:side_letter.md",
            "source_type": "document",
            "filename": "side_letter.md",
            "file_id": "file-example",
        }

    def marker(self, source):
        return "[[cite:" + source["source_id"] + "]]"

    def response(self, answer, sources=None, invalid=None):
        return AgentResponse(
            answer,
            sources if sources is not None else [self.database, self.document],
            [],
            invalid_source_ids=invalid or [],
        )

    def test_first_appearance_overrides_retrieval_order(self):
        raw = self.response(f"Document. {self.marker(self.document)} Position. {self.marker(self.database)}")
        rendered = render_citations(raw)
        self.assertEqual(rendered.answer, "Document. [1] Position. [2]")
        self.assertEqual([c['source'] for c in rendered.citations], [self.document, self.database])

    def test_repeated_source_reuses_number(self):
        raw = self.response(f"A. {self.marker(self.database)} B. {self.marker(self.document)} A. {self.marker(self.database)}")
        rendered = render_citations(raw)
        self.assertEqual(rendered.answer, "A. [1] B. [2] A. [1]")
        self.assertEqual(len(rendered.citations), 2)

    def test_adjacent_duplicate_markers(self):
        rendered = render_citations(self.response(self.marker(self.database) * 2 + self.marker(self.document)))
        self.assertEqual(rendered.answer, "[1][1][2]")
        self.assertEqual([c['number'] for c in rendered.citations], [1, 2])

    def test_uncited_source_is_not_displayed(self):
        rendered = render_citations(self.response(self.marker(self.document)))
        self.assertEqual(rendered.citations, [{"number": 1, "source_id": self.document['source_id'], "source": self.document}])

    def test_invalid_citation_never_takes_a_number(self):
        invalid = "db:capital_calls:CC-999"
        raw = self.response(f"Bad. [[cite:{invalid}]] Good. {self.marker(self.database)} [[cite:{invalid}]]", invalid=[invalid])
        rendered = render_citations(raw)
        self.assertEqual(rendered.answer, "Bad. [citation unavailable] Good. [1] [citation unavailable]")
        self.assertEqual(rendered.invalid_source_ids, [invalid])
        self.assertEqual(len(rendered.citations), 1)

    def test_missing_validation_state_does_not_grant_trust(self):
        rendered = render_citations(self.response("[[cite:invented]]"))
        self.assertEqual(rendered.answer, "[citation unavailable]")
        self.assertEqual(rendered.invalid_source_ids, ["invented"])
        self.assertEqual(rendered.citations, [])

    def test_flagged_invalid_id_is_not_rendered_as_trusted(self):
        rendered = render_citations(self.response(self.marker(self.database), invalid=[self.database['source_id']]))
        self.assertEqual(rendered.answer, "[citation unavailable]")
        self.assertEqual(rendered.citations, [])

    def test_exact_ids_are_not_normalized(self):
        for altered in (self.database['source_id'].upper(), self.database['source_id'] + ' '):
            with self.subTest(altered=altered):
                rendered = render_citations(self.response(f"[[cite:{altered}]]"))
                self.assertEqual(rendered.invalid_source_ids, [altered])
                self.assertEqual(rendered.citations, [])

    def test_no_citations_preserves_plain_text(self):
        rendered = render_citations(self.response("Plain text.\nAnother paragraph."))
        self.assertEqual(rendered.answer, "Plain text.\nAnother paragraph.")
        self.assertEqual(rendered.citations, [])

    def test_no_sources(self):
        rendered = render_citations(self.response(self.marker(self.database), sources=[]))
        self.assertEqual(rendered.answer, "[citation unavailable]")
        self.assertEqual(rendered.citations, [])
        self.assertEqual(rendered.invalid_source_ids, [self.database['source_id']])
        self.assertEqual(render_citations(self.response("No records.", sources=[])).answer, "No records.")

    def test_preserves_metadata_and_does_not_mutate_input(self):
        raw = self.response(self.marker(self.database))
        before = copy.deepcopy(raw)
        rendered = render_citations(raw)
        self.assertEqual(raw, before)
        self.assertEqual(rendered.citations[0]['source'], self.database)
        rendered.citations[0]['source']['record_key']['fund'] = 'changed by caller'
        self.assertEqual(raw, before)

    def test_json_serialization_and_numbering_reset(self):
        first = render_citations(self.response(self.marker(self.database)))
        second = render_citations(self.response(self.marker(self.document)))
        self.assertEqual(second.answer, '[1]')
        payload = json.loads(json.dumps(asdict(first)))
        self.assertEqual(set(payload), {'answer', 'citations', 'invalid_source_ids'})
        self.assertEqual(payload['citations'][0]['source'], self.database)


if __name__ == "__main__":
    unittest.main()

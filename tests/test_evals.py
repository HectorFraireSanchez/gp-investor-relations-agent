"""Source assertions use run metadata and participate in trial summaries."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.mcp_agent import AgentResponse
from evals import run_evals


SOURCE_ID = "db:investors:INV-001"


class SourceEvalTests(unittest.IsolatedAsyncioTestCase):
    async def evaluate(self, case, response):
        with patch.object(run_evals, "run_agent", AsyncMock(return_value=response)), redirect_stdout(io.StringIO()):
            return await run_evals.evaluate_case({"id": "test", "prompt": "Question", **case})

    async def test_sources_are_exact_registry_membership_not_answer_text(self):
        response = AgentResponse(f"Claim [[cite:{SOURCE_ID}]]", [], [], cited_source_ids=[SOURCE_ID])
        result = await self.evaluate({"required_source_ids": [SOURCE_ID], "required_citation_ids": [SOURCE_ID]}, response)
        self.assertFalse(result["passed"])
        self.assertTrue(all(not check["passed"] for check in result["checks"]))
        response.sources = [{"source_id": SOURCE_ID}]
        result = await self.evaluate({"required_source_ids": [SOURCE_ID, SOURCE_ID.lower()], "required_citation_ids": [SOURCE_ID]}, response)
        self.assertEqual([check["passed"] for check in result["checks"]], [True, False, True])
        self.assertEqual(result["source_ids"], [SOURCE_ID])
        self.assertEqual(result["cited_source_ids"], [SOURCE_ID])

    async def test_retrieval_alone_does_not_satisfy_required_citation(self):
        response = AgentResponse("Answer", [{"source_id": SOURCE_ID}], [])
        result = await self.evaluate({"required_source_ids": [SOURCE_ID], "required_citation_ids": [SOURCE_ID]}, response)
        self.assertEqual([check["passed"] for check in result["checks"]], [True, False])

    async def test_trial_failure_continuation_counts_and_saved_results(self):
        case = {"id": "trial_test", "prompt": "Question", "must_contain": ["Answer"],
                "must_contain_amounts": [5000000], "forbidden_tools": ["get_positions"],
                "required_source_ids": [SOURCE_ID], "required_citation_ids": [SOURCE_ID]}
        response = AgentResponse("Answer $5M", [{"source_id": SOURCE_ID}], [], cited_source_ids=[SOURCE_ID])
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "cases.json").write_text(json.dumps([case]), encoding="utf-8")
            with patch.object(run_evals, "EVALS_DIR", directory), \
                    patch.object(run_evals, "RESULTS_DIR", directory / "results"), \
                    patch.object(run_evals, "TRIALS_PER_CASE", 2), \
                    patch.object(run_evals, "run_agent", AsyncMock(side_effect=[RuntimeError("failed run"), response])) as agent, \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(await run_evals.main(), 1)
            self.assertEqual(agent.await_count, 2)
            files = list((directory / "results").glob("*.json"))
            self.assertEqual(len(files), 1)
            report = json.loads(files[0].read_text())
        self.assertEqual(report["summary"], {
            "passed": 5, "failed": 5, "total": 10, "passed_trials": 1,
            "failed_trials": 1, "total_trials": 2, "trial_pass_rate": 0.5,
        })
        case_result = report["cases"][0]
        self.assertEqual(case_result["summary"]["pass_rate"], 0.5)
        self.assertEqual(case_result["trials"][0]["error"], "RuntimeError: failed run")
        self.assertTrue(all(not check["passed"] for check in case_result["trials"][0]["checks"]))
        self.assertEqual(case_result["trials"][1]["source_ids"], [SOURCE_ID])
        self.assertEqual(case_result["trials"][1]["cited_source_ids"], [SOURCE_ID])

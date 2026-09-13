import asyncio
import os
import sys
import unittest
from dataclasses import asdict
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import api
from backend.citations import RenderedResponse


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.setup = self.enterContext(patch.object(api, "ensure_vector_store"))
        self.generate = self.enterContext(patch.object(api, "generate_briefing", AsyncMock()))
        self.client = self.enterContext(TestClient(api.app))

    def test_health_does_not_call_agent_or_document_setup(self):
        self.setup.reset_mock()
        response = self.client.get("/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")
        self.setup.assert_not_called()
        self.generate.assert_not_awaited()

    def test_cors_origins_can_be_configured_without_a_wildcard(self):
        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": " http://localhost:5173, https://frontend.example.test, "}):
            self.assertEqual(api.get_cors_origins(), ["http://localhost:5173", "https://frontend.example.test"])
        with patch.dict(os.environ, {"CORS_ALLOW_ORIGINS": ""}):
            self.assertEqual(api.get_cors_origins(), [])

    def test_validation_never_calls_service(self):
        for body in ({}, {"prompt": ""}, {"prompt": " \n "}, {"prompt": 42},
                     {"prompt": None}, {"prompt": "x" * 10001},
                     {"prompt": "hello", "unknown": True}):
            with self.subTest(body=str(body)[:80]):
                self.assertEqual(self.client.post("/api/briefings", json=body).status_code, 422)
        self.generate.assert_not_awaited()

    def test_serializes_full_response_and_initializes_only_once(self):
        source = {"source_id": "db:investors:INV-001", "source_type": "database",
                  "database": "northstar.db", "table": "investors",
                  "record_key": {"investor_id": "INV-001"}, "extra": {"kept": True}}
        result = RenderedResponse("Investor. [1] Again. [1] [citation unavailable]",
                                  [{"number": 1, "source_id": source["source_id"], "source": source}],
                                  ["unknown"])
        self.generate.return_value = result
        for _ in range(2):
            response = self.client.post("/api/briefings", json={"prompt": " Prepare Redwood "})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), asdict(result))
        self.generate.assert_awaited_with(" Prepare Redwood ")
        self.setup.assert_called_once()

    def test_errors_do_not_disclose_internal_details(self):
        self.generate.side_effect = RuntimeError("private upstream details")
        with self.assertLogs("backend.api", level="ERROR"):
            response = self.client.post("/api/briefings", json={"prompt": "Prepare Redwood"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private", response.text)
        self.generate.side_effect = None
        self.generate.return_value = RenderedResponse("Next request works", [], [])
        self.assertEqual(self.client.post("/api/briefings", json={"prompt": "Again"}).status_code, 200)

    def test_local_cors_is_restricted(self):
        for origin, allowed in (("http://localhost:5173", True),
                                ("http://127.0.0.1:5173", True),
                                ("https://example.com", False)):
            response = self.client.options("/api/briefings", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            })
            self.assertEqual(response.headers.get("access-control-allow-origin"), origin if allowed else None)


class StartupTests(unittest.TestCase):
    def test_web_loop_supports_subprocesses_required_by_mcp(self):
        async def spawn():
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "print('ready')", stdout=asyncio.subprocess.PIPE,
            )
            output, _ = await process.communicate()
            self.assertEqual(process.returncode, 0)
            self.assertEqual(output.strip(), b"ready")

        loop = api.create_event_loop()
        try:
            loop.run_until_complete(spawn())
        finally:
            loop.close()

    def test_failed_setup_prevents_startup(self):
        with patch.object(api, "ensure_vector_store", side_effect=RuntimeError("setup failed")):
            with self.assertRaisesRegex(RuntimeError, "setup failed"):
                with TestClient(api.app):
                    self.fail("Startup should not succeed")

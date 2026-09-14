"""Worker-owned MCP lifecycle and request isolation, without external API calls."""

import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from agents import Model, RunConfig, Runner
from agents.items import ModelResponse
from agents.usage import Usage
from fastapi.testclient import TestClient
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from backend import api, mcp_agent
from backend.service import BriefingResult


class LifespanTests(unittest.TestCase):
    def test_opens_once_per_worker_and_closes_in_the_owning_task(self):
        tasks = []
        servers = []

        class Server:
            def __init__(self):
                self.list_tools = AsyncMock(return_value=[])
                self.closed = False

            async def __aenter__(self):
                tasks.append(asyncio.current_task())
                return self

            async def __aexit__(self, *args):
                tasks.append(asyncio.current_task())
                self.closed = True

        def construct():
            server = Server()
            servers.append(server)
            return server

        with patch.object(api, "ensure_vector_store"), \
                patch.object(api, "create_mcp_server", side_effect=construct) as factory, \
                patch.object(api, "generate_briefing", AsyncMock(return_value=BriefingResult(
                    "conversation", "Answer", [], [],
                ))) as generate:
            for _ in range(2):
                with TestClient(api.app) as client:
                    server = api.app.state.mcp_server
                    for prompt in ("First", "Follow up"):
                        self.assertEqual(client.post("/api/briefings", json={"prompt": prompt}).status_code, 200)
                        generate.assert_awaited_with(prompt, conversation_id=None, mcp_server=server)
                        self.assertFalse(server.closed)
                    server.list_tools.assert_awaited_once()
                self.assertTrue(server.closed)
                self.assertFalse(hasattr(api.app.state, "mcp_server"))
        self.assertEqual(factory.call_count, 2)
        self.assertIsNot(servers[0], servers[1])
        self.assertIs(tasks[0], tasks[1])
        self.assertIs(tasks[2], tasks[3])

    def test_failed_mcp_connection_or_discovery_prevents_startup(self):
        for method in ("__aenter__", "list_tools"):
            with self.subTest(method=method), patch.object(api, "ensure_vector_store"), \
                    patch.object(api, "create_mcp_server") as factory:
                manager = factory.return_value
                target = manager if method == "__aenter__" else manager.__aenter__.return_value
                getattr(target, method).side_effect = RuntimeError("MCP unavailable")
                with self.assertRaisesRegex(RuntimeError, "MCP unavailable"):
                    with TestClient(api.app):
                        self.fail("Startup should fail")
                if method == "list_tools":
                    manager.__aexit__.assert_awaited_once()
                self.assertFalse(hasattr(api.app.state, "mcp_server"))


class SharedConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_reused_across_concurrent_failed_and_cancelled_runs(self):
        cancellation_started = asyncio.Event()

        class OfflineModel(Model):
            def __init__(self, prompt):
                self.prompt = prompt
                self.calls = 0

            async def get_response(self, *args, **kwargs):
                if self.prompt == "fail":
                    raise RuntimeError("model failed")
                if self.prompt == "cancel":
                    cancellation_started.set()
                    await asyncio.Event().wait()
                self.calls += 1
                investor_id = "INV-001" if self.prompt == "Redwood" else "INV-002"
                output = [ResponseFunctionToolCall(
                    type="function_call", name="find_investor", call_id="call_test",
                    arguments=json.dumps({"name": self.prompt}),
                )] if self.calls == 1 else [ResponseOutputMessage(
                    type="message", id="msg_test", role="assistant", status="completed",
                    content=[ResponseOutputText(type="output_text", annotations=[],
                        text=f"Investor [[cite:db:investors:{investor_id}]]")],
                )]
                return ModelResponse(output=output, usage=Usage(), response_id=None)

            def stream_response(self, *args, **kwargs):
                raise NotImplementedError

        real_run = Runner.run

        async def offline_run(agent, prompt, **kwargs):
            agent.model = OfflineModel(prompt)
            return await real_run(agent, prompt, **kwargs, run_config=RunConfig(tracing_disabled=True))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test", "OPENAI_VECTOR_STORE_ID": "offline-test"}), \
                patch.object(api, "ensure_vector_store"), \
                patch.object(api, "create_mcp_server", wraps=mcp_agent.create_mcp_server) as factory, \
                patch.object(mcp_agent.Runner, "run", side_effect=offline_run), \
                self.assertLogs("backend.timing", level="INFO") as captured:
            async with api.lifespan(api.app):
                server = api.app.state.mcp_server
                with patch.object(mcp_agent, "create_mcp_server", side_effect=AssertionError("Unexpected subprocess")):
                    results = await asyncio.gather(
                        mcp_agent.run_agent("Redwood", mcp_server=server),
                        mcp_agent.run_agent("Beacon", mcp_server=server),
                    )
                    for result, investor_id in zip(results, ("INV-001", "INV-002")):
                        self.assertEqual([s["source_id"] for s in result.sources], [f"db:investors:{investor_id}"])
                        self.assertEqual(result.cited_source_ids, [f"db:investors:{investor_id}"])
                        self.assertEqual(result.invalid_source_ids, [])
                    with self.assertRaisesRegex(RuntimeError, "model failed"):
                        await mcp_agent.run_agent("fail", mcp_server=server)
                    task = asyncio.create_task(mcp_agent.run_agent("cancel", mcp_server=server))
                    await asyncio.wait_for(cancellation_started.wait(), timeout=5)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    again = await mcp_agent.run_agent("Redwood", mcp_server=server)
                    self.assertEqual(again.cited_source_ids, ["db:investors:INV-001"])
                    self.assertIsNotNone(server.session)
            self.assertIsNone(server.session)
            factory.assert_called_once()
        ends = [json.loads(r.getMessage()) for r in captured.records if '"phase": "end"' in r.getMessage()]
        self.assertEqual(sum(r["stage"] == "mcp.connect" for r in ends), 1)
        self.assertEqual(sum(r["stage"] == "mcp.cleanup" for r in ends), 1)

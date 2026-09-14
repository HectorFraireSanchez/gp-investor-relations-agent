"""Offline timing checks, including real SDK hook dispatch and concurrent runs."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from agents import Agent, Model, RunConfig, Runner, function_tool
from agents.items import ModelResponse
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from backend import timing
from backend.sdk_timing import ModelTimingHooks, TimedConversationsSession, TimedMCPServerStdio


def records(capture):
    return [json.loads(record.getMessage()) for record in capture.records]


class TimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_duration_errors_and_cancellation_do_not_log_payloads(self):
        clock = [1.0]
        with self.assertLogs("backend.timing", level="INFO") as captured, \
                patch.object(timing, "perf_counter", side_effect=lambda: clock[0]):
            for error in (ValueError("private payload"), asyncio.CancelledError()):
                with self.assertRaises(type(error)), timing.timing_scope():
                    with timing.measure("failure"):
                        clock[0] += 0.25
                        raise error
        ends = [r for r in records(captured) if r["phase"] == "end"]
        self.assertEqual([r["status"] for r in ends], ["error", "cancelled"])
        self.assertEqual([r["duration_ms"] for r in ends], [250, 250])
        self.assertNotEqual(ends[0]["request_id"], ends[1]["request_id"])
        self.assertNotIn("private payload", str(records(captured)))

    async def test_parallel_requests_and_tools_keep_distinct_ids(self):
        @timing.timed("request")
        async def request():
            @timing.timed("tool")
            async def tool():
                await asyncio.sleep(0)
            await asyncio.gather(tool(), tool())

        with self.assertLogs("backend.timing", level="INFO") as captured:
            await asyncio.gather(request(), request())
        ends = [r for r in records(captured) if r["phase"] == "end"]
        request_ids = {r["request_id"] for r in ends}
        self.assertEqual(len(request_ids), 2)
        self.assertEqual(len({r["operation_id"] for r in ends}), 6)
        for request_id in request_ids:
            self.assertEqual(sorted(r["stage"] for r in ends if r["request_id"] == request_id),
                             ["request", "tool", "tool"])

    async def test_session_and_mcp_adapters_preserve_results_and_failures(self):
        from agents import OpenAIConversationsSession
        from agents.mcp import MCPServerStdio
        from types import SimpleNamespace

        session = TimedConversationsSession(openai_client=object())
        server = TimedMCPServerStdio(params={"command": "unused"})
        messages = [{"role": "user", "content": "private prompt"}]
        tool_error = SimpleNamespace(is_error=True)
        with self.assertLogs("backend.timing", level="INFO") as captured, timing.timing_scope(), \
                patch.object(OpenAIConversationsSession, "get_items", AsyncMock(return_value=messages)) as get, \
                patch.object(OpenAIConversationsSession, "add_items", AsyncMock()) as add, \
                patch.object(MCPServerStdio, "call_tool", AsyncMock(return_value=tool_error)) as call:
            self.assertIs(await session.get_items(limit=2), messages)
            await session.add_items(messages)
            self.assertIs(await server.call_tool("find_investor", {"name": "private investor"}), tool_error)
            get.assert_awaited_once_with(limit=2)
            add.assert_awaited_once_with(messages)
            call.assert_awaited_once_with("find_investor", {"name": "private investor"}, meta=None)
        ends = [r for r in records(captured) if r["phase"] == "end"]
        self.assertEqual([r["stage"] for r in ends], ["conversation.load", "conversation.save", "mcp.tool"])
        self.assertEqual(ends[-1]["status"], "error")
        self.assertNotIn("private", str(records(captured)))

    async def test_real_runner_times_multiple_model_calls_and_errors(self):
        class OfflineModel(Model):
            def __init__(self, error=False):
                self.calls = 0
                self.error = error

            async def get_response(self, *args, **kwargs):
                self.calls += 1
                if self.error:
                    raise ValueError("private model failure")
                output = [ResponseFunctionToolCall(
                    type="function_call", name="lookup", call_id="call_test", arguments="{}",
                )] if self.calls == 1 else [ResponseOutputMessage(
                    type="message", id="msg_test", role="assistant", status="completed",
                    content=[ResponseOutputText(type="output_text", text="private answer", annotations=[])],
                )]
                return ModelResponse(output=output, usage=Usage(), response_id=None)

            def stream_response(self, *args, **kwargs):
                raise NotImplementedError

        @function_tool
        def lookup() -> str:
            return "private tool result"

        for fail in (False, True):
            hooks = ModelTimingHooks()
            model = OfflineModel(error=fail)
            with self.assertLogs("backend.timing", level="INFO") as captured, timing.timing_scope():
                async def run():
                    with hooks.track_run():
                        return await Runner.run(
                            Agent(name="Offline", model=model, tools=[lookup]), "private prompt",
                            hooks=hooks, run_config=RunConfig(tracing_disabled=True),
                        )
                if fail:
                    with self.assertRaisesRegex(ValueError, "private model failure"):
                        await run()
                else:
                    self.assertEqual((await run()).final_output, "private answer")
            ends = [r for r in records(captured) if r["phase"] == "end"]
            self.assertEqual([r["call"] for r in ends], [1] if fail else [1, 2])
            self.assertEqual([r["status"] for r in ends], ["error"] if fail else ["ok", "ok"])
            self.assertNotIn("private", str(records(captured)))

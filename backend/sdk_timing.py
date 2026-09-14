"""Timing adapters for the installed Agents SDK's public lifecycle methods."""

import asyncio
from contextlib import contextmanager

from agents import OpenAIConversationsSession, RunHooks
from agents.mcp import MCPServerStdio

from backend.timing import StageTimer, measure, timed


class TimedMCPServerStdio(MCPServerStdio):
    @timed("mcp.connect")
    async def connect(self):
        return await super().connect()

    @timed("mcp.cleanup")
    async def cleanup(self):
        return await super().cleanup()

    @timed("mcp.list_tools")
    async def list_tools(self, run_context=None, agent=None):
        return await super().list_tools(run_context=run_context, agent=agent)

    async def call_tool(self, tool_name, arguments, meta=None):
        with measure("mcp.tool", tool=tool_name) as timer:
            result = await super().call_tool(tool_name, arguments, meta=meta)
            if result.is_error:
                timer.finish("error")
            return result


class TimedConversationsSession(OpenAIConversationsSession):
    @timed("conversation.load")
    async def get_items(self, limit=None):
        # Includes lazy remote conversation creation on the first turn.
        return await super().get_items(limit=limit)

    @timed("conversation.save")
    async def add_items(self, items):
        return await super().add_items(items)


class ModelTimingHooks(RunHooks):
    def __init__(self):
        self.pending = None
        self.call_number = 0

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        self.call_number += 1
        self.pending = StageTimer("model.request", call=self.call_number)

    async def on_llm_end(self, context, agent, response):
        if self.pending is not None:
            self.pending.finish()
            self.pending = None

    @contextmanager
    def track_run(self):
        # The SDK does not call on_llm_end when model invocation raises.
        try:
            yield
        except BaseException as exc:
            if self.pending is not None:
                self.pending.finish(
                    "cancelled" if isinstance(exc, asyncio.CancelledError) else "error",
                    error_type=type(exc).__name__,
                )
                self.pending = None
            raise

"""Session context and SDK persistence checks without external API requests."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agents import OpenAIConversationsSession
from agents.run_internal.session_persistence import prepare_input_with_session
from openai import AsyncOpenAI

from backend import mcp_agent


def dialogue():
    # Responses input messages and normalized Conversations output messages.
    return [
        {"role": "user", "content": "Prepare Redwood. [[cite:user-text]]"},
        {"type": "message", "role": "assistant", "id": "msg_history",
         "status": "completed", "phase": "final_answer", "content": [
             {"type": "output_text", "text": "Redwood owes $250K. [[cite:db:old]]",
              "annotations": [], "logprobs": []},
             {"type": "refusal", "refusal": "Unchanged refusal."},
         ]},
        {"role": "assistant", "content": "Other text [[cite:doc:old]] stays."},
        {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "What about them?"},
            {"type": "input_image", "image_url": "https://example.com/image.png",
             "detail": "auto"},
        ]},
    ]


class SessionInputTests(unittest.TestCase):
    def test_dialogue_preserved_and_only_old_assistant_markers_removed(self):
        history = dialogue()
        original = deepcopy(history)
        result = mcp_agent._prepare_session_input(history, [])
        self.assertEqual(result[0], history[0])
        self.assertEqual(result[3], history[3])
        self.assertEqual(result[1]["content"][0]["text"], "Redwood owes $250K. ")
        self.assertEqual(result[1]["content"][1], history[1]["content"][1])
        self.assertEqual(result[1]["phase"], "final_answer")
        self.assertEqual(result[1]["id"], "msg_history")
        self.assertEqual(result[2]["content"], "Other text  stays.")
        self.assertEqual(history, original)
        self.assertIsNot(result[1], history[1])
        self.assertIsNot(result[1]["content"], history[1]["content"])

    def test_old_execution_artifacts_removed_but_current_items_untouched(self):
        artifacts = [
            {"type": "function_call", "call_id": "call_1", "name": "find_investor",
             "arguments": '{"name":"Redwood"}'},
            {"type": "function_call_output", "call_id": "call_1", "output": "old data"},
            {"type": "reasoning", "id": "rs_old", "summary": []},
            {"type": "mcp_call", "id": "mcp_old", "name": "search",
             "server_label": "northstar", "arguments": "{}", "output": "old data"},
            {"type": "item_reference", "id": "old_item"},
            {"role": "developer", "content": "Old internal instruction"},
        ]
        history = dialogue() + artifacts
        new_items = deepcopy(artifacts) + [
            {"role": "assistant", "content": "Current [[cite:db:current]]"},
            {"role": "user", "content": "Current question"},
        ]
        original_history, original_new = deepcopy(history), deepcopy(new_items)
        result = mcp_agent._prepare_session_input(history, new_items)
        self.assertEqual(len(result), 4 + len(new_items))
        for actual, expected in zip(result[4:], new_items):
            self.assertIs(actual, expected)
        self.assertEqual(history, original_history)
        self.assertEqual(new_items, original_new)
        self.assertEqual(mcp_agent._prepare_session_input([], []), [])


class SessionSdkTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_sends_sanitized_history_without_persisting_it_as_new(self):
        history = dialogue()[:2]
        original = deepcopy(history)
        async with AsyncOpenAI(api_key="offline-test") as client:
            session = OpenAIConversationsSession(conversation_id="conv_offline", openai_client=client)
            with patch.object(session, "get_items", AsyncMock(return_value=history)):
                prepared, to_persist = await prepare_input_with_session(
                    "Follow up", session, mcp_agent._session_input_callback
                )
        self.assertEqual(history, original)
        self.assertEqual(len(prepared), 3)
        self.assertEqual(prepared[1]["content"][0]["text"], "Redwood owes $250K. ")
        self.assertNotIn("id", prepared[1])  # SDK removes Conversations replay metadata.
        self.assertEqual(to_persist, [{"role": "user", "content": "Follow up"}])

    async def test_runner_receives_session_only_when_explicitly_supplied(self):
        async with AsyncOpenAI(api_key="offline-test") as client:
            session = OpenAIConversationsSession(conversation_id="conv_offline", openai_client=client)
            for supplied in (None, session):
                with self.subTest(session=supplied is not None), \
                        patch.dict(mcp_agent.os.environ, {
                            "OPENAI_API_KEY": "offline-test", "OPENAI_VECTOR_STORE_ID": "offline-test"
                        }), \
                        patch.object(mcp_agent, "MCPServerStdio"), \
                        patch.object(mcp_agent.Runner, "run", AsyncMock(return_value=SimpleNamespace(
                            final_output="Answer", new_items=[]
                        ))) as run:
                    result = await mcp_agent.run_agent("Question", session=supplied)
                    self.assertEqual(result.final_output, "Answer")
                    self.assertEqual(result.sources, [])
                    self.assertEqual(result.new_items, [])
                    self.assertEqual(result.invalid_source_ids, [])
                    self.assertEqual(run.await_args.args[1], "Question")
                    if supplied is None:
                        self.assertEqual(set(run.await_args.kwargs), {"hooks"})
                    else:
                        self.assertIs(run.await_args.kwargs["session"], session)
                        self.assertIs(run.await_args.kwargs["run_config"].session_input_callback,
                                      mcp_agent._session_input_callback)

import unittest
from unittest.mock import AsyncMock, patch

from agents import OpenAIConversationsSession
from openai import AsyncOpenAI

from backend import service
from backend.mcp_agent import AgentResponse


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = AsyncOpenAI(api_key="offline-test")
        self.addAsyncCleanup(self.client.close)
        self.sessions = []

        def construct(**kwargs):
            session = OpenAIConversationsSession(openai_client=self.client, **kwargs)
            self.sessions.append(session)
            return session

        self.factory = self.enterContext(patch.object(
            service, "OpenAIConversationsSession", side_effect=construct
        ))

    async def test_new_conversation_returns_initialized_id_and_rendered_response(self):
        source = {"source_id": "doc:notes.md", "source_type": "document", "filename": "notes.md"}
        raw = AgentResponse("Claim. [[cite:doc:notes.md]]", [source], [])
        async def run(prompt, *, session):
            with self.assertRaises(ValueError):
                _ = session.session_id
            session.session_id = "initialized-id"
            return raw

        with patch.object(service, 'run_agent', AsyncMock(side_effect=run)) as agent:
            result = await service.generate_briefing("Prepare a briefing")
        self.factory.assert_called_once_with()
        agent.assert_awaited_once_with("Prepare a briefing", session=self.sessions[0])
        self.assertEqual(result.conversation_id, "initialized-id")
        self.assertEqual(result.answer, "Claim. [1]")
        self.assertEqual(result.citations[0]['source'], source)
        self.assertEqual(result.invalid_source_ids, [])

    async def test_resumed_requests_each_construct_a_new_wrapper(self):
        raw = AgentResponse("Answer", [], [])
        with patch.object(service, 'run_agent', AsyncMock(return_value=raw)) as agent:
            for _ in range(2):
                result = await service.generate_briefing("Follow up", conversation_id="existing-id")
                self.factory.assert_called_with(conversation_id="existing-id")
                agent.assert_awaited_with("Follow up", session=self.sessions[-1])
                self.assertEqual(result.conversation_id, "existing-id")
        self.assertEqual(self.factory.call_count, 2)
        self.assertIsNot(self.sessions[0], self.sessions[1])

    async def test_blank_prompt_does_not_run_agent(self):
        with patch.object(service, 'run_agent', AsyncMock()) as agent:
            with self.assertRaises(ValueError):
                await service.generate_briefing("   ")
        agent.assert_not_awaited()
        self.factory.assert_not_called()

    async def test_agent_error_propagates_to_caller(self):
        with patch.object(service, 'run_agent', AsyncMock(side_effect=RuntimeError('failure'))):
            with self.assertRaisesRegex(RuntimeError, 'failure'):
                await service.generate_briefing("Briefing")
        self.factory.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

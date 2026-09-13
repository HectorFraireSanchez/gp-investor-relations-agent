import contextlib
import io
import unittest
from unittest.mock import AsyncMock, patch

from backend import cli, service
from backend.citations import RenderedResponse
from backend.mcp_agent import AgentResponse


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_rendered_response(self):
        source = {"source_id": "doc:notes.md", "source_type": "document", "filename": "notes.md"}
        raw = AgentResponse("Claim. [[cite:doc:notes.md]]", [source], [])
        with patch.object(service, 'run_agent', AsyncMock(return_value=raw)) as agent:
            result = await service.generate_briefing("Prepare a briefing")
        agent.assert_awaited_once_with("Prepare a briefing")
        self.assertEqual(result.answer, "Claim. [1]")
        self.assertEqual(result.citations[0]['source'], source)

    async def test_blank_prompt_does_not_run_agent(self):
        with patch.object(service, 'run_agent', AsyncMock()) as agent:
            with self.assertRaises(ValueError):
                await service.generate_briefing("   ")
        agent.assert_not_awaited()

    async def test_agent_error_propagates_to_caller(self):
        with patch.object(service, 'run_agent', AsyncMock(side_effect=RuntimeError('failure'))):
            with self.assertRaisesRegex(RuntimeError, 'failure'):
                await service.generate_briefing("Briefing")


class CliTests(unittest.TestCase):
    def test_setup_runs_once_before_service_and_prints_sources(self):
        events = []

        async def generate(prompt):
            self.assertEqual(prompt, 'Prep me for Redwood')
            events.append('service')
            return RenderedResponse('Claim. [1]', [{'number': 1, 'source_id': 'doc:notes.md', 'source': {}}], [])

        terminal = io.StringIO()
        with patch.object(cli, 'load_dotenv'), patch.object(cli, 'ensure_vector_store', side_effect=lambda: events.append('setup')) as setup, patch.object(cli, 'generate_briefing', side_effect=generate), contextlib.redirect_stdout(terminal):
            self.assertEqual(cli.main(['Prep me for Redwood']), 0)
        self.assertEqual(events, ['setup', 'service'])
        setup.assert_called_once()
        self.assertEqual(terminal.getvalue(), 'Claim. [1]\n\nSources\n[1] doc:notes.md\n')

    def test_setup_error_does_not_run_service(self):
        terminal = io.StringIO()
        with patch.object(cli, 'load_dotenv'), patch.object(cli, 'ensure_vector_store', side_effect=RuntimeError('setup failed')), patch.object(cli, 'generate_briefing', AsyncMock()) as generate, contextlib.redirect_stderr(terminal):
            self.assertEqual(cli.main(['Briefing']), 1)
        generate.assert_not_awaited()
        self.assertIn('setup failed', terminal.getvalue())

    def test_help_and_blank_prompt_do_not_initialize(self):
        for arguments, code in ((['--help'], 0), (['   '], 2)):
            with self.subTest(arguments=arguments), patch.object(cli, 'ensure_vector_store') as setup, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main(arguments)
                self.assertEqual(raised.exception.code, code)
                setup.assert_not_called()


if __name__ == "__main__":
    unittest.main()

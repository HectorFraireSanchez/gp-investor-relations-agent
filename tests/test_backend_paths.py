"""Regression checks for package relocation, without external API requests."""

import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import create_database, domain, mcp_agent, paths, setup_documents


class ResourcePathTests(unittest.TestCase):
    def test_resources_and_database_reads_from_another_directory(self):
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                self.assertEqual(paths.ROOT_DIR, Path(__file__).resolve().parents[1])
                self.assertEqual(paths.ENV_PATH, paths.ROOT_DIR / ".env")
                self.assertEqual(setup_documents.DOCUMENTS_DIR, paths.ROOT_DIR / "documents")
                self.assertEqual(domain.DB_PATH, paths.BACKEND_DIR / "data/northstar.db")
                self.assertEqual(create_database.DB_PATH, domain.DB_PATH)
                self.assertTrue((setup_documents.DOCUMENTS_DIR / "redwood_side_letter.md").is_file())
                investor = domain.find_investor("Redwood")
                self.assertEqual(investor["investor_id"], "INV-001")
                self.assertEqual(domain.get_positions("INV-001")[0]["commitment"], 5000000)
                self.assertEqual(domain.get_capital_calls("INV-001")[0]["call_id"], "CC-019")
            finally:
                os.chdir(original)

    def test_create_and_reset_in_a_temporary_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "data/northstar.db"
            with patch.object(create_database, "DB_PATH", database), contextlib.redirect_stdout(io.StringIO()):
                create_database.main()
                with contextlib.closing(sqlite3.connect(database)) as connection:
                    connection.execute("DELETE FROM investors")
                    connection.commit()
                create_database.main()
            with contextlib.closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM investors").fetchone()[0], 3)
                self.assertEqual(connection.execute("SELECT amount FROM capital_calls WHERE call_id='CC-019'").fetchone()[0], 250000)

    def test_setup_uses_root_documents_and_persists_to_its_env_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            with patch.dict(os.environ, {"OPENAI_VECTOR_STORE_ID": ""}), \
                    patch.object(setup_documents, "ENV_PATH", env_path), \
                    patch.object(setup_documents, "OpenAI") as client_factory:
                client = client_factory.return_value
                client.vector_stores.create.return_value.id = "test-store"
                uploaded_paths = []

                def upload(**kwargs):
                    uploaded_paths.append(Path(kwargs["file"].name))
                    return SimpleNamespace(status="completed")

                client.vector_stores.files.upload_and_poll.side_effect = upload
                self.assertEqual(setup_documents.ensure_vector_store(), "test-store")
                self.assertEqual(set(uploaded_paths), set(paths.DOCUMENTS_DIR.glob("*.md")))
                self.assertIn("test-store", env_path.read_text())
                self.assertEqual(os.environ["OPENAI_VECTOR_STORE_ID"], "test-store")


class McpPackageTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_allows_slow_mcp_initialization(self):
        real_server = mcp_agent.MCPServerStdio

        def delayed_server(**kwargs):
            # Exceed MCP v2's ten-second discovery plus five-second initialize waits.
            kwargs["params"] = {**kwargs["params"], "args": [
                "-c",
                "import time, runpy; time.sleep(20); "
                "runpy.run_module('backend.mcp_server', run_name='__main__')",
            ]}
            return real_server(**kwargs)

        async def inspect_server(agent, prompt, **kwargs):
            result = await agent.mcp_servers[0].call_tool("find_investor", {"name": "Redwood"})
            self.assertFalse(result.is_error)
            payload = json.loads(result.content[0].text)
            self.assertEqual(payload["data"]["investor_id"], "INV-001")
            return SimpleNamespace(final_output="Delayed MCP ready", new_items=[])

        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test", "OPENAI_VECTOR_STORE_ID": "offline-test"}), \
                patch.object(mcp_agent, "MCPServerStdio", side_effect=delayed_server), \
                patch.object(mcp_agent.Runner, "run", side_effect=inspect_server):
            response = await mcp_agent.run_agent("Inspect tools without calling the model")
        self.assertEqual(response.final_output, "Delayed MCP ready")

    async def test_agent_launches_real_mcp_package_from_another_directory(self):
        async def inspect_server(agent, prompt, **kwargs):
            server = agent.mcp_servers[0]
            names = {tool.name for tool in await server.list_tools()}
            self.assertEqual(names, {"find_investor", "list_investors", "get_positions", "get_capital_calls", "search_investor_documents"})
            result = await server.call_tool("find_investor", {"name": "Redwood"})
            self.assertFalse(result.is_error)
            # This installed SDK returns the MCP envelope as a JSON text block.
            payload = json.loads(result.content[0].text)
            self.assertEqual(payload["data"]["investor_id"], "INV-001")
            self.assertEqual(payload["sources"][0]["source_id"], "db:investors:INV-001")
            self.assertEqual(payload["sources"][0]["database"], "northstar.db")
            listed = await server.call_tool("list_investors", {})
            self.assertFalse(listed.is_error)
            # List results arrive as one JSON text block per investor in this SDK.
            records = [json.loads(block.text) for block in listed.content]
            self.assertEqual([record["data"] for record in records], domain.list_investors())
            self.assertEqual([record["data"]["investor_id"] for record in records], ["INV-003", "INV-002", "INV-001"])
            for record in records:
                investor_id = record["data"]["investor_id"]
                self.assertEqual(record["sources"], [{
                    "source_id": f"db:investors:{investor_id}",
                    "source_type": "database", "database": "northstar.db",
                    "schema": "main", "table": "investors",
                    "record_key": {"investor_id": investor_id},
                }])
            return SimpleNamespace(final_output="Checked MCP package", new_items=[])

        original = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-test", "OPENAI_VECTOR_STORE_ID": "offline-test"}), \
                        patch.object(mcp_agent.Runner, "run", side_effect=inspect_server):
                    response = await mcp_agent.run_agent("Inspect tools without calling the model")
                self.assertEqual(response.final_output, "Checked MCP package")
            finally:
                os.chdir(original)

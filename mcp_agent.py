import asyncio
import os
import sys
from pathlib import Path

from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def main():
    server_path = Path(__file__).parent / "mcp_server.py"

    async with MCPServerStdio(
        name="Northstar Investor Operations",
        params={
            "command": sys.executable,
            "args": [str(server_path)],
            "env": {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            "OPENAI_VECTOR_STORE_ID": os.environ["OPENAI_VECTOR_STORE_ID"],
            }
        },
        cache_tools_list=True,
    ) as server:

        agent = Agent(
            name="Investor Relations Assistant",
            instructions=(
                "You assist the investor relations team at Northstar Capital, "
                "a fictional private-markets GP. "

                "Use MCP tools to retrieve authoritative investor information. "

                "Use structured tools such as get_positions and get_capital_calls "
                "for structured financial information. "

                "Use search_investor_documents for unstructured information such "
                "as side-letter provisions, meeting notes, reporting obligations, "
                "and fund-report context. "

                "Never invent information. If required information is unavailable, "
                "say so. "

                "For every material claim that comes from document retrieval, "
                "include the source filename immediately after the claim in the "
                "format [Source: filename]."
            ),
            mcp_servers=[server],
        )

        result = await Runner.run(
            agent,
            "Prepare me for a meeting with Redwood Family Office. "
            "Include: "
            "- their investment position "
            "- any outstanding capital calls "
            "- any special reporting obligations "
            "- what they discussed in their most recent meeting "
            "Cite the source for information taken from documents."
        )

        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
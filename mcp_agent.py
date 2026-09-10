import asyncio
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
        },
        cache_tools_list=True,
    ) as server:

        agent = Agent(
            name="Investor Relations Assistant",
            instructions=(
                "You assist the investor relations team at Northstar Capital, "
                "a fictional private-markets GP. "
                "Use the available MCP tools to retrieve investor information. "
                "Never invent financial information. "
                "If information is unavailable, say so."
            ),
            mcp_servers=[server],
        )

        result = await Runner.run(
            agent,
            "Does redwood have any capital calls?"
        )

        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
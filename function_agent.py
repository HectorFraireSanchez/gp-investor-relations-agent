import json
from pathlib import Path

from agents import Agent, Runner
from agents.decorators import tool
from dotenv import load_dotenv

import domain


load_dotenv(Path(__file__).parent / ".env")


@tool
def find_investor(name: str) -> str:
    """Find an investor by name."""
    result = domain.find_investor(name)
    return json.dumps(result)


@tool
def get_positions(investor_id: str) -> str:
    """Get an investor's fund positions."""
    result = domain.get_positions(investor_id)
    return json.dumps(result)


@tool
def get_capital_calls(investor_id: str) -> str:
    """Get an investor's capital calls."""
    result = domain.get_capital_calls(investor_id)
    return json.dumps(result)


agent = Agent(
    name="Investor Relations Assistant",
    instructions=(
        "You assist the investor relations team at Northstar Capital, "
        "a fictional private-markets GP. "
        "Use the available tools to retrieve investor information. "
        "Never invent financial information. "
        "If information is unavailable, say so."
    ),
    tools=[
        find_investor,
        get_positions,
        get_capital_calls,
    ],
)


result = Runner.run_sync(
    agent,
    "What are Redwood's positions?"
)

print(result.final_output)

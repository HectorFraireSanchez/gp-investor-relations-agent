"""Application boundary shared by the CLI and future clients."""

from citations import RenderedResponse, render_citations
from mcp_agent import run_agent


async def generate_briefing(prompt: str) -> RenderedResponse:
    if not prompt.strip():
        raise ValueError("Please enter a prompt before generating a briefing.")
    agent_response = await run_agent(prompt)
    return render_citations(agent_response)

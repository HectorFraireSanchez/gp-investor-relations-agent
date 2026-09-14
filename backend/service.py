"""Frontend-independent briefing boundary used by the HTTP API."""

from dataclasses import dataclass

from backend.citations import render_citations
from backend.mcp_agent import run_agent
from backend.sdk_timing import (
    TimedConversationsSession as OpenAIConversationsSession,
    TimedMCPServerStdio,
)
from backend.timing import measure, timed


@dataclass
class BriefingResult:
    conversation_id: str
    answer: str
    citations: list[dict]
    invalid_source_ids: list[str]


@timed("briefing.total")
async def generate_briefing(
    prompt: str, *, conversation_id: str | None = None,
    mcp_server: TimedMCPServerStdio | None = None,
) -> BriefingResult:
    if not prompt.strip():
        raise ValueError("Please enter a prompt before generating a briefing.")
    # Each request gets a wrapper; OpenAI stores the persistent conversation.
    with measure("conversation.wrapper"):
        session = (
            OpenAIConversationsSession() if conversation_id is None
            else OpenAIConversationsSession(conversation_id=conversation_id)
        )
    if mcp_server is None:
        agent_response = await run_agent(prompt, session=session)
    else:
        agent_response = await run_agent(prompt, session=session, mcp_server=mcp_server)
    with measure("citations.render"):
        rendered = render_citations(agent_response)
    return BriefingResult(
        conversation_id=session.session_id,
        answer=rendered.answer,
        citations=rendered.citations,
        invalid_source_ids=rendered.invalid_source_ids,
    )

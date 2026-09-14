"""Frontend-independent briefing boundary used by the HTTP API."""

from dataclasses import dataclass

from agents import OpenAIConversationsSession

from backend.citations import render_citations
from backend.mcp_agent import run_agent


@dataclass
class BriefingResult:
    conversation_id: str
    answer: str
    citations: list[dict]
    invalid_source_ids: list[str]


async def generate_briefing(
    prompt: str, *, conversation_id: str | None = None
) -> BriefingResult:
    if not prompt.strip():
        raise ValueError("Please enter a prompt before generating a briefing.")
    # Each request gets a wrapper; OpenAI stores the persistent conversation.
    session = (
        OpenAIConversationsSession() if conversation_id is None
        else OpenAIConversationsSession(conversation_id=conversation_id)
    )
    agent_response = await run_agent(prompt, session=session)
    rendered = render_citations(agent_response)
    return BriefingResult(
        conversation_id=session.session_id,
        answer=rendered.answer,
        citations=rendered.citations,
        invalid_source_ids=rendered.invalid_source_ids,
    )

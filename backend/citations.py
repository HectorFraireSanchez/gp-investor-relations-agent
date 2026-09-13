"""Deterministic presentation of citations backed by per-run provenance."""

from copy import deepcopy
from dataclasses import dataclass

from backend.mcp_agent import AgentResponse, CITATION_PATTERN


@dataclass
class RenderedResponse:
    answer: str
    citations: list[dict]
    invalid_source_ids: list[str]


def render_citations(response: AgentResponse) -> RenderedResponse:
    registry = {}
    for source in response.sources:
        registry.setdefault(source["source_id"], source)

    invalid_source_ids = list(dict.fromkeys(response.invalid_source_ids))
    invalid = set(invalid_source_ids)
    numbers = {}
    citations = []

    def replace_marker(match) -> str:
        source_id = match.group(1)
        # Recheck membership so missing or stale validation state cannot grant trust.
        if source_id not in registry or source_id in invalid:
            if source_id not in invalid:
                invalid.add(source_id)
                invalid_source_ids.append(source_id)
            return "[citation unavailable]"

        if source_id not in numbers:
            number = len(citations) + 1
            numbers[source_id] = number
            citations.append({
                "number": number,
                "source_id": source_id,
                "source": deepcopy(registry[source_id]),
            })
        return f"[{numbers[source_id]}]"

    answer = CITATION_PATTERN.sub(replace_marker, response.final_output)
    return RenderedResponse(answer, citations, invalid_source_ids)

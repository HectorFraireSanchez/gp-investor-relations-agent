import json
import os
import re
import sys
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field

from agents import Agent, RunConfig, Runner, Session
from agents.items import RunItem, ToolCallOutputItem, TResponseInputItem
from agents.mcp import MCPServerStdio, MCPToolCustomDataContext
from dotenv import load_dotenv

from backend.paths import ENV_PATH, ROOT_DIR

load_dotenv(ENV_PATH)
CITATION_PATTERN = re.compile(r"\[\[cite:([^\[\]]*)\]\]")


@dataclass
class AgentResponse:
    final_output: str
    sources: list[dict]
    new_items: list[RunItem]
    cited_source_ids: list[str] = field(default_factory=list)
    invalid_source_ids: list[str] = field(default_factory=list)


def validate_citations(answer: str, sources: list[dict]) -> tuple[list[str], list[str]]:
    """Return cited IDs and invalid IDs; this checks membership, not claim support.

    Both lists are unique and ordered by first appearance. IDs are not normalized.
    Only the supplied per-run sources establish validity; neither input is modified.
    """
    cited_source_ids = list(dict.fromkeys(CITATION_PATTERN.findall(answer)))
    valid_source_ids = {source["source_id"] for source in sources}
    invalid_source_ids = [
        source_id for source_id in cited_source_ids if source_id not in valid_source_ids
    ]
    return cited_source_ids, invalid_source_ids


def _capture_mcp_sources(context: MCPToolCustomDataContext) -> dict | None:
    """Keep successful MCP provenance in SDK-only tool-output custom data."""
    if context.is_error:
        return None

    if context.structured_content is not None:
        payloads = [context.structured_content]
    else:
        # The installed SDK exposes unstructured MCP results as text blocks.
        # Decode the tool's JSON envelope, never the model's answer or document text.
        blocks = context.tool_output
        blocks = blocks if isinstance(blocks, list) else [blocks]
        payloads = []
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            try:
                payloads.append(json.loads(block["text"]))
            except (KeyError, TypeError, ValueError):
                continue

    sources = []
    for payload in payloads:
        # MCP wraps list return values in structured_content['result'].
        records = payload.get("result", payload) if isinstance(payload, Mapping) else payload
        records = records if isinstance(records, list) else [records]
        for record in records:
            if not isinstance(record, Mapping) or "data" not in record:
                continue
            candidates = record.get("sources", [])
            if not isinstance(candidates, list):
                continue
            for source in candidates:
                if (
                    isinstance(source, dict)
                    and isinstance(source.get("source_id"), str)
                    and source["source_id"].strip()
                ):
                    sources.append(deepcopy(source))
    return {"sources": sources}


def collect_sources(items: list[RunItem]) -> list[dict]:
    """Deduplicate captured MCP sources in encounter order; first occurrence wins."""
    sources = {}
    for item in items:
        if (
            not isinstance(item, ToolCallOutputItem)
            or item.tool_origin is None
            or item.tool_origin.type != "mcp"
        ):
            continue
        for source in (item.custom_data or {}).get("sources", []):
            if source["source_id"] not in sources:
                sources[source["source_id"]] = deepcopy(source)
    return list(sources.values())


def _prepare_session_input(
    history_items: list[TResponseInputItem], new_items: list[TResponseInputItem]
) -> list[TResponseInputItem]:
    """Copy ordinary old dialogue, strip old assistant citations, then append new input."""
    history = []
    for item in history_items:
        if item.get("type", "message") != "message" or item.get("role") not in (
            "user", "assistant"
        ):
            continue
        message = deepcopy(item)
        if message["role"] == "assistant":
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = CITATION_PATTERN.sub("", content)
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") in ("input_text", "output_text"):
                        part["text"] = CITATION_PATTERN.sub("", part["text"])
        history.append(message)
    return history + new_items


def _session_input_callback(
    history_items: list[TResponseInputItem], new_items: list[TResponseInputItem]
) -> list[TResponseInputItem]:
    prepared = _prepare_session_input(history_items, new_items)
    # SDK 0.22.2 gives callbacks a private deep copy of session history, then
    # fingerprints that list AFTER the callback to identify old versus new items.
    # Replace only this private list, not its original objects or stored history,
    # so citation-stripped copies are not mistakenly persisted as new messages.
    history_items[:] = prepared[:len(prepared) - len(new_items)]
    return prepared


async def run_agent(prompt: str, *, session: Session | None = None) -> AgentResponse:
    async with MCPServerStdio(
        name="Northstar Investor Operations",
        params={
            "command": sys.executable,
            "args": ["-m", "backend.mcp_server"],
            "cwd": str(ROOT_DIR),
            "env": {
                "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
                "OPENAI_VECTOR_STORE_ID": os.environ["OPENAI_VECTOR_STORE_ID"],
            },
        },
        cache_tools_list=True,
        custom_data_extractor=_capture_mcp_sources,
    ) as server:

        agent = Agent(
            name="Investor Relations Assistant",
            instructions=(
                "You assist investor relations professionals at Northstar Capital. "
                "Use MCP tools to retrieve investor information rather than inventing facts. "
                "Use prior conversation only to understand references and user intent, "
                "not as authoritative factual evidence. Re-query the appropriate MCP tools "
                "for material factual claims on each run and cite sources returned in that run. "
                "Use list_investors only when the user asks to enumerate all investors, "
                "browse available investors, or describe the investor base. For a particular "
                "investor named in the request, use find_investor and do not call list_investors. "
                "Resolve the name first, then pass the returned data.investor_id to "
                "get_positions and get_capital_calls for financial information; never guess "
                "an investor ID or substitute the investor's name. "
                "Use search_investor_documents for unstructured information such as "
                "side-letter provisions, meeting notes, reporting obligations, and "
                "fund-report context. "
                "For requests limited to investor records, positions, or capital calls "
                "(including call status), use only structured tools. Search investor documents only when the request "
                "needs document context, such as reporting obligations, meeting history, "
                "or a broader briefing. "
                "Tool results pair data with sources containing provenance metadata. "
                "Ground factual claims in the returned data and associate them with "
                "the corresponding sources. For each material factual claim with returned "
                "provenance, cite its exact source_id immediately after the claim using "
                "[[cite:<source_id>]]. Cite both structured database facts and document-derived "
                "facts. If a claim relies on multiple sources, use one marker per source. "
                "Copy source_id values exactly from tool results; never invent, modify, "
                "shorten, reconstruct, or guess them. Use these markers instead of free-form "
                "source text or manually reconstructed database, schema, table, or filename "
                "citations. Do not reproduce full provenance objects in the answer. "
                "Never invent information. If required information is unavailable, say so. "
                "If no source metadata is returned for a claim, do not fabricate a citation."
            ),
            mcp_servers=[server],
        )

        if session is None:
            result = await Runner.run(agent, prompt)
        else:
            result = await Runner.run(
                agent, prompt, session=session,
                run_config=RunConfig(session_input_callback=_session_input_callback),
            )
        sources = collect_sources(result.new_items)
        cited_source_ids, invalid_source_ids = validate_citations(result.final_output, sources)

        return AgentResponse(
            final_output=result.final_output,
            sources=sources,
            new_items=result.new_items,
            cited_source_ids=cited_source_ids,
            invalid_source_ids=invalid_source_ids,
        )

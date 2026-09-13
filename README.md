# GP Investor Relations Agent

An AI-assisted application for investor meeting preparation at Northstar Capital,
a fictional private-markets general partner (GP). An investor-relations user can
ask for a briefing that brings together fund positions, capital calls, reporting
obligations and recent meeting context. The local prototype combines deterministic
SQLite-backed data tools and semantic document retrieval through MCP, with source
attribution for document-backed claims.

## What It Does

The workflow addresses a concrete investor-relations task: gathering financial
records, side-letter obligations and prior discussion points before an investor
meeting. Its scope is read-only briefing preparation for an IR professional to
review.

Pass a natural-language request to the CLI to receive a briefing with numbered
citations and a source list. The frontend-independent Python service returns the
same answer and full source metadata for future clients. No web UI or HTTP API
is currently included.

Example questions supported by the included data:

- Prepare me for a meeting with Redwood Family Office. Include its investment
  position, outstanding capital calls, special reporting obligations, and most
  recent meeting discussion.
- What outstanding capital calls does Redwood Family Office have?
- What special reporting obligations apply to Beacon University Endowment?
- What did Redwood Family Office discuss in its most recent meeting?

## Architecture

```mermaid
flowchart TD
    CLI["cli.py"] --> SERVICE["service.py<br/>async generate_briefing(prompt)"]
    SERVICE --> A["mcp_agent.py<br/>async run_agent(prompt)"]
    A <-->|MCP over stdio| M["mcp_server.py<br/>Structured and document tools"]
    M <--> D["domain.py<br/>SQLite queries"]
    D <--> DB[("data/northstar.db<br/>Investors, positions, capital calls")]
    M <--> S["search_investor_documents<br/>Semantic retrieval"]
    S <--> V["OpenAI vector store"]
    CLI -.->|At startup| SETUP["setup_documents.py<br/>ensure_vector_store()"]
    F["documents/<br/>Side letters and meeting notes"] -.->|Upload when creating a store| SETUP
    SETUP -.->|Create or reuse| V
    SETUP -.->|Persist new store ID| ENV[".env"]
    A --> RAW["AgentResponse<br/>Answer, provenance, validation, SDK items"]
    RAW --> R["citations.py<br/>Deterministic citation rendering"]
    R --> SERVICE
    SERVICE --> RESULT["RenderedResponse<br/>Answer, citations, invalid source IDs"]
    RESULT --> CLI
```

For each request, `mcp_agent.py` starts `mcp_server.py` as a subprocess using the
same Python interpreter. The OpenAI Agents SDK discovers and invokes the
server's tools over standard input/output; the MCP connection closes after the
run. Structured results and retrieved document excerpts return to the agent for
synthesis.

Structured operational data flows from SQLite through `domain.py` functions to
MCP tools. Unstructured investor documents remain in `documents/` and are uploaded
to an OpenAI vector store for semantic retrieval through an MCP tool. The agent
chooses tools and combines their results; the CLI calls the shared service to run
the workflow and render its citations.

For a meeting-preparation request, the agent can resolve the investor, retrieve
positions and capital calls, search for relevant side-letter and meeting-note
context, then assemble a briefing. The model selects the tools and their
arguments; the tool implementations determine how the requested data is retrieved.

## Design Decisions

- **Structured facts through deterministic tools.** `find_investor`,
  `get_positions`, and `get_capital_calls` call `domain.py` functions that query
  `data/northstar.db` using parameterized SQL. The model chooses which capabilities
  to invoke; application code supplies the authoritative values for this demo. This keeps financial data
  access behind domain functions rather than asking the model to infer balances
  from prose or giving it arbitrary data access.
- **Document context through retrieval.** `search_investor_documents` uses
  semantic search in an OpenAI vector store for side-letter terms and meeting
  context. It prefixes the query with the investor name, then filters results to
  filenames containing the first word of that name, returning at most three
  matching results. This is simple prototype context scoping, not an
  authorization boundary.
- **MCP as the capability interface.** Both structured tools and document search
  are exposed through the same MCP server. MCP provides tool discovery and
  invocation; domain functions and vector-store search perform the actual data
  access. Business logic remains separate from agent configuration.
- **Source attribution.** MCP results include authoritative database/document
  provenance. The agent uses `[[cite:source_id]]` markers, validated against sources
  returned during that run. Python assigns numbers in order of first citation,
  reuses numbers for repeated sources, and displays invalid references as
  `[citation unavailable]`. This validates source identity, not claim support.
- **Reuse across entry points.** `service.generate_briefing(prompt)` returns a
  `RenderedResponse` with `answer`, `citations`, and `invalid_source_ids`. Each
  citation preserves the full authoritative source object. Use
  `dataclasses.asdict(result)` for a JSON-ready dictionary. The CLI uses this
  boundary; evaluations continue to inspect the raw `run_agent()` response.

## Data and Documents

**All business data is synthetic. Northstar Capital and every investor are
fictional.** [data/northstar.db](data/northstar.db) stores investor IDs, names and
types; positions in Northstar Growth Fund II with commitment, contributed and
unfunded amounts; and capital calls with amounts, due dates and statuses.

| Investor | Structured coverage | Documents |
| --- | --- | --- |
| Redwood Family Office | Investor record, fund position, outstanding capital call | [Side letter](documents/redwood_side_letter.md); [August 14, 2026 meeting notes](documents/redwood_meeting_notes_2026_08_14.md) |
| Beacon University Endowment | Investor record, fund position, paid capital call | [Side letter](documents/beacon_side_letter.md); [July 20, 2026 meeting notes](documents/beacon_meeting_notes_2026_07_20.md) |
| Atlas Pension Fund | Investor record only; no position or capital-call records | None |

The four Markdown documents contain reporting obligations and meeting discussion
context. To inspect an answer, compare financial values with the SQLite database
(or its synthetic seed data in [create_database.py](create_database.py)) and
document-derived claims with the cited files in [documents/](documents/).
The agent is instructed to acknowledge unavailable information.

## Project Structure

```text
cli.py               Local command-line entry point and document-store setup
service.py           Frontend-independent briefing service
citations.py         Deterministic rendering of validated citation references
mcp_agent.py         Async agent entry point, instructions and MCP client setup
mcp_server.py        MCP tools for structured records and document search
domain.py            Domain/data-access functions that query SQLite
data/northstar.db     SQLite database containing synthetic operational records
create_database.py   Optional database recreation/reset with synthetic seed data
setup_documents.py   Reuses or creates a vector store; saves new ID to .env
test_search.py       Manual vector-store search inspection; loads .env
function_agent.py    Earlier direct function-tool example, outside the service path
tests/               Offline citation-renderer, service, and CLI tests
evals/               Raw agent evaluations with multiple trials and saved results
documents/           Two synthetic side letters and two meeting-note files
requirements.txt     Python dependencies
.env.example         Empty configuration placeholders to copy into .env
.gitignore           Excludes the virtual environment, .env and Python caches
```

## Running Locally

Use Python 3.10+ and PowerShell:

```powershell
git clone https://github.com/HectorFraireSanchez/gp-investor-relations-agent.git
cd gp-investor-relations-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` to add your own API key. Leave the vector-store ID blank on first setup:

```dotenv
OPENAI_API_KEY=your-openai-api-key
OPENAI_VECTOR_STORE_ID=
```

Start the application:

```powershell
python cli.py "Prep me for my meeting with Redwood Family Office."
```

At startup, `cli.py` calls `ensure_vector_store()` from `setup_documents.py` once.
It reuses the configured store if it exists. If no ID is configured, or OpenAI
reports that the configured store was not found, it creates a store, uploads the
files in `documents/`, waits for indexing, and saves `OPENAI_VECTOR_STORE_ID` in
`.env` and the running process. Initial startup may take longer while documents
are indexed. No manual document-setup command, ID copying, or PowerShell
environment-variable exports are needed.

The CLI prints the rendered answer and its numbered source list, then exits.
The MCP server starts automatically; no separate server command is needed.

For later runs, activate `.venv` and run `python cli.py "Your question"`; configuration is loaded
from `.env`. That file is intentionally git-ignored, and `.env.example` contains
placeholders only. Each user supplies their own OpenAI credentials and store.

Normal startup uses the existing `data/northstar.db`. To recreate a missing
database or reset it to the synthetic seed data, optionally run
`python create_database.py`. This deletes and replaces the existing database;
the app does not initialize SQLite automatically.

OpenAI API usage may incur charges and is
[billed separately from ChatGPT subscriptions](https://help.openai.com/en/articles/9039756-managing-billing-settings-on-chatgpt-web-and-platform).

Run the deterministic tests without API calls:

```powershell
python -m unittest discover -s tests -v
```

Run raw agent evaluations with API access and a configured vector store:

```powershell
python evals/run_evals.py
```

Future clients can call `await service.generate_briefing(prompt)` after loading
configuration and ensuring the document store at application startup.

## Technology

Python, OpenAI Agents SDK, Model Context Protocol (MCP) Python SDK, OpenAI API
and vector stores, SQLite, and python-dotenv.

## Current Scope and Limitations

- A portfolio prototype with a small synthetic dataset and local execution.
  Operational records
  are synthetic SQLite records, with no connection to a live fund-administration
  system.
- Reusing an existing vector store does not synchronize changes to local documents.
- No application authentication, authorization or tenant isolation. Filename
  filtering only narrows retrieved context.
- Responses and tool selection are model-driven. Instructions request source
  citations and acknowledgement of missing data; they do not guarantee factual
  or citation correctness.
- Evaluations check raw output, numeric amounts, and tool calls across repeated
  trials; they do not establish whether a cited source supports a claim.
  `test_search.py` remains a manual retrieval inspection script. Dependencies
  are currently unpinned.

## What This Project Demonstrates

- Scoping a private-markets operational task into a working local briefing
  application with concrete data requirements and example requests.
- Connecting a CLI, async agent orchestration and MCP tools across
  the application workflow.
- Designing context from two sources: deterministic financial records and
  retrieved investor documents, with source metadata preserved for inspection.
- Separating the agent workflow from citation presentation and future clients.
- Documenting setup, dataset coverage and limitations so another developer can
  run and inspect the prototype with their own credentials.

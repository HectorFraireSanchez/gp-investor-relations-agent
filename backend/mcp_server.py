import os

from backend import domain
from backend.paths import ENV_PATH
from dotenv import load_dotenv
from mcp.server import MCPServer
from openai import OpenAI


mcp = MCPServer("Northstar Investor Operations")

load_dotenv(ENV_PATH)

openai_client = OpenAI()
VECTOR_STORE_ID = os.environ["OPENAI_VECTOR_STORE_ID"]


def _with_database_source(record: dict, table: str, key_fields: tuple[str, ...]) -> dict:
    """Attach provenance using the actual returned record's identifying fields."""
    record_key = {field: record[field] for field in key_fields}
    source_id = f"db:{table}:" + ":".join(str(value) for value in record_key.values())
    return {
        "data": record,
        "sources": [
            {
                "source_id": source_id,
                "source_type": "database",
                "database": domain.DB_PATH.name,
                "schema": "main",
                "table": table,
                "record_key": record_key,
            }
        ],
    }


@mcp.tool()
def list_investors() -> list[dict]:
    """Enumerate all Northstar investor records with provenance for list/browse requests.

    For a particular investor named by the user, use find_investor instead.
    """
    return [
        _with_database_source(record, "investors", ("investor_id",))
        for record in domain.list_investors()
    ]


@mcp.tool()
def find_investor(name: str) -> dict:
    """Resolve one investor by name, returning data and source provenance.

    Use the returned data.investor_id for get_positions and get_capital_calls.
    """
    record = domain.find_investor(name)
    if record is None:
        return {"data": None, "sources": []}
    return _with_database_source(record, "investors", ("investor_id",))


@mcp.tool()
def get_positions(investor_id: str) -> list[dict]:
    """Get an investor's fund positions, each with data and source provenance."""
    return [
        _with_database_source(record, "positions", ("investor_id", "fund"))
        for record in domain.get_positions(investor_id)
    ]


@mcp.tool()
def get_capital_calls(investor_id: str) -> list[dict]:
    """Get an investor's capital calls, each with data and source provenance."""
    return [
        _with_database_source(record, "capital_calls", ("call_id",))
        for record in domain.get_capital_calls(investor_id)
    ]

@mcp.tool()
def search_investor_documents(
    investor_name: str,
    query: str,
) -> list[dict]:
    """
    Search documents for information about a specific investor.

    Use this for unstructured information such as side-letter terms,
    meeting notes, reporting requirements, and fund-report context.
    Each result contains retrieved data and document source provenance.
    """

    search_query = f"{investor_name}: {query}"

    response = openai_client.vector_stores.search(
        vector_store_id=VECTOR_STORE_ID,
        query=search_query,
    )

    results = []

    investor_keyword = investor_name.split()[0].lower()

    for item in response.data:
        filename = item.filename

        # Restrict returned documents to files whose filename corresponds to the investor.
        if investor_keyword not in filename.lower():
            continue

        text_parts = []

        for content in item.content:
            if hasattr(content, "text"):
                text_parts.append(content.text)

        results.append(
            {
                "data": {
                    "file_id": item.file_id,
                    "filename": filename,
                    "score": item.score,
                    "text": "\n".join(text_parts),
                },
                "sources": [
                    {
                        "source_id": f"doc:{filename}",
                        "source_type": "document",
                        "filename": filename,
                        "file_id": item.file_id,
                    }
                ],
            }
        )

        if len(results) == 3:
            break

    return results


if __name__ == "__main__":
    mcp.run()

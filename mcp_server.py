import os
from pathlib import Path

import domain
from dotenv import load_dotenv
from mcp.server import MCPServer
from openai import OpenAI


mcp = MCPServer("Northstar Investor Operations")

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

openai_client = OpenAI()
VECTOR_STORE_ID = os.environ["OPENAI_VECTOR_STORE_ID"]


@mcp.tool()
def find_investor(name: str) -> dict | None:
    """Find an investor by name."""
    return domain.find_investor(name)


@mcp.tool()
def get_positions(investor_id: str) -> list[dict]:
    """Get an investor's fund positions."""
    return domain.get_positions(investor_id)


@mcp.tool()
def get_capital_calls(investor_id: str) -> list[dict]:
    """Get an investor's capital calls."""
    return domain.get_capital_calls(investor_id)

@mcp.tool()
def search_investor_documents(
    investor_name: str,
    query: str,
) -> list[dict]:
    """
    Search documents for information about a specific investor.

    Use this for unstructured information such as side-letter terms,
    meeting notes, reporting requirements, and fund-report context.
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
                "file_id": item.file_id,
                "filename": filename,
                "score": item.score,
                "text": "\n".join(text_parts),
            }
        )

        if len(results) == 3:
            break

    return results


if __name__ == "__main__":
    mcp.run()
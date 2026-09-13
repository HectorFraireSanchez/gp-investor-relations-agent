"""Local CLI for generating a briefing with numbered source references."""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from backend.paths import ENV_PATH
from backend.service import generate_briefing
from backend.setup_documents import ensure_vector_store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="+", help="Investor question or meeting-preparation request")
    args = parser.parse_args(argv)
    prompt = " ".join(args.prompt)
    if not prompt.strip():
        parser.error("prompt must not be empty")

    load_dotenv(ENV_PATH)
    try:
        ensure_vector_store()
        result = asyncio.run(generate_briefing(prompt))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(result.answer)
    if result.citations:
        print("\nSources")
        for citation in result.citations:
            print(f"[{citation['number']}] {citation['source_id']}")
    if result.invalid_source_ids:
        print("Unavailable citations: " + ", ".join(result.invalid_source_ids), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

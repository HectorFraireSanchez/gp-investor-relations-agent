import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


def main():
    load_dotenv(Path(__file__).parent / ".env")
    client = OpenAI()

    vector_store_id = os.environ["OPENAI_VECTOR_STORE_ID"]

    response = client.vector_stores.search(
        vector_store_id=vector_store_id,
        query="What special reporting obligations does Beacon have?"
    )

    for result in response.data:
        print("=" * 60)
        print(f"File: {result.filename}")
        print(f"Score: {result.score}")

        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)


if __name__ == "__main__":
    main()

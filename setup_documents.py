import os
from pathlib import Path

from dotenv import load_dotenv, set_key
from openai import NotFoundError, OpenAI


ROOT_DIR = Path(__file__).parent
DOCUMENTS_DIR = ROOT_DIR / "documents"
ENV_PATH = ROOT_DIR / ".env"

load_dotenv(ENV_PATH)


def ensure_vector_store() -> str:
    client = OpenAI()

    existing_id = os.environ.get("OPENAI_VECTOR_STORE_ID")

    if existing_id:
        try:
            client.vector_stores.retrieve(existing_id)
            print(f"Using existing vector store: {existing_id}")
            return existing_id

        except NotFoundError:
            print(
                "Configured vector store no longer exists. "
                "Creating a new one..."
            )

    vector_store = client.vector_stores.create(
        name="Northstar Investor Documents"
    )

    for file_path in DOCUMENTS_DIR.iterdir():
        if not file_path.is_file():
            continue

        with file_path.open("rb") as file_handle:
            uploaded_file = client.vector_stores.files.upload_and_poll(
                vector_store_id=vector_store.id,
                file=file_handle,
            )

        if uploaded_file.status != "completed":
            raise RuntimeError(
                f"Document indexing did not complete for {file_path.name}: "
                f"{uploaded_file.status}"
            )

    ENV_PATH.touch(exist_ok=True)

    set_key(
        str(ENV_PATH),
        "OPENAI_VECTOR_STORE_ID",
        vector_store.id,
    )

    # Make the new value available immediately to this running process.
    os.environ["OPENAI_VECTOR_STORE_ID"] = vector_store.id

    return vector_store.id


def main():
    ensure_vector_store()


if __name__ == "__main__":
    main()

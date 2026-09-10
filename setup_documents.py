from pathlib import Path

from openai import OpenAI


DOCUMENTS_DIR = Path(__file__).parent / "documents"

client = OpenAI()


def main():
    vector_store = client.vector_stores.create(
        name="Northstar Investor Documents"
    )

    print(f"Created vector store: {vector_store.id}")

    for file_path in DOCUMENTS_DIR.iterdir():
        if not file_path.is_file():
            continue

        print(f"Uploading {file_path.name}...")

        with file_path.open("rb") as file_handle:
            client.vector_stores.files.upload_and_poll(
                vector_store_id=vector_store.id,
                file=file_handle,
            )

        print(f"Uploaded {file_path.name}")

    print()
    print("Document setup complete.")
    print(f"Vector store ID: {vector_store.id}")
    print()
    print("Set this in PowerShell with:")
    print(
        f'$env:OPENAI_VECTOR_STORE_ID = "{vector_store.id}"'
    )


if __name__ == "__main__":
    main()
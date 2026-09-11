import logging
import os
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv

from mcp_agent import run_agent
from setup_documents import ensure_vector_store


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


async def generate_briefing(prompt: str, progress=gr.Progress()):
    if not prompt.strip():
        return "Please enter a prompt before generating a briefing."

    if not all(
        os.environ.get(name)
        for name in ("OPENAI_API_KEY", "OPENAI_VECTOR_STORE_ID")
    ):
        return (
            "Missing OpenAI configuration. Add OPENAI_API_KEY to .env and run "
            "setup_documents.py to configure OPENAI_VECTOR_STORE_ID. "
            "See README.md for setup instructions."
        )

    progress(0, desc="Generating briefing...")
    try:
        result = await run_agent(prompt)
        return result.final_output
    except Exception:
        logging.exception("Briefing generation failed")
        return (
            "Unable to generate the briefing. Please check your local setup and "
            "connection, then try again. Details are available in the terminal."
        )


demo = gr.Interface(
    fn=generate_briefing,
    title="Northstar Investor Relations Assistant",
    description=(
        "Generate investor briefings from structured investor data and investor "
        "documents. Select an example below or enter your own prompt, then click "
        "Generate Briefing."
    ),
    inputs=gr.Textbox(
        label="Prompt",
        lines=5,
        value=(
            "Prepare me for a meeting with Redwood Family Office. Include its "
            "investment position, outstanding capital calls, special reporting "
            "obligations, and most recent meeting discussion."
        ),
    ),
    outputs=gr.Markdown(label="Response", show_label=True, container=True),
    examples=[
        ["Prepare me for a meeting with Redwood Family Office."],
        ["What outstanding capital calls does Redwood Family Office have?"],
        ["What special reporting obligations apply to Beacon University Endowment?"],
        ["What did Redwood Family Office discuss in its most recent meeting?"],
    ],
    cache_examples=False,
    submit_btn="Generate Briefing",
    clear_btn=None,
    flagging_mode="never",
    analytics_enabled=False,
)

with demo:
    with gr.Accordion("About the demo data", open=False):
        gr.Markdown(
            "Available investors are **Redwood Family Office**, "
            "**Beacon University Endowment**, and **Atlas Pension Fund**.\n\n"
            "All data is entirely synthetic. The demo combines structured "
            "investor/fund data stored in `data/northstar.db` with investor documents in "
            "`documents/`, including side letters and meeting notes.\n\n"
            "Document-derived responses include source filename citations so "
            "you can verify claims against the underlying files in `documents/`."
        )


def main():
    ensure_vector_store()

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=True,
    )


if __name__ == "__main__":
    main()

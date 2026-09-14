"""HTTP transport for the existing briefing service."""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.paths import ENV_PATH
from backend.mcp_agent import create_mcp_server
from backend.service import BriefingResult, generate_briefing
from backend.setup_documents import ensure_vector_store
from backend.timing import measure, timed, timing_scope

logger = logging.getLogger(__name__)
load_dotenv(ENV_PATH)


def get_cors_origins() -> list[str]:
    """Read an explicit, comma-separated backend allowlist at application startup."""
    return [origin.strip() for origin in os.environ.get(
        "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()]


def create_event_loop() -> asyncio.AbstractEventLoop:
    """Uvicorn loop factory that supports MCP subprocesses during Windows reload."""
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(ENV_PATH)
    # Finish the existing synchronous setup before accepting requests.
    with timing_scope(), measure("startup.documents"):
        await asyncio.to_thread(ensure_vector_store)
    # Enter and exit in the lifespan task: MCP's task groups belong to this task.
    async with create_mcp_server() as server:
        await server.list_tools()
        app.state.mcp_server = server
        try:
            yield
        finally:
            del app.state.mcp_server


app = FastAPI(title="Northstar Investor Intelligence", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


class BriefingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(strict=True, min_length=1, max_length=10000)
    conversation_id: str | None = Field(default=None, strict=True, min_length=1, max_length=256)

    @field_validator("conversation_id")
    @classmethod
    def reject_blank_conversation_id(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Conversation ID must not be blank")
        return value

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt must not be blank")
        return value


@app.post("/api/briefings")
@timed("api.total")
async def create_briefing(request: BriefingRequest, http_request: Request) -> BriefingResult:
    try:
        return await generate_briefing(
            request.prompt, conversation_id=request.conversation_id,
            mcp_server=http_request.app.state.mcp_server,
        )
    except Exception as exc:
        logger.exception("Briefing generation failed")
        raise HTTPException(
            status_code=502,
            detail="We couldn't generate your briefing. Please try again.",
        ) from exc

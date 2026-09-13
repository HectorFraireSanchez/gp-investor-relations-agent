"""HTTP transport for the existing briefing service."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.citations import RenderedResponse
from backend.paths import ENV_PATH
from backend.service import generate_briefing
from backend.setup_documents import ensure_vector_store

logger = logging.getLogger(__name__)


def create_event_loop() -> asyncio.AbstractEventLoop:
    """Uvicorn loop factory that supports MCP subprocesses during Windows reload."""
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop()
    return asyncio.new_event_loop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(ENV_PATH)
    # Finish the existing synchronous setup before accepting requests.
    await asyncio.to_thread(ensure_vector_store)
    yield


app = FastAPI(title="Northstar Investor Intelligence", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


class BriefingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(strict=True, min_length=1, max_length=10000)

    @field_validator("prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt must not be blank")
        return value


@app.post("/api/briefings")
async def create_briefing(request: BriefingRequest) -> RenderedResponse:
    try:
        return await generate_briefing(request.prompt)
    except Exception as exc:
        logger.exception("Briefing generation failed")
        raise HTTPException(
            status_code=502,
            detail="We couldn't generate your briefing. Please try again.",
        ) from exc

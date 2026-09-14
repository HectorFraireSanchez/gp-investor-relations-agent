"""Request-correlated elapsed timings without prompts, results, or credentials."""

import asyncio
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from time import perf_counter
from uuid import uuid4


logger = logging.getLogger("backend.timing")
# Uvicorn does not configure application INFO logs. Keep these on stderr, which
# also avoids corrupting stdio if a developer imports this from an MCP process.
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


@dataclass(frozen=True)
class TimingContext:
    request_id: str
    started: float


_context: ContextVar[TimingContext | None] = ContextVar("briefing_timing", default=None)


@contextmanager
def timing_scope():
    existing = _context.get()
    if existing is not None:
        yield existing
        return
    context = TimingContext(uuid4().hex, perf_counter())
    token = _context.set(context)
    try:
        yield context
    finally:
        _context.reset(token)


class StageTimer:
    def __init__(self, stage: str, **metadata):
        self.context = _context.get()
        self.stage = stage
        self.metadata = metadata
        self.operation_id = uuid4().hex
        self.started = perf_counter()
        self.finished = False
        self._emit("start")

    def _emit(self, event: str, **fields):
        if self.context is None:
            return
        logger.info(json.dumps({
            "event": "timing", "phase": event,
            "request_id": self.context.request_id,
            "operation_id": self.operation_id,
            "stage": self.stage,
            "offset_ms": round((perf_counter() - self.context.started) * 1000, 2),
            **self.metadata, **fields,
        }))

    def finish(self, status="ok", **fields):
        if self.finished:
            return
        self.finished = True
        self._emit("end", status=status,
                   duration_ms=round((perf_counter() - self.started) * 1000, 2), **fields)


@contextmanager
def measure(stage: str, **metadata):
    timer = StageTimer(stage, **metadata)
    try:
        yield timer
    except BaseException as exc:
        timer.finish("cancelled" if isinstance(exc, asyncio.CancelledError) else "error",
                     error_type=type(exc).__name__)
        raise
    else:
        timer.finish()


def timed(stage: str):
    def decorate(function):
        @wraps(function)
        async def wrapped(*args, **kwargs):
            with timing_scope(), measure(stage):
                return await function(*args, **kwargs)
        return wrapped
    return decorate

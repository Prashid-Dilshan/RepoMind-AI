import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from typing import Literal

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi import Path as ApiPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from utils import config, indexer, registry
from utils.errors import UserFacingError, friendly_error
from utils.github_loader import REPO_ID_PATTERN
from utils.rag_chain import ask_question, stream_answer
from utils.security import (
    SecurityHeadersMiddleware,
    limit_indexing,
    limit_questions,
    require_access,
)
from utils.vector_store import has_vector_store

log = logging.getLogger("repomind")


@asynccontextmanager
async def lifespan(_app):
    logging.basicConfig(
        level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    indexer.startup()
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY is not set. Indexing and questions will fail until it is.")
    if config.IS_PRODUCTION and not config.ACCESS_KEY:
        log.warning("ACCESS_KEY is not set: anyone who finds this URL can spend your OpenAI credit.")
    yield


app = FastAPI(
    title="RepoMind-AI",
    description="Ask questions about any public GitHub repository.",
    lifespan=lifespan,
    docs_url=None if config.IS_PRODUCTION else "/docs",
    redoc_url=None,
    openapi_url=None if config.IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Access-Key"],
)


@app.exception_handler(UserFacingError)
async def user_facing_error_handler(_request, exc: UserFacingError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


public = APIRouter(prefix="/api")
private = APIRouter(prefix="/api", dependencies=[Depends(require_access)])


# ---------- Request models ----------
class IndexRequest(BaseModel):
    repo_url: str = Field(min_length=1, max_length=300)
    force: bool = False


class HistoryItem(BaseModel):
    role: Literal["user", "ai", "assistant"]
    content: str = Field(max_length=8000)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_CHARS)
    repo_id: str = Field(pattern=REPO_ID_PATTERN)
    history: list[HistoryItem] = Field(default_factory=list, max_length=20)


# ---------- Public routes ----------
@public.get("/health")
def health():
    """Liveness: the process is up."""
    return {"ok": True}


def _checks():
    return {
        "openai_key_set": bool(os.getenv("OPENAI_API_KEY")),
        "git_installed": shutil.which("git") is not None,
        "data_dir_writable": os.access(config.DATA_DIR, os.W_OK),
    }


@public.get("/ready")
def ready():
    """Readiness: the server is configured well enough to do its job."""
    checks = _checks()
    ok = all(checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"ok": ok, **checks})


@public.get("/config")
def get_config():
    checks = _checks()
    return {
        "auth_required": bool(config.ACCESS_KEY),
        "openai_key_set": checks["openai_key_set"],
        "git_installed": checks["git_installed"],
        "max_question_chars": config.MAX_QUESTION_CHARS,
    }


# ---------- Protected routes ----------
@private.get("/auth/check")
def auth_check():
    return {"ok": True}


@private.get("/repos")
def list_repos():
    return {"repos": [indexer.public_repo(r) for r in registry.list_all()]}


@private.post("/repos", dependencies=[Depends(limit_indexing)])
def index_repository(request: IndexRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=500,
            detail="The server has no OPENAI_API_KEY. Add it to the server's environment and restart it.",
        )
    return indexer.enqueue(request.repo_url, force=request.force)


@private.get("/repos/{repo_id}")
def get_repo(repo_id: str = ApiPath(pattern=REPO_ID_PATTERN)):
    row = registry.get(repo_id)
    if not row:
        raise HTTPException(status_code=404, detail="Repository not found.")
    return indexer.public_repo(row)


@private.delete("/repos/{repo_id}")
def delete_repo(repo_id: str = ApiPath(pattern=REPO_ID_PATTERN)):
    if not registry.get(repo_id):
        raise HTTPException(status_code=404, detail="Repository not found.")
    indexer.delete_repo(repo_id)
    return {"ok": True}


def _require_indexed(repo_id):
    row = registry.get(repo_id)
    if not row or row["status"] != "completed" or not has_vector_store(repo_id):
        raise HTTPException(
            status_code=409,
            detail="This repository isn't indexed yet. Index it first, then ask your question.",
        )
    registry.touch(repo_id)
    return row


def _sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@private.post("/query/stream", dependencies=[Depends(limit_questions)])
def query_stream(request: QueryRequest):
    """Server-sent events: one `sources` event, many `token` events, then `done` (or `error`)."""
    row = _require_indexed(request.repo_id)
    history = [h.model_dump() for h in request.history]

    def events():
        try:
            for event in stream_answer(request.question, request.repo_id, history, row):
                yield _sse(event)
            yield _sse({"type": "done"})
        except Exception as exc:
            log.exception("Query failed for %s", request.repo_id)
            yield _sse({"type": "error", "message": friendly_error(exc)})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@private.post("/query", dependencies=[Depends(limit_questions)])
def query_repository(request: QueryRequest):
    """Same as /query/stream, but returns the whole answer as JSON."""
    row = _require_indexed(request.repo_id)
    history = [h.model_dump() for h in request.history]
    try:
        answer, sources = ask_question(request.question, request.repo_id, history, row)
    except Exception as exc:
        log.exception("Query failed for %s", request.repo_id)
        raise HTTPException(status_code=500, detail=friendly_error(exc))
    return {"answer": answer, "sources": sources}


app.include_router(public)
app.include_router(private)

# Serve the built frontend (npm run build in frontend/) from the same address as the API.
if config.STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("HOST", "localhost"),
        port=int(os.getenv("PORT", "8000")),
    )

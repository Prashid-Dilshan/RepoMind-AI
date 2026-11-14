"""Indexing pipeline: queue, live progress, clone -> read -> embed, and cleanup."""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from utils import registry
from utils.config import (
    CLONE_DIR,
    MAX_CHUNKS,
    MAX_CONCURRENT_INDEXING,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_REPOS,
    MAX_WAITING_INDEXING,
)
from utils.errors import ServerBusy, UserFacingError, friendly_error
from utils.file_loader import build_structure_document, load_files
from utils.fs import remove_dir
from utils.github_loader import clone_repo, fetch_repo_info, get_repo_id, normalize_repo_url, parse_repo_url
from utils.rag_chain import invalidate_cache
from utils.vector_store import create_vector_store, delete_vector_store, has_vector_store

log = logging.getLogger("repomind.indexer")

_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_INDEXING, thread_name_prefix="indexer")
_enqueue_lock = threading.Lock()
_live = {}
_live_lock = threading.Lock()


# ---------- Live progress (changes many times a second, so it stays in memory) ----------
def set_live(repo_id, **fields):
    with _live_lock:
        _live.setdefault(repo_id, {}).update(fields)


def get_live(repo_id):
    with _live_lock:
        return dict(_live.get(repo_id, {}))


def clear_live(repo_id):
    with _live_lock:
        _live.pop(repo_id, None)


def public_repo(row):
    """The JSON the frontend sees: database row merged with live progress."""
    live = get_live(row["repo_id"]) if row["status"] == "processing" else {}
    done = row["status"] == "completed"
    return {
        "repo_id": row["repo_id"],
        "url": row.get("url"),
        "name": row.get("name"),
        "description": row.get("description"),
        "language": row.get("language"),
        "stars": row.get("stars"),
        "default_branch": row.get("default_branch"),
        "status": row["status"],
        "stage": "ready" if done else (live.get("stage") or row.get("stage")),
        "message": live.get("message", ""),
        "error": row.get("error"),
        "note": row.get("note"),
        "files": live.get("files", row.get("files") or 0),
        "chunks_done": live.get("chunks_done", row.get("chunks") or 0),
        "chunks_total": live.get("chunks_total", row.get("chunks") or 0),
        "indexed_at": row.get("indexed_at"),
        "last_used_at": row.get("last_used_at"),
    }


# ---------- Lifecycle ----------
def startup():
    registry.init()
    registry.mark_interrupted()
    remove_dir(CLONE_DIR)  # leftovers from a crash; clones are temporary
    os.makedirs(CLONE_DIR, exist_ok=True)


def enqueue(repo_url, force=False):
    url = normalize_repo_url(repo_url)
    repo_id = get_repo_id(url)
    owner, name = parse_repo_url(url)

    existing = registry.get(repo_id)
    if existing:
        if existing["status"] == "processing":
            return public_repo(existing)
        if existing["status"] == "completed" and not force and has_vector_store(repo_id):
            registry.touch(repo_id)
            return public_repo(registry.get(repo_id))

    if registry.count_processing() >= MAX_CONCURRENT_INDEXING + MAX_WAITING_INDEXING:
        raise ServerBusy("The server is busy indexing other repositories. Try again in a few minutes.")

    info = fetch_repo_info(owner, name) or {}  # may raise RepoNotFound / RepoTooLarge

    with _enqueue_lock:
        existing = registry.get(repo_id)
        if existing and existing["status"] == "processing":
            return public_repo(existing)
        now = time.time()
        registry.upsert(
            repo_id,
            url=url,
            name=info.get("full_name") or f"{owner}/{name}",
            description=info.get("description"),
            language=info.get("language"),
            stars=info.get("stars"),
            default_branch=info.get("default_branch"),
            status="processing",
            stage="queued",
            error=None,
            note=None,
            files=0,
            chunks=0,
            created_at=(existing or {}).get("created_at") or now,
            last_used_at=now,
        )
        set_live(repo_id, stage="queued", message="Waiting for a free slot…",
                 files=0, chunks_done=0, chunks_total=0)
        _executor.submit(_run, url, repo_id)

    return public_repo(registry.get(repo_id))


def _run(url, repo_id):
    target = os.path.join(CLONE_DIR, repo_id)
    try:
        log.info("Indexing %s (%s)", url, repo_id)
        set_live(repo_id, stage="cloning", message="Cloning repository…")
        clone_repo(url, target)

        set_live(repo_id, stage="reading", message="Reading files…")
        docs, stats = load_files(target)
        if not docs:
            raise UserFacingError("No readable text files were found in this repository.")
        remove_dir(target)  # everything needed is in memory now

        file_count = len(docs)
        docs.append(build_structure_document([d.metadata["source"] for d in docs]))
        set_live(repo_id, files=file_count, stage="embedding", message="Building search index…")

        found, used = create_vector_store(
            docs, repo_id,
            on_progress=lambda done, total: set_live(repo_id, chunks_done=done, chunks_total=total),
        )
        invalidate_cache(repo_id)

        notes = []
        if stats["truncated"]:
            notes.append(f"Only the first {MAX_FILES:,} files were read.")
        if stats["skipped_large"]:
            notes.append(f"{stats['skipped_large']} files over {MAX_FILE_BYTES // 1000} KB were skipped.")
        if found > used:
            notes.append(f"Indexed {used:,} of {found:,} chunks (limit {MAX_CHUNKS:,}).")

        registry.upsert(
            repo_id, status="completed", stage="ready", error=None, note=" ".join(notes) or None,
            files=file_count, chunks=used, indexed_at=time.time(),
        )
        log.info("Indexed %s: %d files, %d chunks", repo_id, file_count, used)
        _evict_old()
    except Exception as exc:
        log.exception("Indexing failed for %s", repo_id)
        registry.upsert(
            repo_id, status="failed", stage=get_live(repo_id).get("stage"), error=friendly_error(exc)
        )
    finally:
        remove_dir(target)
        clear_live(repo_id)


def _evict_old():
    for repo_id in registry.evictable(MAX_REPOS):
        log.info("Removing least recently used index %s", repo_id)
        delete_repo(repo_id)


def delete_repo(repo_id):
    row = registry.get(repo_id)
    if row and row["status"] == "processing":
        raise UserFacingError("This repository is still being indexed. Wait for it to finish, then delete it.")
    invalidate_cache(repo_id)
    delete_vector_store(repo_id)
    remove_dir(os.path.join(CLONE_DIR, repo_id))
    registry.delete(repo_id)

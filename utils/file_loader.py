import os

from langchain_core.documents import Document

from utils.config import (
    EXCLUDED_DIRS,
    EXCLUDED_EXTENSIONS,
    EXCLUDED_FILES,
    EXCLUDED_SUFFIXES,
    MAX_FILE_BYTES,
    MAX_FILES,
)

STRUCTURE_SOURCE = "(repository structure)"


def _should_skip_file(name):
    lower = name.lower()
    if lower in EXCLUDED_FILES or lower.startswith(".env"):  # never index secrets
        return True
    if lower.endswith(EXCLUDED_SUFFIXES):
        return True
    return os.path.splitext(lower)[1] in EXCLUDED_EXTENSIONS


def _read_text(path):
    """Returns (text, reason_skipped)."""
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None, "large"
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None, "unreadable"
    if b"\x00" in raw[:4096]:
        return None, "binary"
    try:
        return raw.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return None, "binary"


def load_files(repo_path):
    """Read every useful text file. Returns (documents, stats)."""
    documents = []
    stats = {"skipped_large": 0, "truncated": False}

    for root, dirs, files in os.walk(repo_path):
        # Skip excluded folders and never follow symlinked folders.
        dirs[:] = sorted(
            d for d in dirs
            if d not in EXCLUDED_DIRS and not os.path.islink(os.path.join(root, d))
        )

        for name in sorted(files):
            if _should_skip_file(name):
                continue

            path = os.path.join(root, name)
            if os.path.islink(path):  # a symlink could point at files outside the repository
                continue

            text, reason = _read_text(path)
            if reason == "large":
                stats["skipped_large"] += 1
            if not text or not text.strip():
                continue

            source = os.path.relpath(path, repo_path).replace(os.sep, "/")
            documents.append(Document(page_content=text, metadata={"source": source}))

            if len(documents) >= MAX_FILES:
                stats["truncated"] = True
                return documents, stats

    return documents, stats


def build_structure_document(paths, limit=400):
    """A synthetic document listing the files, so questions about layout can be answered."""
    shown = paths[:limit]
    text = "Repository file structure (paths relative to the repository root):\n" + "\n".join(shown)
    if len(paths) > limit:
        text += f"\n... and {len(paths) - limit} more files"
    return Document(page_content=text, metadata={"source": STRUCTURE_SOURCE})

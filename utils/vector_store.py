import os
import re

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from utils.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL,
    MAX_CHUNKS,
    MAX_CHUNKS_PER_FILE,
    VECTORSTORE_DIR,
)
from utils.fs import remove_dir
from utils.github_loader import REPO_ID_PATTERN

_COMPLETE_MARKER = ".complete"

# File extension -> name of a langchain Language, so code is split at function/class boundaries.
_LANGUAGE_BY_EXT = {
    ".py": "PYTHON", ".js": "JS", ".jsx": "JS", ".mjs": "JS", ".cjs": "JS", ".ts": "TS", ".tsx": "TS",
    ".java": "JAVA", ".go": "GO", ".rs": "RUST", ".cpp": "CPP", ".cc": "CPP", ".cxx": "CPP",
    ".hpp": "CPP", ".c": "C", ".h": "C", ".cs": "CSHARP", ".php": "PHP", ".rb": "RUBY",
    ".swift": "SWIFT", ".kt": "KOTLIN", ".scala": "SCALA", ".md": "MARKDOWN", ".markdown": "MARKDOWN",
    ".html": "HTML", ".htm": "HTML", ".sol": "SOL", ".lua": "LUA", ".pl": "PERL", ".hs": "HASKELL",
}
_splitters = {}


def _splitter_for(source):
    ext = os.path.splitext(source)[1].lower()
    if ext in _splitters:
        return _splitters[ext]

    options = dict(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, add_start_index=True)
    language = getattr(Language, _LANGUAGE_BY_EXT.get(ext, ""), None)
    splitter = None
    if language is not None:
        try:
            splitter = RecursiveCharacterTextSplitter.from_language(language=language, **options)
        except Exception:
            splitter = None
    if splitter is None:
        splitter = RecursiveCharacterTextSplitter(**options)
    _splitters[ext] = splitter
    return splitter


def _persist_dir(repo_id):
    if not re.match(REPO_ID_PATTERN, repo_id or ""):
        raise ValueError("Invalid repository id.")
    return os.path.join(VECTORSTORE_DIR, repo_id)


def get_embeddings():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing. Add it to the server's environment and restart it.")
    return OpenAIEmbeddings(model=EMBEDDING_MODEL, api_key=api_key, max_retries=6)


def has_vector_store(repo_id):
    """True only for stores that finished building (a crash mid-way leaves no marker)."""
    return os.path.exists(os.path.join(_persist_dir(repo_id), _COMPLETE_MARKER))


def delete_vector_store(repo_id):
    persist_dir = _persist_dir(repo_id)
    remove_dir(persist_dir)
    if os.path.exists(persist_dir):  # Windows can keep Chroma files locked
        try:
            Chroma(persist_directory=persist_dir, embedding_function=get_embeddings()).delete_collection()
        except Exception:
            pass
        marker = os.path.join(persist_dir, _COMPLETE_MARKER)
        if os.path.exists(marker):
            os.remove(marker)


def _split(documents):
    chunks = []
    for doc in documents:
        source = doc.metadata.get("source", "")
        pieces = _splitter_for(source).split_documents([doc])[:MAX_CHUNKS_PER_FILE]
        for piece in pieces:
            if not piece.page_content.strip():
                continue
            start = piece.metadata.pop("start_index", -1)
            if isinstance(start, int) and start >= 0:
                start_line = doc.page_content.count("\n", 0, start) + 1
                end_line = start_line + piece.page_content.count("\n")
            else:
                start_line = end_line = 0  # 0 means unknown
            piece.metadata["start_line"] = start_line
            piece.metadata["end_line"] = end_line
            # Put the path inside the chunk so the model (and the search) can see where it came from.
            piece.page_content = f"File: {source}\n{piece.page_content}"
            chunks.append(piece)
    return chunks


def create_vector_store(documents, repo_id, on_progress=None):
    """Split, embed and store documents. Returns (chunks_found, chunks_indexed)."""
    chunks = _split(documents)
    found = len(chunks)
    chunks = chunks[:MAX_CHUNKS]
    total = len(chunks)

    embeddings = get_embeddings()
    delete_vector_store(repo_id)
    persist_dir = _persist_dir(repo_id)
    os.makedirs(persist_dir, exist_ok=True)

    db = Chroma(persist_directory=persist_dir, embedding_function=embeddings)

    if on_progress:
        on_progress(0, total)
    for start in range(0, total, EMBEDDING_BATCH_SIZE):
        db.add_documents(chunks[start:start + EMBEDDING_BATCH_SIZE])
        if on_progress:
            on_progress(min(start + EMBEDDING_BATCH_SIZE, total), total)

    with open(os.path.join(persist_dir, _COMPLETE_MARKER), "w") as marker:
        marker.write("ok")
    return found, total


def load_vector_store(repo_id):
    if not has_vector_store(repo_id):
        raise FileNotFoundError("This repository isn't indexed yet.")
    return Chroma(persist_directory=_persist_dir(repo_id), embedding_function=get_embeddings())

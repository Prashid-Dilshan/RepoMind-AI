"""All settings live here. Every value can be overridden with an environment variable (or the .env file)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env here so every module sees the same settings, whatever folder you start the server from.
# Real environment variables always win over the .env file.
load_dotenv(BASE_DIR / ".env")


def _int(name, default, minimum=0):
    try:
        return max(minimum, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def _list(name, default):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# ---------- Environment ----------
APP_ENV = os.getenv("APP_ENV", "development").lower()  # set to "production" when deployed
IS_PRODUCTION = APP_ENV == "production"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ---------- Paths ----------
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data")).resolve()
CLONE_DIR = DATA_DIR / "clones"            # temporary; emptied after every indexing run
VECTORSTORE_DIR = DATA_DIR / "vectorstores"
DB_PATH = DATA_DIR / "repomind.db"
STATIC_DIR = BASE_DIR / "static"           # created by `npm run build` in frontend/

CLONE_DIR.mkdir(parents=True, exist_ok=True)
VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Access and abuse protection ----------
ACCESS_KEY = os.getenv("ACCESS_KEY", "").strip()  # empty = anyone can use the app
CORS_ORIGINS = _list("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000")
RATE_LIMIT_INDEX_PER_HOUR = _int("RATE_LIMIT_INDEX_PER_HOUR", 20)   # 0 disables
RATE_LIMIT_QUERY_PER_MINUTE = _int("RATE_LIMIT_QUERY_PER_MINUTE", 30)  # 0 disables
MAX_QUESTION_CHARS = 4000

# ---------- Indexing limits (keep OpenAI cost, disk and time predictable) ----------
MAX_CONCURRENT_INDEXING = _int("MAX_CONCURRENT_INDEXING", 2, minimum=1)
MAX_WAITING_INDEXING = _int("MAX_WAITING_INDEXING", 8)
MAX_REPOS = _int("MAX_REPOS", 30, minimum=1)                  # least recently used indexes are removed beyond this
MAX_REPO_SIZE_MB = _int("MAX_REPO_SIZE_MB", 300, minimum=1)
CLONE_TIMEOUT_SECONDS = _int("CLONE_TIMEOUT_SECONDS", 180, minimum=10)
MAX_FILES = _int("MAX_FILES", 1500, minimum=1)
MAX_FILE_BYTES = _int("MAX_FILE_BYTES", 150_000, minimum=1000)
MAX_CHUNKS = _int("MAX_CHUNKS", 4000, minimum=10)
MAX_CHUNKS_PER_FILE = _int("MAX_CHUNKS_PER_FILE", 40, minimum=1)

# Optional: raises GitHub's API rate limit (60 -> 5000 requests/hour). Only used for repo metadata, never for cloning.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()

# ---------- Chunking and retrieval ----------
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
TOP_K = 6

# ---------- Models ----------
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LANGUAGE_MODEL = os.getenv("LANGUAGE_MODEL", "gpt-4o-mini")
MAX_NEW_TOKENS = _int("MAX_NEW_TOKENS", 1500, minimum=100)
TEMPERATURE = 0.2
EMBEDDING_BATCH_SIZE = 100

# ---------- What to skip ----------
EXCLUDED_DIRS = {
    ".git", "node_modules", "__pycache__", "dist", "build", "venv",
    ".venv", "env", ".env_vars", "target", "bin", "obj", ".idea", ".vscode",
    ".next", "coverage", "vendor", "third_party",
}

# Lock files are huge and useless for Q&A.
EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "pipfile.lock", "composer.lock", "cargo.lock", "go.sum", "gradle.lockfile",
}

EXCLUDED_SUFFIXES = (".min.js", ".min.css", ".map", ".lock")

EXCLUDED_EXTENSIONS = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    # Media
    ".mp3", ".mp4", ".mov", ".avi", ".wav",
    # Archives
    ".zip", ".tar", ".gz", ".7z", ".rar",
    # Binaries / compiled
    ".exe", ".dll", ".so", ".bin", ".pyc", ".pyd", ".o", ".a", ".lib", ".jar", ".class",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Documents and models
    ".pdf", ".docx", ".pptx", ".xlsx", ".pt", ".pth", ".h5", ".onnx", ".npy", ".npz",
    # Data / large
    ".csv", ".sqlite", ".db", ".parquet", ".pickle", ".pkl",
}

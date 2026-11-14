import hashlib
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request

from utils.config import CLONE_TIMEOUT_SECONDS, GITHUB_TOKEN, MAX_REPO_SIZE_MB
from utils.errors import CloneFailed, InvalidRepoURL, RepoNotFound, RepoTooLarge
from utils.fs import dir_size_bytes, remove_dir

_GITHUB_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
)
REPO_ID_PATTERN = r"^[a-f0-9]{10}$"


def parse_repo_url(repo_url):
    """Return (owner, name) for any github.com repository link, or raise InvalidRepoURL."""
    url = (repo_url or "").strip().split("#")[0].split("?")[0]
    match = _GITHUB_RE.match(url)
    if not match or match.group(1) in (".", "..") or match.group(2) in (".", ".."):
        raise InvalidRepoURL(
            "Enter a public GitHub repository URL, for example https://github.com/owner/repo."
        )
    return match.group(1), match.group(2)


def normalize_repo_url(repo_url):
    owner, name = parse_repo_url(repo_url)
    return f"https://github.com/{owner}/{name}.git"


def get_repo_id(repo_url):
    return hashlib.md5(normalize_repo_url(repo_url).lower().encode()).hexdigest()[:10]


def fetch_repo_info(owner, name):
    """Ask GitHub about the repo before cloning.

    Raises RepoNotFound / RepoTooLarge for clear problems. Returns None when GitHub can't be asked
    (rate limit, network): cloning then goes ahead without the extra metadata.
    """
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoMind-AI"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    request = urllib.request.Request(f"https://api.github.com/repos/{owner}/{name}", headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RepoNotFound(
                "Repository not found. It may be private, or the URL may be misspelled."
            ) from exc
        return None
    except Exception:
        return None

    if data.get("private"):
        raise RepoNotFound("This repository is private. Only public repositories are supported.")

    size_mb = (data.get("size") or 0) / 1024
    if size_mb > MAX_REPO_SIZE_MB:
        raise RepoTooLarge(
            f"This repository is about {size_mb:,.0f} MB, over the {MAX_REPO_SIZE_MB} MB limit."
        )

    return {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "language": data.get("language"),
        "stars": data.get("stargazers_count"),
        "default_branch": data.get("default_branch"),
    }


def _explain_clone_failure(stderr):
    low = stderr.lower()
    if any(k in low for k in (
        "repository not found", "could not read username", "terminal prompts disabled",
        "authentication failed", "not found",
    )):
        return "Couldn't clone this repository. It may be private, or the URL may be misspelled."
    if any(k in low for k in ("could not resolve host", "unable to access", "timed out", "connection")):
        return "The server couldn't reach GitHub. Try again in a minute."
    last_line = (stderr.strip().splitlines() or ["unknown error"])[-1][:200]
    return f"Git couldn't clone the repository: {last_line}"


def clone_repo(url, target):
    """Shallow-clone a public repository into `target` using the git command line."""
    git = shutil.which("git")
    if not git:
        raise CloneFailed("Git isn't installed on the server. Install Git and restart the backend.")

    remove_dir(target)
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",     # fail at once instead of waiting for a password
        "GIT_ALLOW_PROTOCOL": "https",  # no file://, ssh:// or ext:: tricks
        "GIT_LFS_SKIP_SMUDGE": "1",     # don't download large LFS files
    }
    command = [
        git, "-c", "core.symlinks=false", "clone",
        "--depth", "1", "--single-branch", "--no-tags", "--quiet", "--", url, target,
    ]

    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=CLONE_TIMEOUT_SECONDS, env=env
        )
    except subprocess.TimeoutExpired as exc:
        remove_dir(target)
        raise CloneFailed(
            f"Cloning took longer than {CLONE_TIMEOUT_SECONDS} seconds. The repository may be too large."
        ) from exc

    if result.returncode != 0:
        remove_dir(target)
        raise CloneFailed(_explain_clone_failure(result.stderr or ""))

    size_mb = dir_size_bytes(target) / (1024 * 1024)
    if size_mb > MAX_REPO_SIZE_MB:
        remove_dir(target)
        raise RepoTooLarge(
            f"This repository is about {size_mb:,.0f} MB, over the {MAX_REPO_SIZE_MB} MB limit."
        )

# RepoMind-AI

Paste a public GitHub repository URL, let RepoMind index it, then ask questions about the code. Answers stream in live and cite the exact excerpts they came from, with links to the lines on GitHub.

## Features

- **Streaming answers** with a Stop button, Regenerate, Copy, and conversation export to Markdown.
- **Sources you can verify:** every answer lists the files and line ranges it used, links to GitHub, and shows the excerpts.
- **Follow-up questions work:** the search query is rewritten using the conversation so "explain that more" finds the right code.
- **Code-aware indexing:** code is split at function and class boundaries, and a file-tree overview is indexed so layout questions work.
- **Live indexing progress** (clone, read, embed) with a queue, so several people can index at once.
- **Repositories persist** across restarts. Least recently used ones are removed past a limit, and you can delete any of them.
- **Light and dark themes**, mobile layout, keyboard shortcuts (`/` focuses the question box, `Esc` stops an answer).
- **Safe to host:** optional access key, rate limits, request validation, security headers, symlink and secret-file protection, size and time limits.

## Run it locally

Requires Python 3.10+, Node 20.19+ (or 22+), and **Git** (`git --version` must work).

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
# open .env and paste your OPENAI_API_KEY
python main.py
```

```bash
# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In development Vite forwards `/api` to the backend on port 8000, so there is nothing to configure.

`http://localhost:8000/docs` shows the API documentation (development only). `http://localhost:8000/api/ready` tells you if the server is configured correctly.

## Run it in production

See [DEPLOYMENT.md](DEPLOYMENT.md). The short version:

```bash
cp .env.example .env     # set OPENAI_API_KEY and ACCESS_KEY
docker compose up -d --build
```

Then open http://localhost:8000.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## What the error messages mean

| Message | Fix |
| --- | --- |
| Can't reach the server | Start `python main.py` and keep that terminal open. |
| The server has no OPENAI_API_KEY | Add it to `.env` (or the host's environment variables) and restart. |
| OpenAI rejected the API key | The key is wrong or revoked. Create a new one. |
| The OpenAI account is out of credit | Add credit in the OpenAI dashboard. |
| Couldn't clone this repository | The repository is private or the URL is misspelled. Only public GitHub repositories work. |
| Too many requests | A rate limit was hit. Wait the number of seconds shown. |
| Enter the access key | The server is protected. Ask the owner for the key. |

The real error is always in the server log.

## Limits

To keep cost and time predictable, the defaults are: 300 MB per repository, 1,500 files (each under 150 KB), 4,000 chunks, and 30 repositories kept. Lock files, minified files, binaries and `.env` files are skipped. Every limit can be changed with an environment variable. See `.env.example`.

## Project layout

```
main.py              API routes, middleware, static file serving
utils/
  config.py          every setting (environment variables)
  indexer.py         queue, progress, clone -> read -> embed pipeline
  github_loader.py   URL parsing, GitHub metadata, safe shallow clone
  file_loader.py     reads useful text files, skips noise and symlinks
  vector_store.py    code-aware chunking, embeddings, Chroma storage
  rag_chain.py       search, follow-up rewriting, streaming answers
  registry.py        SQLite list of repositories
  security.py        access key, rate limits, security headers
frontend/            React + Vite app
tests/               pytest suite
Dockerfile, docker-compose.yml, render.yaml, .github/workflows/ci.yml
```

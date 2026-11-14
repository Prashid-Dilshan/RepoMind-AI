# Deploying RepoMind-AI

RepoMind is one container: the Python backend also serves the built React app, so there is a single address to expose.

## Before you go live

1. **Set `ACCESS_KEY`** to a long random string. Without it, anyone who finds the URL can spend your OpenAI credit. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. **Set a monthly spending limit** in the OpenAI dashboard (Settings, Limits). This is your real safety net.
3. **Use a new OpenAI key** that has never been shared or committed.
4. **Serve it over HTTPS** (every option below does this for you or shows how).
5. **Keep one worker.** Indexing progress lives in the memory of one process. The Dockerfile already does this.
6. **Mount a persistent volume at `/data`.** It holds the SQLite registry and the search indexes. Without it, everything is lost when the container is replaced.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | none (required) | Embeddings and answers. |
| `ACCESS_KEY` | empty | Shared password for the app. Empty means open to everyone. |
| `APP_ENV` | `development` | Set `production` to hide API docs and use generic error text. |
| `DATA_DIR` | `./data` (`/data` in Docker) | Where indexes are stored. |
| `PORT` | `8000` | Port to listen on. Hosts like Render set this for you. |
| `CORS_ORIGINS` | localhost dev origins | Only needed if the frontend is hosted on a different domain. |
| `LANGUAGE_MODEL` / `EMBEDDING_MODEL` | `gpt-4o-mini` / `text-embedding-3-small` | Models to use. |
| `RATE_LIMIT_INDEX_PER_HOUR` | `20` | Per IP address. `0` disables. |
| `RATE_LIMIT_QUERY_PER_MINUTE` | `30` | Per IP address. `0` disables. |
| `MAX_CONCURRENT_INDEXING` | `2` | Repositories indexed at the same time. |
| `MAX_REPOS` | `30` | Least recently used indexes are removed beyond this. |
| `MAX_REPO_SIZE_MB` | `300` | Larger repositories are refused. |
| `MAX_FILES`, `MAX_FILE_BYTES`, `MAX_CHUNKS` | `1500`, `150000`, `4000` | Per-repository limits. |
| `GITHUB_TOKEN` | empty | Optional. Raises GitHub's API rate limit for metadata lookups. |
| `LOG_LEVEL` | `INFO` | Python log level. |

## Option A: Docker on any server (VPS)

On a Linux server with Docker installed:

```bash
git clone <your-repo-url> repomind && cd repomind
cp .env.example .env        # fill in OPENAI_API_KEY and ACCESS_KEY, keep APP_ENV=production
docker compose up -d --build
docker compose logs -f
```

The app is now on port 8000. For HTTPS, put Caddy in front of it. Point a DNS `A` record for your domain at the server, then add this to `docker-compose.yml`:

```yaml
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy-data:/data
    depends_on: [repomind]
    restart: unless-stopped
```

Add `caddy-data:` under `volumes:`, remove the `ports:` entry from the `repomind` service (so only Caddy is public), and create `Caddyfile`:

```
repomind.example.com {
    reverse_proxy repomind:8000 {
        flush_interval -1
    }
}
```

`flush_interval -1` keeps answers streaming instead of arriving in one piece. Caddy gets and renews the HTTPS certificate on its own.

Update later with `git pull && docker compose up -d --build`. Your indexes stay in the `repomind-data` volume.

## Option B: Render

1. Push the project to GitHub.
2. In Render choose New, then Blueprint, and pick the repository. It reads `render.yaml`.
3. Enter `OPENAI_API_KEY` and `ACCESS_KEY` when asked.
4. The persistent disk requires a paid instance type (the blueprint uses `starter`). On the free tier the disk is missing, so indexes disappear on every deploy.

Render provides HTTPS and sets `PORT` automatically. Health checks use `/api/health`.

## Option C: Railway, Fly.io and similar

Any host that builds a Dockerfile works. Create a service from the repository, add a volume mounted at `/data`, set the environment variables above, and make sure the instance runs a single replica.

## Operating it

- **Health:** `GET /api/health` (is it running) and `GET /api/ready` (is it configured: OpenAI key, Git, writable data folder).
- **Logs:** everything goes to stdout, so `docker compose logs -f` or your host's log viewer shows it. Each indexing failure prints a full traceback.
- **Backups:** the whole state is the `/data` volume. Copy it, or skip backups, since any repository can be re-indexed.
- **Cost:** indexing a typical repository costs a fraction of a cent in embeddings. Answers cost a little more per question. The rate limits and per-repository caps bound the worst case.
- **Updating dependencies:** after a first successful run, `pip freeze > requirements.lock.txt` records exact versions. Use that file in the Dockerfile if you want identical builds every time.
- **Scaling:** one process handles a small team comfortably. If you need several instances, move indexing progress and the rate limiter out of memory first (for example to Redis) and share the data volume.

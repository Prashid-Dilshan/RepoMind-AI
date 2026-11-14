import logging
from urllib.parse import quote

from langchain_core.messages import AIMessage, HumanMessage

from utils.config import TOP_K
from utils.llm import get_llm
from utils.prompt import condense_prompt, prompt
from utils.vector_store import load_vector_store

log = logging.getLogger("repomind.rag")

_retrievers = {}
_HISTORY_MESSAGES = 6
_HISTORY_CHARS = 1500


def invalidate_cache(repo_id):
    _retrievers.pop(repo_id, None)


def _get_retriever(repo_id):
    if repo_id not in _retrievers:
        _retrievers[repo_id] = load_vector_store(repo_id).as_retriever(
            search_type="mmr",  # mixes relevance with variety, so answers draw on more than one file
            search_kwargs={"k": TOP_K, "fetch_k": TOP_K * 4},
        )
    return _retrievers[repo_id]


def _clean_history(history):
    items = []
    for item in (history or [])[-_HISTORY_MESSAGES:]:
        role = item.get("role")
        content = str(item.get("content", ""))[:_HISTORY_CHARS]
        if content and role in ("user", "ai", "assistant"):
            items.append(("user" if role == "user" else "ai", content))
    return items


def _to_messages(history):
    return [
        HumanMessage(content=text) if role == "user" else AIMessage(content=text)
        for role, text in _clean_history(history)
    ]


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some model versions return a list of content parts
        return "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return ""


def _standalone_question(question, history):
    """Rewrite follow-ups ("explain that more") so the search has something to match."""
    items = _clean_history(history)
    if not items:
        return question
    transcript = "\n".join(f"{'User' if r == 'user' else 'Assistant'}: {t}" for r, t in items)
    try:
        reply = get_llm().invoke(condense_prompt.format(history=transcript, question=question))
        rewritten = _text(reply.content).strip()
        return rewritten[:500] or question
    except Exception:
        log.warning("Could not rewrite the follow-up question; using the original.", exc_info=True)
        return question


def _github_url(repo, path, start, end):
    if not repo or not repo.get("name") or not repo.get("default_branch") or path.startswith("("):
        return None
    url = f"https://github.com/{repo['name']}/blob/{repo['default_branch']}/{quote(path)}"
    if start and end and end > start:
        return f"{url}#L{start}-L{end}"
    return f"{url}#L{start}" if start else url


def _source_entry(doc, repo):
    meta = doc.metadata
    path = meta.get("source", "")
    start = int(meta.get("start_line") or 0)
    end = int(meta.get("end_line") or 0)
    text = doc.page_content
    if text.startswith("File: ") and "\n" in text:
        text = text.split("\n", 1)[1]
    return {
        "path": path,
        "start_line": start or None,
        "end_line": end or None,
        "snippet": text[:600],
        "url": _github_url(repo, path, start, end),
    }


def stream_answer(question, repo_id, history=None, repo=None):
    """Yield {"type": "sources"} once, then {"type": "token"} events as the answer is written."""
    search_text = _standalone_question(question, history)
    docs = _get_retriever(repo_id).invoke(search_text)
    yield {"type": "sources", "sources": [_source_entry(d, repo) for d in docs]}

    context = "\n\n---\n\n".join(d.page_content for d in docs)
    messages = prompt.format_messages(
        context=context, chat_history=_to_messages(history), input=question
    )
    for chunk in get_llm().stream(messages):
        text = _text(chunk.content)
        if text:
            yield {"type": "token", "text": text}


def ask_question(question, repo_id, history=None, repo=None):
    """Non-streaming version of stream_answer. Returns (answer, sources)."""
    answer, sources = [], []
    for event in stream_answer(question, repo_id, history, repo):
        if event["type"] == "sources":
            sources = event["sources"]
        else:
            answer.append(event["text"])
    return "".join(answer), sources

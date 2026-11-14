import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Sidebar from './components/Sidebar.jsx';
import Chat from './components/Chat.jsx';
import AccessGate from './components/AccessGate.jsx';
import {
  deleteRepo,
  getConfig,
  getRepo,
  listRepos,
  setAccessKey,
  setUnauthorizedHandler,
  startIndex,
  streamAnswer,
} from './lib/api.js';
import { exportChat } from './lib/exportChat.js';
import { readJSON, readText, removeKey, writeJSON, writeText } from './lib/storage.js';
import { applyTheme, initialTheme } from './lib/theme.js';
import './App.css';

const KEYS = {
  active: 'repomind.active',
  chats: 'repomind.chats.v2',
  access: 'repomind.access',
};
const GITHUB_URL = /github\.com\/[\w.-]+\/[\w.-]+/i;
const NO_MESSAGES = [];
const MAX_SAVED_MESSAGES = 40;

function loadChats() {
  const raw = readJSON(KEYS.chats, {});
  const clean = {};
  for (const [id, list] of Object.entries(raw)) {
    if (Array.isArray(list)) clean[id] = list.map((m) => ({ ...m, streaming: false }));
  }
  return clean;
}

export default function App() {
  const [config, setConfig] = useState(null);
  const [bootError, setBootError] = useState('');
  const [locked, setLocked] = useState(false);
  const [repos, setRepos] = useState([]);
  const [activeId, setActiveId] = useState(() => readText(KEYS.active));
  const [repoUrl, setRepoUrl] = useState('');
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [chats, setChats] = useState(loadChats);
  const [asking, setAsking] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [connectionLost, setConnectionLost] = useState(false);
  const [theme, setTheme] = useState(initialTheme);
  const abortRef = useRef(null);

  const repo = useMemo(() => repos.find((r) => r.repo_id === activeId) ?? null, [repos, activeId]);
  const messages = repo ? (chats[repo.repo_id] ?? NO_MESSAGES) : NO_MESSAGES;

  // ---------- Loading ----------
  const loadRepos = useCallback(async () => {
    const list = await listRepos();
    setRepos(list);
    setConnectionLost(false);
    const saved = readText(KEYS.active);
    const active = list.find((r) => r.repo_id === saved);
    if (active) setRepoUrl((current) => current || active.url);
    else setActiveId(null);
    return list;
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      removeKey(KEYS.access);
      setAccessKey('');
      setLocked(true);
    });

    let cancelled = false;
    (async () => {
      try {
        const cfg = await getConfig();
        if (cancelled) return;
        setConfig(cfg);
        if (cfg.auth_required) {
          const stored = readText(KEYS.access);
          if (!stored) {
            setLocked(true);
            return;
          }
          setAccessKey(stored);
        }
        await loadRepos();
      } catch (err) {
        if (!cancelled && err.status !== 401) setBootError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadRepos]);

  const unlock = async (key) => {
    writeText(KEYS.access, key);
    setAccessKey(key);
    setLocked(false);
    try {
      await loadRepos();
    } catch (err) {
      setBootError(err.message);
    }
  };

  // ---------- Persistence ----------
  useEffect(() => {
    if (activeId) writeText(KEYS.active, activeId);
    else removeKey(KEYS.active);
  }, [activeId]);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const known = new Set(repos.map((r) => r.repo_id));
      const out = {};
      for (const [id, list] of Object.entries(chats)) {
        if (repos.length && !known.has(id)) continue;
        out[id] = list.slice(-MAX_SAVED_MESSAGES).map((m) => ({
          role: m.role,
          content: m.content,
          sources: m.sources,
          isError: m.isError,
          stopped: m.stopped,
        }));
      }
      writeJSON(KEYS.chats, out);
    }, 500);
    return () => clearTimeout(timer);
  }, [chats, repos]);

  // ---------- Progress polling (every repo that is still indexing) ----------
  const processingKey = repos
    .filter((r) => r.status === 'processing')
    .map((r) => r.repo_id)
    .join(',');

  useEffect(() => {
    if (!processingKey || locked) return undefined;
    let cancelled = false;
    let failures = 0;

    const tick = async () => {
      try {
        const results = await Promise.all(
          processingKey.split(',').map((id) =>
            getRepo(id).catch((err) => {
              if (err.status === 404) return { repo_id: id, gone: true };
              throw err;
            }),
          ),
        );
        if (cancelled) return;
        failures = 0;
        setConnectionLost(false);
        setRepos((prev) =>
          prev
            .filter((r) => !results.some((x) => x.gone && x.repo_id === r.repo_id))
            .map((r) => results.find((x) => !x.gone && x.repo_id === r.repo_id) ?? r),
        );
        if (results.some((x) => x.status === 'completed' && x.repo_id === activeId)) {
          setDrawerOpen(false);
        }
      } catch {
        failures += 1;
        if (!cancelled && failures >= 3) setConnectionLost(true);
      }
    };

    const timer = setInterval(tick, 1500);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [processingKey, activeId, locked]);

  // ---------- Repositories ----------
  const upsertRepo = (data) =>
    setRepos((prev) =>
      prev.some((r) => r.repo_id === data.repo_id)
        ? prev.map((r) => (r.repo_id === data.repo_id ? data : r))
        : [data, ...prev],
    );

  const startIndexing = async (url, { force = false } = {}) => {
    const clean = url.trim();
    if (!GITHUB_URL.test(clean)) {
      setFormError('Enter a public GitHub repository URL, for example https://github.com/owner/repo.');
      return;
    }
    setFormError('');
    setSubmitting(true);
    try {
      const data = await startIndex(clean, force);
      upsertRepo(data);
      setActiveId(data.repo_id);
      setRepoUrl(clean);
      if (force) setChats((prev) => ({ ...prev, [data.repo_id]: [] }));
      if (data.status === 'completed') setDrawerOpen(false);
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const selectRepo = (id) => {
    const target = repos.find((r) => r.repo_id === id);
    setActiveId(id);
    setFormError('');
    if (target) setRepoUrl(target.url ?? '');
    setDrawerOpen(false);
  };

  const removeRepo = async (id) => {
    try {
      await deleteRepo(id);
      setRepos((prev) => prev.filter((r) => r.repo_id !== id));
      setChats((prev) => {
        const { [id]: _removed, ...rest } = prev;
        return rest;
      });
      if (activeId === id) setActiveId(null);
    } catch (err) {
      setFormError(err.message);
    }
  };

  // ---------- Chat ----------
  const patchLast = (repoId, patch) =>
    setChats((prev) => {
      const list = [...(prev[repoId] ?? [])];
      const last = list[list.length - 1];
      if (!last) return prev;
      list[list.length - 1] = { ...last, ...(typeof patch === 'function' ? patch(last) : patch) };
      return { ...prev, [repoId]: list };
    });

  const sendQuestion = async (text, { base } = {}) => {
    const question = text.trim();
    if (!question || !repo || repo.status !== 'completed' || asking) return;

    const repoId = repo.repo_id;
    const prior = base ?? chats[repoId] ?? [];
    const history = prior
      .filter((m) => !m.isError && m.content)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    setChats((prev) => ({
      ...prev,
      [repoId]: [
        ...prior,
        { role: 'user', content: question },
        { role: 'ai', content: '', sources: [], streaming: true },
      ],
    }));

    const controller = new AbortController();
    abortRef.current = controller;
    setAsking(true);
    try {
      await streamAnswer({
        question,
        repoId,
        history,
        signal: controller.signal,
        onSources: (sources) => patchLast(repoId, { sources }),
        onToken: (token) => patchLast(repoId, (m) => ({ content: m.content + token })),
      });
      patchLast(repoId, { streaming: false });
    } catch (err) {
      if (err?.name === 'AbortError') {
        patchLast(repoId, { streaming: false, stopped: true });
      } else {
        patchLast(repoId, (m) =>
          m.content
            ? { streaming: false, interrupted: err.message }
            : { streaming: false, isError: true, content: err.message },
        );
      }
    } finally {
      setAsking(false);
      abortRef.current = null;
    }
  };

  const stopAnswer = useCallback(() => abortRef.current?.abort(), []);

  const regenerate = () => {
    if (!repo || asking) return;
    const list = chats[repo.repo_id] ?? [];
    let index = list.length - 1;
    while (index >= 0 && list[index].role !== 'user') index -= 1;
    if (index < 0) return;
    sendQuestion(list[index].content, { base: list.slice(0, index) });
  };

  const warnings = [];
  if (config && !config.openai_key_set) {
    warnings.push('The server has no OPENAI_API_KEY. Add it to the server’s environment and restart it.');
  }
  if (config && !config.git_installed) {
    warnings.push('Git isn’t installed on the server, so repositories can’t be cloned.');
  }

  // ---------- Render ----------
  if (bootError) {
    return (
      <div className="fatal" role="alert">
        <h1 className="fatal-title">Can’t start RepoMind</h1>
        <p className="fatal-text">{bootError}</p>
        <button type="button" className="btn-solid" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }
  if (locked) return <AccessGate onUnlock={unlock} />;
  if (!config) return <div className="fatal" role="status">Loading…</div>;

  return (
    <div className="app">
      <Sidebar
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        repoUrl={repoUrl}
        onUrlChange={setRepoUrl}
        onSubmit={() => startIndexing(repoUrl)}
        submitting={submitting}
        formError={formError}
        warnings={warnings}
        repo={repo}
        repos={repos}
        onRetry={() => repo && startIndexing(repo.url, { force: true })}
        onSelect={selectRepo}
        onDelete={removeRepo}
      />
      {drawerOpen && (
        <button type="button" className="scrim" aria-label="Close sidebar" onClick={() => setDrawerOpen(false)} />
      )}
      <Chat
        repo={repo}
        messages={messages}
        asking={asking}
        connectionLost={connectionLost}
        theme={theme}
        onSend={sendQuestion}
        onStop={stopAnswer}
        onRegenerate={regenerate}
        onExport={() => repo && exportChat(repo, messages)}
        onReindex={() => repo && startIndexing(repo.url, { force: true })}
        onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))}
        onOpenSidebar={() => setDrawerOpen(true)}
      />
    </div>
  );
}

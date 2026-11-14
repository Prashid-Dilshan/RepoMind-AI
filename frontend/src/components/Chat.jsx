import { useEffect, useRef, useState } from 'react';
import { ArrowDown, Download, ExternalLink, Menu, Moon, RefreshCw, Send, Square, Sun, WifiOff } from 'lucide-react';
import { Message } from './Message.jsx';

const SUGGESTIONS = [
  'What does this project do?',
  'How do I run it locally?',
  'Where does the program start?',
  'Which libraries does it use?',
];

function statusPill(repo) {
  if (!repo) return null;
  if (repo.status === 'completed') return { tone: 'ready', text: 'Ready' };
  if (repo.status === 'failed') return { tone: 'failed', text: 'Indexing failed' };
  return { tone: 'busy', text: 'Indexing…' };
}

function emptyText(repo) {
  if (!repo) {
    return 'Paste a public repository URL in the sidebar. RepoMind reads its files, then answers with the exact excerpts it used.';
  }
  if (repo.status === 'completed') return 'This repository is indexed. Try one of these, or ask your own question.';
  if (repo.status === 'failed') return 'Indexing stopped before it finished. The sidebar shows what went wrong.';
  return 'Indexing is in progress. You can ask questions as soon as the last step finishes.';
}

function RepoFacts({ repo }) {
  const facts = [
    repo.language && ['Language', repo.language],
    typeof repo.stars === 'number' && ['Stars on GitHub', new Intl.NumberFormat().format(repo.stars)],
    repo.status === 'completed' && ['Files indexed', new Intl.NumberFormat().format(repo.files)],
    repo.indexed_at && ['Last indexed', new Date(repo.indexed_at * 1000).toLocaleString()],
  ].filter(Boolean);

  return (
    <div className="repo-card">
      {repo.description && <p className="repo-card-desc">{repo.description}</p>}
      {facts.length > 0 && (
        <dl className="facts">
          {facts.map(([label, value]) => (
            <div key={label} className="fact">
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {repo.url && (
        <a
          className="repo-card-link"
          href={repo.url.replace(/\.git$/, '')}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open on GitHub <ExternalLink size={13} aria-hidden="true" />
        </a>
      )}
    </div>
  );
}

export default function Chat({
  repo,
  messages,
  asking,
  connectionLost,
  theme,
  onSend,
  onStop,
  onRegenerate,
  onExport,
  onReindex,
  onToggleTheme,
  onOpenSidebar,
}) {
  const [draft, setDraft] = useState('');
  const scrollRef = useRef(null);
  const stickRef = useRef(true); // follow new text only while the reader is at the bottom
  const inputRef = useRef(null);
  const [showJump, setShowJump] = useState(false);

  const ready = repo?.status === 'completed';
  const pill = statusPill(repo);
  const last = messages[messages.length - 1];

  const repoId = repo?.repo_id;

  // Opening another repository starts at the latest message.
  useEffect(() => {
    stickRef.current = true;
  }, [repoId]);

  // Keep the newest text in view, but never fight a reader who scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [repoId, messages.length, last?.content, asking]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    stickRef.current = atBottom;
    setShowJump(!atBottom);
  };

  const jumpToLatest = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = true;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  };

  const send = (text) => {
    stickRef.current = true; // sending a question always jumps to the answer
    onSend(text);
  };

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [draft]);

  useEffect(() => {
    const onKey = (e) => {
      const typing = ['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName);
      if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape' && asking) onStop();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [asking, onStop]);

  const submit = () => {
    if (!draft.trim() || !ready || asking) return;
    send(draft);
    setDraft('');
  };

  return (
    <main className="main">
      <header className="topbar">
        <button type="button" className="icon-btn menu-btn" onClick={onOpenSidebar} aria-label="Open sidebar">
          <Menu size={20} aria-hidden="true" />
        </button>
        <div className="topbar-title">
          <span className="topbar-repo">{repo ? repo.name : 'No repository yet'}</span>
          {pill && <span className={`pill pill-${pill.tone}`}>{pill.text}</span>}
        </div>
        <div className="topbar-actions">
          {ready && (
            <button type="button" className="btn-ghost" onClick={onReindex} disabled={asking}>
              <RefreshCw size={15} aria-hidden="true" /> Re-index
            </button>
          )}
          <button
            type="button"
            className="icon-btn"
            onClick={onExport}
            disabled={messages.length === 0}
            aria-label="Download this conversation as Markdown"
            title="Download conversation"
          >
            <Download size={18} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="icon-btn"
            onClick={onToggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
          >
            {theme === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
          </button>
        </div>
      </header>

      {connectionLost && (
        <div className="banner" role="status">
          <WifiOff size={16} aria-hidden="true" />
          Lost connection to the server. Retrying…
        </div>
      )}

      <div className="scroll-wrap">
      <div className="scroll" ref={scrollRef} onScroll={onScroll}>
        <div className="column">
          {messages.length === 0 && (
            <section className="empty">
              <h1 className="empty-title">Ask anything about a GitHub repository</h1>
              <p className="empty-text">{emptyText(repo)}</p>
              {repo && <RepoFacts repo={repo} />}
              {ready && (
                <ul className="suggestions">
                  {SUGGESTIONS.map((q) => (
                    <li key={q}>
                      <button type="button" className="suggestion" onClick={() => send(q)} disabled={asking}>
                        {q}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {messages.map((message, i) => (
            <Message
              key={i}
              message={message}
              isLast={i === messages.length - 1 && !asking}
              onRegenerate={onRegenerate}
            />
          ))}
        </div>
      </div>
      {showJump && (
        <button type="button" className="jump" onClick={jumpToLatest} aria-label="Scroll to the latest message">
          <ArrowDown size={16} aria-hidden="true" /> Latest
        </button>
      )}
      </div>

      <div className="composer-wrap">
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <textarea
            ref={inputRef}
            className="composer-input"
            rows={1}
            maxLength={4000}
            aria-label="Your question"
            placeholder={ready ? 'Ask about this repository' : 'Index a repository to start asking'}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            disabled={!ready}
          />
          {asking ? (
            <button type="button" className="send" onClick={onStop} aria-label="Stop generating" title="Stop (Esc)">
              <Square size={16} fill="currentColor" aria-hidden="true" />
            </button>
          ) : (
            <button type="submit" className="send" aria-label="Send question" disabled={!ready || !draft.trim()}>
              <Send size={18} aria-hidden="true" />
            </button>
          )}
        </form>
        <p className="composer-note">
          Answers come from the indexed files and can be wrong. Open the excerpts to check them.
        </p>
      </div>
    </main>
  );
}

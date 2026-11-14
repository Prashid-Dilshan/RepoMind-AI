import { useState } from 'react';
import { AlertCircle, GitBranch, Loader2, RefreshCw, Trash2, X } from 'lucide-react';
import IndexProgress from './IndexProgress.jsx';

const fmt = (n) => new Intl.NumberFormat().format(n ?? 0);

export default function Sidebar({
  open,
  onClose,
  repoUrl,
  onUrlChange,
  onSubmit,
  submitting,
  formError,
  warnings,
  repo,
  repos,
  onRetry,
  onSelect,
  onDelete,
}) {
  const [confirmId, setConfirmId] = useState(null);

  return (
    <aside className={`sidebar${open ? ' is-open' : ''}`} aria-label="Repositories">
      <div className="brand">
        <span className="brand-mark">
          <GitBranch size={18} aria-hidden="true" />
        </span>
        <span className="brand-name">RepoMind-AI</span>
        <button type="button" className="icon-btn sidebar-close" onClick={onClose} aria-label="Close sidebar">
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="warning" role="alert">
          <AlertCircle size={16} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            {warnings.map((w) => (
              <p key={w} className="warning-text">
                {w}
              </p>
            ))}
          </div>
        </div>
      )}

      <form
        className="repo-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <label className="field-label" htmlFor="repo-url">
          GitHub repository URL
        </label>
        <input
          id="repo-url"
          className="repo-input"
          type="text"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          placeholder="https://github.com/owner/repo"
          value={repoUrl}
          onChange={(e) => onUrlChange(e.target.value)}
        />
        <button className="btn-primary" type="submit" disabled={submitting || !repoUrl.trim()}>
          {submitting ? (
            <>
              <Loader2 size={16} className="spin" aria-hidden="true" /> Starting…
            </>
          ) : (
            'Index repository'
          )}
        </button>
        {formError && (
          <p className="field-error" role="alert">
            {formError}
          </p>
        )}
      </form>

      {repo && (
        <section aria-live="polite" aria-label="Indexing status">
          <h2 className="progress-repo">{repo.name}</h2>
          {repo.status === 'completed' ? (
            <>
              <p className="progress-summary">
                {fmt(repo.files)} files indexed in {fmt(repo.chunks_total)} chunks.
              </p>
              {repo.note && <p className="progress-note">{repo.note}</p>}
            </>
          ) : (
            <IndexProgress repo={repo} />
          )}
          {repo.status === 'failed' && (
            <>
              <div className="failure" role="alert">
                <AlertCircle size={18} aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }} />
                <div>
                  <p className="failure-title">Couldn’t index this repository</p>
                  <p className="failure-text">{repo.error || 'Something went wrong while indexing.'}</p>
                </div>
              </div>
              <button type="button" className="btn-ghost failure-retry" onClick={onRetry}>
                <RefreshCw size={15} aria-hidden="true" /> Try again
              </button>
            </>
          )}
        </section>
      )}

      {repos.length > 0 && (
        <section aria-label="Your repositories">
          <h2 className="side-heading">Your repositories</h2>
          <ul className="recent">
            {repos.map((item) => {
              const confirming = confirmId === item.repo_id;
              return (
                <li key={item.repo_id} className="recent-row">
                  {confirming ? (
                    <div className="confirm" role="group" aria-label={`Delete ${item.name}?`}>
                      <span className="confirm-text">Delete {item.name}?</span>
                      <button
                        type="button"
                        className="confirm-yes"
                        onClick={() => {
                          setConfirmId(null);
                          onDelete(item.repo_id);
                        }}
                      >
                        Delete
                      </button>
                      <button type="button" className="confirm-no" onClick={() => setConfirmId(null)}>
                        Keep
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        className={`recent-open${repo?.repo_id === item.repo_id ? ' is-active' : ''}`}
                        onClick={() => onSelect(item.repo_id)}
                        title={item.url}
                      >
                        <span
                          className={`dot dot-${item.status === 'completed' ? 'ready' : item.status === 'failed' ? 'failed' : 'busy'}`}
                          role="img"
                          aria-label={
                            item.status === 'completed' ? 'Ready' : item.status === 'failed' ? 'Failed' : 'Indexing'
                          }
                        />
                        <span className="recent-name">{item.name}</span>
                      </button>
                      <button
                        type="button"
                        className="icon-btn recent-remove"
                        onClick={() => setConfirmId(item.repo_id)}
                        aria-label={`Delete ${item.name}`}
                        disabled={item.status === 'processing'}
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </button>
                    </>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <p className="sidebar-foot">
        Public GitHub repositories only. Answers are generated with OpenAI from the files RepoMind indexes.
      </p>
    </aside>
  );
}

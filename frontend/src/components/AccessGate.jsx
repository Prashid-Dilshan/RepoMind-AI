import { useState } from 'react';
import { Loader2, Lock } from 'lucide-react';
import { verifyAccessKey } from '../lib/api.js';

export default function AccessGate({ onUnlock }) {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) return;
    setBusy(true);
    setError('');
    try {
      await verifyAccessKey(trimmed);
      onUnlock(trimmed);
    } catch (err) {
      setError(err.status === 401 ? 'That access key isn’t correct.' : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="gate">
      <form className="gate-card" onSubmit={submit}>
        <span className="gate-icon">
          <Lock size={20} aria-hidden="true" />
        </span>
        <h1 className="gate-title">RepoMind-AI is private</h1>
        <p className="gate-text">Enter the access key you were given to continue.</p>
        <label className="gate-label" htmlFor="access-key">
          Access key
        </label>
        <input
          id="access-key"
          className="gate-input"
          type="password"
          autoComplete="current-password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          autoFocus
        />
        {error && (
          <p className="gate-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn-solid" disabled={busy || !key.trim()}>
          {busy ? <Loader2 size={16} className="spin" aria-hidden="true" /> : null}
          Unlock
        </button>
      </form>
    </main>
  );
}

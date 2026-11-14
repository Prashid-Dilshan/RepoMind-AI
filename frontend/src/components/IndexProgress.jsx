import { Check, Loader2, X } from 'lucide-react';

const STEPS = [
  { key: 'cloning', label: 'Clone repository' },
  { key: 'reading', label: 'Read files' },
  { key: 'embedding', label: 'Build search index' },
  { key: 'ready', label: 'Ready for questions' },
];

const fmt = (n) => new Intl.NumberFormat().format(n ?? 0);

function stepState(index, repo) {
  if (repo.status === 'completed') return 'done';
  const current = Math.max(0, STEPS.findIndex((s) => s.key === repo.stage));
  if (index < current) return 'done';
  if (index === current) return repo.status === 'failed' ? 'failed' : 'active';
  return 'pending';
}

function detailFor(step, state, repo) {
  if (step.key === 'cloning' && repo.stage === 'queued' && state === 'active') {
    return 'Waiting for a free slot';
  }
  if (step.key === 'reading' && repo.files > 0) return `${fmt(repo.files)} files`;
  if (step.key === 'embedding' && repo.chunks_total > 0) {
    if (state === 'active' || state === 'failed') {
      return `${fmt(repo.chunks_done)} of ${fmt(repo.chunks_total)} chunks`;
    }
    return `${fmt(repo.chunks_total)} chunks`;
  }
  return '';
}

function Marker({ state }) {
  if (state === 'done') return <Check size={13} strokeWidth={3} aria-hidden="true" />;
  if (state === 'failed') return <X size={13} strokeWidth={3} aria-hidden="true" />;
  if (state === 'active') return <Loader2 size={13} className="spin" aria-hidden="true" />;
  return null;
}

export default function IndexProgress({ repo }) {
  const percent =
    repo.chunks_total > 0 ? Math.round((repo.chunks_done / repo.chunks_total) * 100) : 0;

  return (
    <ol className="steps">
      {STEPS.map((step, index) => {
        const state = stepState(index, repo);
        const detail = detailFor(step, state, repo);
        return (
          <li key={step.key} className={`step is-${state}`}>
            <span className="step-marker">
              <Marker state={state} />
            </span>
            <div>
              <div className="step-label">{step.label}</div>
              {detail && <div className="step-detail">{detail}</div>}
              {step.key === 'embedding' && state === 'active' && repo.chunks_total > 0 && (
                <div
                  className="bar"
                  role="progressbar"
                  aria-label="Search index progress"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={percent}
                >
                  <div className="bar-fill" style={{ width: `${percent}%` }} />
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

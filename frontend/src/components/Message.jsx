import { Children, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { AlertCircle, Check, Copy, ExternalLink, FileText, Loader2, RefreshCw } from 'lucide-react';

function useCopy() {
  const [copied, setCopied] = useState(false);
  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable (for example on plain http); ignore */
    }
  };
  return [copied, copy];
}

function CodeBlock({ children }) {
  const [copied, copy] = useCopy();
  const codeEl = Children.toArray(children)[0];
  const text = String(codeEl?.props?.children ?? '').replace(/\n$/, '');
  const language = /language-([\w-]+)/.exec(codeEl?.props?.className || '')?.[1];

  return (
    <div className="codeblock">
      <div className="codeblock-bar">
        <span>{language || 'code'}</span>
        <button type="button" className="codeblock-copy" onClick={() => copy(text)}>
          {copied ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="codeblock-pre">{children}</pre>
    </div>
  );
}

const markdownComponents = { pre: CodeBlock };

function splitPath(path) {
  const i = path.lastIndexOf('/');
  return i === -1 ? ['', path] : [path.slice(0, i + 1), path.slice(i + 1)];
}

function lineRange(source) {
  if (!source.start_line) return '';
  return source.end_line > source.start_line
    ? `L${source.start_line}–${source.end_line}`
    : `L${source.start_line}`;
}

function Sources({ sources }) {
  return (
    <div className="sources-wrap">
      <p className="sources-label">
        Based on {sources.length} {sources.length === 1 ? 'excerpt' : 'excerpts'} from the repository
      </p>
      <ul className="sources">
        {sources.map((source, i) => {
          const [dir, file] = splitPath(source.path);
          const range = lineRange(source);
          const content = (
            <>
              <FileText size={13} aria-hidden="true" />
              <span>
                {dir && <span className="source-dir">{dir}</span>}
                <span className="source-file">{file}</span>
                {range && <span className="source-lines"> {range}</span>}
              </span>
              {source.url && <ExternalLink size={12} aria-hidden="true" />}
            </>
          );
          return (
            <li key={`${source.path}-${i}`}>
              {source.url ? (
                <a
                  className="source"
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  title="Open on GitHub"
                >
                  {content}
                </a>
              ) : (
                <span className="source">{content}</span>
              )}
            </li>
          );
        })}
      </ul>
      <details className="excerpts">
        <summary>View excerpts</summary>
        {sources.map((source, i) => (
          <div key={`${source.path}-ex-${i}`} className="excerpt">
            <div className="excerpt-path">
              {source.path} {lineRange(source)}
            </div>
            <pre className="excerpt-code">{source.snippet}</pre>
          </div>
        ))}
      </details>
    </div>
  );
}

export function Message({ message, isLast, onRegenerate }) {
  const [copied, copy] = useCopy();

  if (message.role === 'user') {
    return (
      <div className="msg-user">
        <p>{message.content}</p>
      </div>
    );
  }

  if (message.isError) {
    return (
      <div className="msg-ai is-error" role="alert">
        <AlertCircle size={18} aria-hidden="true" style={{ flexShrink: 0, marginTop: 2 }} />
        <p className="msg-error-text">{message.content}</p>
      </div>
    );
  }

  const sources = message.sources ?? [];
  const waiting = message.streaming && !message.content;

  return (
    <div className="msg-ai">
      {waiting ? (
        <div className="thinking" role="status">
          <Loader2 size={16} className="spin" aria-hidden="true" />
          {sources.length > 0 ? 'Writing the answer…' : 'Searching the indexed files…'}
        </div>
      ) : (
        <div className="prose">
          <ReactMarkdown components={markdownComponents}>{message.content}</ReactMarkdown>
        </div>
      )}
      {message.stopped && <p className="msg-note">Stopped before the answer finished.</p>}
      {message.interrupted && <p className="msg-note">{message.interrupted}</p>}
      {sources.length > 0 && <Sources sources={sources} />}
      {!message.streaming && message.content && (
        <div className="msg-actions">
          <button type="button" className="chip-btn" onClick={() => copy(message.content)}>
            {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
            {copied ? 'Copied' : 'Copy answer'}
          </button>
          {isLast && (
            <button type="button" className="chip-btn" onClick={onRegenerate}>
              <RefreshCw size={14} aria-hidden="true" /> Regenerate
            </button>
          )}
        </div>
      )}
    </div>
  );
}

import axios from 'axios';

// Empty by default: in development Vite proxies /api to the backend, and in production the
// backend serves this app, so both live at the same address. Set VITE_API_BASE only if the
// API is hosted somewhere else.
export const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

let accessKey = '';
let onUnauthorized = null;

export const setAccessKey = (key) => {
  accessKey = key || '';
};
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

function unreachableMessage() {
  const where = API_BASE || window.location.origin;
  return `Can't reach the server at ${where}. Start the backend with "python main.py" and keep that terminal open.`;
}

function toApiError(err) {
  if (err instanceof ApiError) return err;
  const status = err?.response?.status ?? 0;
  const detail = err?.response?.data?.detail;
  let message;
  if (typeof detail === 'string' && detail) message = detail;
  else if (Array.isArray(detail)) message = 'The request was not valid. Check the input and try again.';
  else if (!err?.response) message = unreachableMessage();
  else message = `The server returned an error (${status}). Check the server logs for details.`;
  return new ApiError(message, status);
}

const http = axios.create({ baseURL: API_BASE, timeout: 60000 });

http.interceptors.request.use((request) => {
  if (accessKey && !request.headers['X-Access-Key']) request.headers['X-Access-Key'] = accessKey;
  return request;
});

http.interceptors.response.use(
  (response) => response,
  (err) => {
    const apiError = toApiError(err);
    if (apiError.status === 401 && onUnauthorized) onUnauthorized();
    return Promise.reject(apiError);
  },
);

export const getConfig = () => http.get('/api/config').then((r) => r.data);

export const verifyAccessKey = (key) =>
  http.get('/api/auth/check', { headers: { 'X-Access-Key': key } }).then((r) => r.data);

export const listRepos = () => http.get('/api/repos').then((r) => r.data.repos);

export const getRepo = (repoId) => http.get(`/api/repos/${repoId}`).then((r) => r.data);

export const startIndex = (repoUrl, force = false) =>
  http.post('/api/repos', { repo_url: repoUrl, force }).then((r) => r.data);

export const deleteRepo = (repoId) => http.delete(`/api/repos/${repoId}`).then((r) => r.data);

// Streaming needs fetch: axios can't read a response while it is still arriving.
export async function streamAnswer({ question, repoId, history, signal, onSources, onToken }) {
  let response;
  try {
    response = await fetch(`${API_BASE}/api/query/stream`, {
      method: 'POST',
      signal,
      headers: {
        'Content-Type': 'application/json',
        ...(accessKey ? { 'X-Access-Key': accessKey } : {}),
      },
      body: JSON.stringify({ question, repo_id: repoId, history }),
    });
  } catch (err) {
    if (err?.name === 'AbortError') throw err;
    throw new ApiError(unreachableMessage(), 0);
  }

  if (!response.ok) {
    let detail = '';
    try {
      detail = (await response.json()).detail;
    } catch {
      /* not JSON */
    }
    const apiError = new ApiError(
      typeof detail === 'string' && detail ? detail : `The server returned an error (${response.status}).`,
      response.status,
    );
    if (apiError.status === 401 && onUnauthorized) onUnauthorized();
    throw apiError;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const handle = (raw) => {
    const line = raw.split('\n').find((l) => l.startsWith('data: '));
    if (!line) return false;
    const event = JSON.parse(line.slice(6));
    if (event.type === 'sources') onSources?.(event.sources);
    else if (event.type === 'token') onToken?.(event.text);
    else if (event.type === 'error') throw new ApiError(event.message, 500);
    else if (event.type === 'done') return true;
    return false;
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      if (handle(raw)) return;
    }
  }
}

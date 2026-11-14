// localStorage can be missing (private mode) or full. Never let that break the app.
export function readText(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeText(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function removeKey(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJSON(key, value) {
  writeText(key, JSON.stringify(value));
}

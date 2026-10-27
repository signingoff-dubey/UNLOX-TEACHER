// The only place the frontend talks to the backend (the FastAPI backend, see its /docs page).
// The base URL comes from Settings > Data, then VITE_API_URL, then the local FastAPI default.
// A 503 means the backend has not generated that artifact yet; ApiError carries the status so screens can say so.
const KEY = 'rootlens-api';

// The deployed API is a Cloud Function: its first request after idling loads the models, so allow longer.
const TIMEOUT_MS = import.meta.env.VITE_FIREBASE === '1' ? 60000 : 15000;

export const API_DEFAULTS = { url: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000', pollMs: 2000 };

export const readApiSettings = () => {
  try {
    return { ...API_DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return { ...API_DEFAULTS };
  }
};

export const saveApiSettings = (patch) => {
  const next = { ...readApiSettings(), ...patch };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Storage blocked: the setting holds until the page reloads.
  }
  return next;
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// Absolute URL for something the API serves (images, GLB models). Paths the API returns are relative to its base.
export const apiUrl = (path) => (/^https?:/i.test(path) ? path : `${readApiSettings().url}${path}`);

export const api = async (path, init = {}) => {
  // A FormData body sets its own multipart Content-Type (with the boundary), so JSON is only declared for everything else.
  const isForm = typeof FormData !== 'undefined' && init.body instanceof FormData;
  const res = await fetch(`${readApiSettings().url}${path}`, { ...init, headers: { ...(isForm ? {} : { 'Content-Type': 'application/json' }), ...init.headers }, signal: init.signal ?? AbortSignal.timeout(TIMEOUT_MS) });
  if (!res.ok) {
    let detail = '';
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : Array.isArray(body.detail) ? body.detail.map((d) => d.msg ?? JSON.stringify(d)).join('; ') : body.detail?.message ?? '';
    } catch {
      // No JSON body: the status line is all there is.
    }
    throw new ApiError(res.status, detail || `${res.status} ${res.statusText} on ${path}`);
  }
  return res.json();
};

export const post = (path, body, init = {}) => api(path, { ...init, method: 'POST', body: JSON.stringify(body) });

// Multipart upload (photos, 3D scans). Uploads and model calls are slower than the 15 s default, so the timeout is longer.
export const postForm = (path, form, init = {}) => api(path, { signal: AbortSignal.timeout(120000), ...init, method: 'POST', body: form });

export const health = () => api('/api/health');

import { useCallback, useEffect, useState } from 'react';
import { api, readApiSettings } from './api';

// GET helper shared by the screens. Successful responses are kept for TTL ms and in-flight requests are shared,
// so Overview, the summary panel and the Navbar do not each refetch the same artifact.
const TTL = 30000;
const cache = new Map();

const fetchOnce = (path, force) => {
  const key = `${readApiSettings().url}${path}`;
  const hit = cache.get(key);
  if (!force && hit && Date.now() - hit.at < TTL) return hit.promise;
  const promise = api(path);
  const entry = { at: Date.now(), promise };
  cache.set(key, entry);
  promise.catch(() => {
    if (cache.get(key) === entry) cache.delete(key);
  });
  return promise;
};

// useApi('/api/ranking') -> { data, error, loading, refetch }. Pass an array of paths to get an array of results.
// error.status is 503 when the backend has not generated the artifact yet.
export const useApi = (pathOrPaths) => {
  const key = Array.isArray(pathOrPaths) ? pathOrPaths.join('|') : pathOrPaths;
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    const paths = key.split('|');
    setState((s) => ({ ...s, error: null, loading: true }));
    Promise.all(paths.map((p) => fetchOnce(p, tick > 0)))
      .then((res) => live && setState({ data: paths.length === 1 && !Array.isArray(pathOrPaths) ? res[0] : res, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, refetch };
};

// Daily runs and fails across train, validation and test, built from /api/runs. Shared by the trend chart and the calendar.
export const RUN_PATHS = ['train', 'val', 'test'].map((s) => `/api/runs?split=${s}&limit=2000`);

export const dailyFrom = (responses) => {
  const days = new Map();
  for (const r of responses) {
    for (const run of r.runs) {
      const date = run.timestamp.slice(0, 10);
      const d = days.get(date) ?? { date, runs: 0, fails: 0 };
      d.runs += 1;
      d.fails += run.fail ? 1 : 0;
      days.set(date, d);
    }
  }
  return [...days.values()].sort((a, b) => a.date.localeCompare(b.date));
};

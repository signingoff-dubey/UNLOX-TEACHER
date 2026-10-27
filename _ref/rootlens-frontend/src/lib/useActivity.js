import { useEffect, useState } from 'react';
import { api, apiUrl } from './api';
import { FIREBASE, firestore } from './firebase';

// Live activity (captures, scan inspections, model uploads). Locally the API pushes it over SSE; deployed,
// the dashboard listens to the Firestore collections directly. Polling covers a stream that cannot connect.
const POLL_MS = 10000;
const DAYS = 62;
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

// Same events and day buckets as backend/api/activity.py, built from the Firestore rows.
const toEvents = ({ captures, inspections, assemblies }) => {
  const ev = [];
  for (const c of captures) {
    const bad = ['failed', 'needs_review'].includes(c.status) || c.risk_band === 'high';
    ev.push({ id: c.id, kind: 'capture', at: c.created, tone: bad ? 'rose' : 'good', link: `#/captures/${c.id}`,
      title: `Capture (${c.source}): ${String(c.status ?? '').replace('_', ' ')}${c.risk_band ? `, ${c.risk_band} risk` : ''}` });
  }
  for (const i of inspections) {
    const found = (i.cracks_found ?? 0) > 0 || (i.dent_faces ?? 0) > 0 || (i.part_damage ?? []).length > 0;
    ev.push({ id: i.id, kind: 'inspection', at: i.created, tone: found ? 'rose' : 'info', link: `#/inspection/${i.id}`,
      title: `Scan inspection: ${i.inputs?.mesh ?? i.id}${i.artificial ? ' (artificial defect)' : ''}` });
  }
  for (const a of assemblies) {
    const dmg = a.counts?.damaged_parts ?? 0;
    ev.push({ id: a.id, kind: 'assembly', at: a.created, tone: dmg ? 'rose' : 'info', link: `#/inspection/${a.id}`,
      title: `Model uploaded: ${a.label}${dmg ? ` (${dmg} damaged part)` : ''}` });
  }
  return ev.filter((e) => e.at).sort((x, y) => (x.at < y.at ? 1 : -1));
};

const snapshotOf = (rows) => {
  const now = new Date();
  const since = iso(new Date(now.getTime() - DAYS * 864e5));
  const ev = toEvents(rows).filter((e) => e.at.slice(0, 10) >= since);
  const byDay = new Map();
  for (const e of ev) {
    const key = e.at.slice(0, 10);
    const d = byDay.get(key) ?? { date: key, capture: 0, inspection: 0, assembly: 0, alerts: 0, events: [] };
    d[e.kind] += 1;
    d.alerts += e.tone === 'rose' ? 1 : 0;
    if (d.events.length < 20) d.events.push(e);
    byDay.set(key, d);
  }
  return { now: now.toISOString().slice(0, 19), today: iso(now), version: ev.map((e) => e.id).join(',').slice(0, 64),
    days: [...byDay.values()].sort((a, b) => (a.date < b.date ? -1 : 1)), recent: ev.slice(0, 10) };
};

const useFirestoreActivity = () => {
  const [state, setState] = useState({ data: null, error: null, live: false });
  useEffect(() => {
    const rows = { captures: [], inspections: [], assemblies: [] };
    const seen = new Set();
    const unsubs = [];
    let closed = false;
    firestore()
      .then(({ db, fs }) => {
        if (closed) return;
        for (const col of Object.keys(rows)) {
          const q = fs.query(fs.collection(db, col), fs.orderBy('created', 'desc'), fs.limit(200));
          unsubs.push(fs.onSnapshot(q, (snap) => {
            rows[col] = snap.docs.map((d) => { const { payload, ...rest } = d.data(); return rest; }); // eslint-disable-line no-unused-vars
            seen.add(col);
            if (seen.size === 3) setState({ data: snapshotOf(rows), error: null, live: true });
          }, (error) => setState((s) => ({ ...s, error, live: false }))));
        }
      })
      .catch((error) => setState((s) => ({ ...s, error })));
    return () => {
      closed = true;
      unsubs.forEach((u) => u());
    };
  }, []);
  return state;
};

const useApiActivity = () => {
  const [state, setState] = useState({ data: null, error: null, live: false });

  useEffect(() => {
    let closed = false;
    let source = null;
    let poll = null;

    const apply = (data) => !closed && setState({ data, error: null, live: Boolean(source && source.readyState === 1) });
    const fetchNow = () => api('/api/activity').then(apply).catch((error) => !closed && setState((s) => ({ ...s, error })));

    const startPolling = () => {
      if (poll) return;
      fetchNow();
      poll = setInterval(fetchNow, POLL_MS);
    };
    const stopPolling = () => {
      clearInterval(poll);
      poll = null;
    };

    if (typeof EventSource === 'function') {
      source = new EventSource(apiUrl('/api/activity/stream'));
      source.addEventListener('activity', (e) => {
        stopPolling();
        try {
          apply(JSON.parse(e.data));
        } catch {
          // ignore a malformed frame; the next one replaces it
        }
      });
      source.addEventListener('tick', (e) => {
        try {
          const { now, today } = JSON.parse(e.data);
          !closed && setState((s) => (s.data ? { ...s, live: true, data: { ...s.data, now, today } } : s));
        } catch {
          // heartbeat only
        }
      });
      // EventSource reconnects by itself; poll in the meantime so the calendar never goes stale.
      source.onerror = () => {
        !closed && setState((s) => ({ ...s, live: false }));
        startPolling();
      };
    } else {
      startPolling();
    }

    const onVisible = () => document.visibilityState === 'visible' && fetchNow();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      closed = true;
      source?.close();
      stopPolling();
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, []);

  return state;
};

const useLiveActivity = FIREBASE ? useFirestoreActivity : useApiActivity;

// Production history per day (SECOM runs replayed onto Sep-Oct 2026), merged into the calendar days.
export const useActivity = () => {
  const live = useLiveActivity();
  const [history, setHistory] = useState(null);
  useEffect(() => {
    api('/api/history/calendar', { signal: AbortSignal.timeout(60000) }).then(setHistory).catch(() => setHistory(null));
  }, []);
  if (!live.data || !history) return live;
  const byDate = new Map(live.data.days.map((d) => [d.date, { ...d }]));
  for (const h of history.days) {
    const d = byDate.get(h.date) ?? { date: h.date, capture: 0, inspection: 0, assembly: 0, alerts: 0, events: [] };
    byDate.set(h.date, { ...d, runs: h.runs, fails: h.fails, high_risk: h.high_risk });
  }
  return { ...live, data: { ...live.data, history_label: history.label, days: [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1)) } };
};

// Local "today" that rolls over at midnight without a reload.
export const useToday = () => {
  const [today, setToday] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => {
      const now = new Date();
      setToday((prev) => (prev.toDateString() === now.toDateString() ? prev : now));
    }, 30000);
    return () => clearInterval(id);
  }, []);
  return today;
};

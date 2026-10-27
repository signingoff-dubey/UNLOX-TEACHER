import { useLiveRefetch } from '../lib/useLiveRefetch';
import { useEffect, useState } from 'react';
import { Box, Flame, LoaderCircle, ScanEye, TriangleAlert, Upload } from 'lucide-react';
import { CardTitle } from './ui';
import AssemblyViewer from './AssemblyViewer';
import { api, post, postForm } from '../lib/api';
import CallStatus from './CallStatus';
import Remedy from './Remedy';
import Solutions from './Solutions';
import { askAssistant } from './AssistantDock';
import { useApi } from '../lib/useApi';

// "View damage": a multi-part model (e.g. a Blender export) with simulated internal damage and a thermal layer.
// Sample data to show what the viewer can do; nothing here is measured or linked to the SECOM analysis.

const errText = (e) => (e?.name === 'TimeoutError' ? 'The API took too long to answer.' : e?.message || 'Could not reach the API.');
const fileCls = 'block w-full text-sm file:mr-3 file:cursor-pointer file:rounded-full file:border-0 file:bg-ink/8 file:px-3.5 file:py-2 file:text-sm file:font-medium hover:file:bg-ink/12';
const ACCEPT = '.glb,.zip,.obj,.ply,.stl,.blend';

const Loader = ({ onLoaded, busy, setBusy, setError }) => {
  const [file, setFile] = useState(null);
  const samples = useApi('/api/assembly/samples');
  const caps = useApi('/api/assembly/capabilities');

  const run = async (fn) => {
    setBusy(true);
    setError('');
    try {
      onLoaded(await fn());
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };
  const upload = (e) => {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    run(() => postForm('/api/assembly', form, { signal: AbortSignal.timeout(300000) }));
  };
  const files = (samples.data?.files ?? []).filter((f) => f.kind !== 'builtin');

  return (
    <section className="card" aria-busy={busy}>
      <CardTitle sub="A multi-part model with damage and thermal tags, for example a Blender export.">Load a model</CardTitle>
      <button
        type="button"
        disabled={busy}
        onClick={() => run(() => api('/api/assembly/demo', { signal: AbortSignal.timeout(120000) }))}
        className="flex w-full items-center gap-3 rounded-2xl bg-accent/15 p-3 text-left ring-1 ring-accent/30 transition-colors hover:bg-accent/25 disabled:opacity-50"
      >
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-accent text-on-accent"><ScanEye size={18} /></span>
        <span>
          <span className="block text-sm font-semibold">Sample: power bank with an internal cell crack</span>
          <span className="block text-xs text-ink/60">Built in. Simulated damage and thermal data.</span>
        </span>
      </button>

      <form onSubmit={upload} className="mt-4 flex flex-col gap-2">
        <label className="text-sm font-medium" htmlFor="asm-file">Upload a model</label>
        <input id="asm-file" type="file" accept={ACCEPT} className={fileCls} onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <p className="text-xs text-ink/55">
          .glb preferred (with Custom Properties and Animation exported). Also a zipped .gltf folder, .obj, .ply, .stl
          {caps.data?.blend_conversion ? ', .blend' : '. .blend needs Blender on the server; export .glb instead'}.
        </p>
        <button type="submit" disabled={!file || busy} className="mt-1 flex items-center justify-center gap-2 self-start rounded-full bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-40">
          <Upload size={15} /> Upload and view
        </button>
      </form>

      {files.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-medium">From the models folders</p>
          <ul className="mt-2 flex flex-col gap-1.5">
            {files.map((f) => (
              <li key={f.name}>
                <button type="button" disabled={busy} onClick={() => run(() => post('/api/assembly/samples/load', { name: f.name }, { signal: AbortSignal.timeout(180000) }))} className="flex w-full items-center gap-2 rounded-xl bg-ink/5 px-3 py-2 text-left text-sm hover:bg-ink/10 disabled:opacity-50">
                  <Box size={14} className="shrink-0 text-ink/50" /> <span className="truncate">{f.label}</span>
                  <span className="ml-auto shrink-0 text-xs uppercase text-ink/45">{f.kind}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {busy && <p role="status" className="mt-3 flex items-center gap-2 text-sm text-ink/65"><LoaderCircle size={15} className="animate-spin" /> Reading the model...</p>}
    </section>
  );
};

const Summary = ({ m }) => (
  <section className="card">
    <CardTitle
      sub={m.note}
      action={m.damage?.length > 0 && (
        <button type="button" onClick={() => askAssistant(`What is wrong with the latest inspected part (${m.label}), why does it happen and how do we fix it?`)} className="btn-ghost h-9 px-3 text-sm">Ask AI for a fix</button>
      )}
    >
      {m.label}
    </CardTitle>
    <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
      {[['Parts', m.counts.parts], ['Damaged parts', m.counts.damaged_parts], ['Animations', m.counts.animations], ['Hottest', m.thermal?.max_c != null ? `${m.thermal.max_c} °C` : '-']].map(([k, v]) => (
        <div key={k} className="rounded-xl bg-ink/5 px-3 py-2">
          <dt className="text-xs text-ink/55">{k}</dt>
          <dd className="tabular font-semibold">{v}</dd>
        </div>
      ))}
    </dl>
    {m.damage?.length > 0 && (
      <ul className="mt-3 flex flex-col gap-2">
        {m.damage.map((d) => (
          <li key={d.part} className="rounded-xl bg-bad/10 p-3 text-sm">
            <p className="flex items-center gap-2 font-semibold"><TriangleAlert size={14} className="text-bad" /> {d.display_name}: <span className="capitalize">{d.type}</span>{d.internal ? ', internal' : ''}</p>
            {d.description && <p className="mt-0.5 text-ink/70">{d.description}</p>}
            {d.source && <p className="mt-0.5 text-[11px] text-ink/50">Found by: {d.source}</p>}
            <p className="mt-1 text-xs text-ink/55">
              {d.severity != null && <>Severity {d.severity}. </>}
              {d.temp_c != null && <><Flame size={11} className="inline" /> {d.temp_c} °C (simulated).</>}
            </p>
            <Remedy r={d.remedy} />
          </li>
        ))}
      </ul>
    )}
    {m.warnings?.length > 0 && (
      <ul className="mt-3 flex flex-col gap-1 text-xs text-ink/60">
        {m.warnings.map((w) => <li key={w}>• {w}</li>)}
      </ul>
    )}
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer font-medium">All parts ({m.parts.length})</summary>
      <table className="mt-2 w-full text-left text-xs">
        <thead className="text-ink/55"><tr><th className="py-1">Part</th><th>Role</th><th className="text-right">°C (sim.)</th></tr></thead>
        <tbody>
          {m.parts.map((p) => (
            <tr key={p.name} className="border-t border-ink/8">
              <td className="py-1">{p.display_name}{p.damage ? ' ⚠' : ''}</td>
              <td className="text-ink/60">{p.role}</td>
              <td className="tabular text-right">{p.temp_c ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  </section>
);

const History = ({ q, current, onOpen }) => {
  const items = q.data?.assemblies ?? [];
  if (!items.length) return null;
  return (
    <section className="card">
      <CardTitle>Recent models</CardTitle>
      <ul className="flex flex-col gap-1.5">
        {items.slice(0, 6).map((a) => (
          <li key={a.id}>
            <button type="button" onClick={() => onOpen(a.id)} className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left text-sm ${a.id === current ? 'bg-accent/15 ring-1 ring-accent/30' : 'bg-ink/5 hover:bg-ink/10'}`}>
              <span className="truncate">{a.label}</span>
              <span className="shrink-0 text-xs text-ink/55">{a.counts?.parts} parts</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
};

const DamagePanel = ({ id, onCurrent }) => {
  const [manifest, setManifest] = useState(null);
  const [alertState, setAlertState] = useState(null);   // { callId, note } after View damage
  useEffect(() => setAlertState(null), [manifest?.id]);
  const onViewDamage = async () => {
    if (!manifest?.damage?.length) return;
    try {
      const r = await post('/api/alerts/view-damage', { id: manifest.id }, { signal: AbortSignal.timeout(30000) });
      const call = (r.results ?? []).find((x) => x.channel === 'call');
      setAlertState({ callId: call?.ok ? call.attempt_id : null, note: r.sent ? (call?.ok ? '' : call?.result) : r.reason });
    } catch (e) {
      setAlertState({ callId: null, note: errText(e) });
    }
  };
  useEffect(() => onCurrent?.(manifest?.id), [manifest?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const history = useApi('/api/assembly');
  useLiveRefetch('assemblies', history.refetch);

  const open = async (aid) => {
    setError('');
    try {
      setManifest(await api(`/api/assembly/${encodeURIComponent(aid)}`));
    } catch (e) {
      setError(`Could not open that model: ${errText(e)}`);
    }
  };
  useEffect(() => {
    if (id) open(id);
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  const onLoaded = (m) => {
    setManifest(m);
    history.refetch();
  };

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
      <div className="flex flex-col gap-[var(--gap)]">
        <Loader onLoaded={onLoaded} busy={busy} setBusy={setBusy} setError={setError} />
        <History q={history} current={manifest?.id} onOpen={open} />
      </div>
      <div className="flex min-w-0 flex-col gap-[var(--gap)]">
        {error && <p role="alert" className="rounded-2xl bg-bad/20 px-4 py-3 text-sm font-medium text-white ring-1 ring-bad/40">{error}</p>}
        {manifest ? (
          <>
            <section className="card">
              <AssemblyViewer manifest={manifest} onViewDamage={onViewDamage} />
              {alertState && (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink/60">
                  {alertState.callId && <CallStatus id={alertState.callId} />}
                  {alertState.note && <span>Alert: {alertState.note}</span>}
                </div>
              )}
              <p className="mt-2 text-xs text-ink/55">Drag to rotate, scroll to zoom, click a part for details. Temperatures are simulated{manifest.warnings?.some((w) => w.includes('inferred')) ? '; damage is read from the object names in the file' : ''}.</p>
            </section>
            <Summary m={manifest} />
            <Solutions compact title="Process changes from the line data (SECOM)" />
          </>
        ) : (
          <section className="card grid place-items-center py-16 text-center">
            <span className="grid size-12 place-items-center rounded-2xl bg-accent/15 text-accent-deep"><ScanEye size={22} /></span>
            <p className="mt-4 font-medium">No model loaded</p>
            <p className="mt-1 max-w-sm text-sm text-ink/60">Load the power bank sample or upload a model. Then press View damage to take it apart and see the damaged part.</p>
          </section>
        )}
      </div>
    </div>
  );
};

export default DamagePanel;

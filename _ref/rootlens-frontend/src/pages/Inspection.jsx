import { useLiveRefetch } from '../lib/useLiveRefetch';
import { useEffect, useState } from 'react';
import { Box, Check as CheckIcon, LoaderCircle, PhoneCall, ScanSearch, TriangleAlert } from 'lucide-react';
import { Banner, CardTitle, Tabs } from '../components/ui';
import Gate, { StatusCard } from '../components/ui/Gate';
import ModelViewer from '../components/ModelViewer';
import DamagePanel from '../components/DamagePanel';
import AssemblyViewer from '../components/AssemblyViewer';
import CallStatus from '../components/CallStatus';
import Remedy from '../components/Remedy';
import { askAssistant } from '../components/AssistantDock';
import { api, post, postForm } from '../lib/api';
import { num, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

const SENSOR_NOTE = 'iPad LiDAR resolution is about 1 to 1.5 cm. Small cracks and shallow dents cannot be detected.';
const TABS = ['Upload files', 'Samples from data/scans'];

const whenIso = (ts) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? String(ts ?? '') : d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
};
const errText = (e) => (e?.name === 'TimeoutError' ? 'The API took too long to answer.' : e?.message || 'Could not reach the API.');
const kb = (n) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

const fileCls = 'block w-full text-sm file:mr-3 file:cursor-pointer file:rounded-full file:border-0 file:bg-ink/8 file:px-3.5 file:py-2 file:text-sm file:font-medium hover:file:bg-ink/12';

const Common = ({ threshold, setThreshold, artificial, setArtificial }) => (
  <>
    <label className="block text-sm">
      <span className="flex justify-between"><span className="font-medium">Dent threshold</span><span className="tabular font-semibold">{threshold} mm</span></span>
      <input type="range" min={1} max={50} step={1} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} className="mt-1.5" />
      <span className="mt-1 block text-xs text-ink/55">Surface deviation above this counts toward the dent summary. The sensor cannot resolve much below 10 mm.</span>
    </label>
    <label className="flex items-start gap-2.5 rounded-xl border border-ink/10 px-3 py-2.5 text-sm">
      <input type="checkbox" checked={artificial} onChange={(e) => setArtificial(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-accent)]" />
      <span>
        <span className="font-medium">Artificial defect</span>
        <span className="block text-xs text-ink/60">Tick this when the defect was added on purpose to test the check. The result is then labelled that way.</span>
      </span>
    </label>
  </>
);

const Select = ({ label, value, onChange, options, none }) => (
  <label className="flex flex-col gap-1.5 text-sm">
    <span className="font-medium">{label}</span>
    <select value={value} onChange={(e) => onChange(e.target.value)} className="field">
      {none && <option value="">{none}</option>}
      {options.map((o) => <option key={o.name} value={o.name}>{o.name} ({kb(o.size)})</option>)}
    </select>
  </label>
);

const UploadForm = ({ onResult, setBusy, setError, busy }) => {
  const [mesh, setMesh] = useState(null);
  const [texture, setTexture] = useState(null);
  const [reference, setReference] = useState(null);
  const [threshold, setThreshold] = useState(15);
  const [artificial, setArtificial] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!mesh) return;
    const form = new FormData();
    form.append('mesh', mesh);
    if (texture) form.append('texture', texture);
    if (reference) form.append('reference', reference);
    form.append('threshold_mm', String(threshold));
    form.append('artificial', String(artificial));
    setBusy(true);
    setError('');
    try {
      onResult(await postForm('/api/inspection/scan', form));
    } catch (err) {
      setError(`The scan could not be analyzed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">3D scan <span className="font-normal text-ink/55">(.obj, .ply, .glb or .stl)</span></span>
        <input type="file" accept=".obj,.ply,.glb,.stl" onChange={(e) => setMesh(e.target.files?.[0] ?? null)} className={fileCls} required />
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">Texture image <span className="font-normal text-ink/55">(optional)</span></span>
        <input type="file" accept="image/*" onChange={(e) => setTexture(e.target.files?.[0] ?? null)} className={fileCls} />
      </label>
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">Reference scan <span className="font-normal text-ink/55">(optional, a good part to compare against)</span></span>
        <input type="file" accept=".obj,.ply,.glb,.stl" onChange={(e) => setReference(e.target.files?.[0] ?? null)} className={fileCls} />
      </label>
      <Common threshold={threshold} setThreshold={setThreshold} artificial={artificial} setArtificial={setArtificial} />
      <button type="submit" disabled={busy || !mesh} className="btn-primary self-start">
        {busy ? <LoaderCircle size={16} className="animate-spin" /> : <ScanSearch size={16} />} Analyze scan
      </button>
    </form>
  );
};

const SampleForm = ({ onResult, setBusy, setError, busy }) => {
  const q = useApi('/api/inspection/samples');
  return (
    <Gate q={q} what="The sample scans">
      {(d) => <SamplePicker d={d} onResult={onResult} setBusy={setBusy} setError={setError} busy={busy} />}
    </Gate>
  );
};

const SamplePicker = ({ d, onResult, setBusy, setError, busy }) => {
  const meshes = d.files.filter((f) => f.kind === 'mesh');
  const textures = d.files.filter((f) => f.kind === 'texture');
  const [mesh, setMesh] = useState(meshes[0]?.name ?? '');
  const [texture, setTexture] = useState('');
  const [reference, setReference] = useState('');
  const [threshold, setThreshold] = useState(15);
  const [artificial, setArtificial] = useState(false);
  if (!meshes.length) {
    return <p className="rounded-xl bg-ink/5 px-3 py-3 text-sm text-ink/70">No scans found in <span className="font-mono">{d.folder}</span>. Drop .obj, .ply, .glb or .stl files there (and a texture image if you have one), then reload this page.</p>;
  }
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const body = { mesh, threshold_mm: threshold, artificial, ...(texture ? { texture } : {}), ...(reference ? { reference } : {}) };
      onResult(await post('/api/inspection/samples/analyze', body, { signal: AbortSignal.timeout(120000) }));
    } catch (err) {
      setError(`The scan could not be analyzed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <p className="text-xs text-ink/60">Files in <span className="font-mono">{d.folder}</span> on the machine running the API.</p>
      <Select label="3D scan" value={mesh} onChange={setMesh} options={meshes} />
      <Select label="Texture image (optional)" value={texture} onChange={setTexture} options={textures} none="No texture" />
      <Select label="Reference scan (optional)" value={reference} onChange={setReference} options={meshes.filter((m) => m.name !== mesh)} none="No reference" />
      <Common threshold={threshold} setThreshold={setThreshold} artificial={artificial} setArtificial={setArtificial} />
      <button type="submit" disabled={busy || !mesh} className="btn-primary self-start">
        {busy ? <LoaderCircle size={16} className="animate-spin" /> : <ScanSearch size={16} />} Analyze sample
      </button>
    </form>
  );
};

// ---------------------------------------------------------------- result

const Stat = ({ k, v }) => (
  <div className="rounded-xl bg-ink/5 px-3 py-2">
    <dt className="text-xs text-ink/55">{k}</dt>
    <dd className="tabular text-sm font-semibold">{v}</dd>
  </div>
);

const extentText = (e) => (Array.isArray(e) ? `${e.map((v) => num(v, 0)).join(' x ')} mm` : e && typeof e === 'object' ? Object.values(e).map((v) => num(v, 0)).join(' x ') + ' mm' : e ?? 'unknown');

const Check = ({ title, c, children }) => (
  <section className="rounded-2xl bg-ink/5 p-3.5">
    <h3 className="flex items-center justify-between gap-2 text-sm font-semibold">
      {title}
      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${c?.enabled ? 'bg-good/12 text-good' : 'bg-ink/10 text-ink/60'}`}>{c?.enabled ? 'ran' : 'did not run'}</span>
    </h3>
    {c?.enabled ? <dl className="mt-2 grid grid-cols-2 gap-2">{children}</dl> : <p className="mt-2 text-xs text-ink/65">{c?.reason || 'This check did not run for this scan.'}</p>}
    {c?.enabled && c.reason && <p className="mt-2 text-xs text-ink/60">{c.reason}</p>}
  </section>
);

// Per-part damage for multi-part models (e.g. the Blender team's semiconductor packages).
const PartDamage = ({ p }) => (
  <section className="mt-4 rounded-2xl bg-ink/5 p-3.5">
    <h3 className="flex items-center justify-between gap-2 text-sm font-semibold">
      <span>Damage found in the parts</span>
      {p.damage?.length > 0 && (
        <button type="button" onClick={() => askAssistant('What is wrong with the latest inspected part, why does it happen and how do we fix it?')} className="rounded-full bg-ink/8 px-2.5 py-1 text-xs font-semibold hover:bg-ink/12">Ask AI for a fix</button>
      )}
      <span className="text-xs font-medium text-ink/55">
        {num(p.counts?.damaged_parts, 0)} damaged, {num(p.counts?.damage_markers, 0)} marks{p.thermal?.max_c != null ? `, hottest ${p.thermal.max_c} °C (simulated)` : ''}
      </span>
    </h3>
    {p.damage?.length ? (
      <ul className="mt-2 grid gap-2 sm:grid-cols-2">
        {[...p.damage].sort((a, b) => (b.severity ?? 0) - (a.severity ?? 0)).map((d) => (
          <li key={d.part} className="rounded-xl bg-bad/10 p-2.5 text-sm">
            <p className="flex items-center gap-1.5 font-semibold"><TriangleAlert size={13} className="text-bad" /> {d.display_name}</p>
            <p className="mt-0.5 text-xs text-ink/70 first-letter:uppercase">
              {d.type}{d.internal ? ', internal' : ', external'}{d.severity != null ? `, severity ${d.severity}` : ''}{d.temp_c != null ? `, ${d.temp_c} °C (simulated)` : ''}
            </p>
            {d.description && <p className="mt-0.5 text-xs text-ink/60">{d.description}</p>}
            <Remedy r={d.remedy} />
          </li>
        ))}
      </ul>
    ) : (
      <p className="mt-2 text-sm text-ink/60">No damaged parts in this model.</p>
    )}
  </section>
);

// Multi-part scan: the 3D viewer; View damage alerts once for this scan (call, WhatsApp, email per settings).
const ScanParts = ({ r }) => {
  const [alert, setAlert] = useState(null);
  const onViewDamage = async () => {
    if (!r.parts?.damage?.length) return;
    try {
      const out = await post('/api/alerts/view-damage', { id: r.id }, { signal: AbortSignal.timeout(30000) });
      const call = (out.results ?? []).find((x) => x.channel === 'call');
      setAlert({ callId: call?.ok ? call.attempt_id : null, note: out.sent ? (call?.ok ? '' : call?.result) : out.reason });
    } catch (e) {
      setAlert({ callId: null, note: errText(e) });
    }
  };
  return (
    <>
      <AssemblyViewer key={r.parts.model_url} manifest={{ ...r.parts, label: r.inputs?.mesh }} onViewDamage={onViewDamage} />
      {alert && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink/60">
          {alert.callId && <CallStatus id={alert.callId} />}
          {alert.note && <span>Alert: {alert.note}</span>}
        </div>
      )}
    </>
  );
};

const Result = ({ r }) => (
  <section className="card" aria-live="polite">
    <CardTitle
      sub={`${whenIso(r.created)}. Surface checks only: they say nothing about why a part fails.`}
      action={
        <span className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold">
          <span className="rounded-full bg-ink/8 px-2 py-0.5 text-ink/70">{r.label || 'analyzed after upload'}</span>
          {r.artificial && <span className="rounded-full bg-warn/15 px-2 py-0.5 text-warn">artificial defect</span>}
          {r.status && r.status !== 'ok' && <span className="rounded-full bg-bad/12 px-2 py-0.5 text-bad">{r.status}</span>}
        </span>
      }
    >
      Scan result
    </CardTitle>
    {r.parts ? (
      <ScanParts r={r} />
    ) : r.model_url ? (
      <ModelViewer key={r.model_url} url={r.model_url} />
    ) : (
      <p className="rounded-xl bg-ink/5 px-3 py-6 text-center text-sm text-ink/60">No 3D model was produced for this scan.</p>
    )}
    {r.parts ? (
      <p className="mt-2 text-xs text-ink/65">
        Multi-part model: {num(r.parts.counts?.parts, 0)} parts. View damage takes it apart, isolates the damaged part and shows the heat view;
        the slider explodes it. Temperatures are simulated{r.parts.warnings?.some((w) => w.includes('inferred')) ? '; damage is read from the object names in the file' : ''}.
      </p>
    ) : (
    <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink/65">
      <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-bad" /> crack faces</span>
      <span className="flex items-center gap-1.5"><span className="h-2.5 w-10 rounded-sm" style={{ background: 'linear-gradient(90deg, #2f5fd0, #d63a3a)' }} /> dent deviation, small to large</span>
      <span>Drag to rotate, scroll to zoom.</span>
    </p>
    )}
    <p className="mt-3 flex items-start gap-2 rounded-xl bg-warn/15 px-3 py-2 text-xs font-medium"><TriangleAlert size={14} className="mt-0.5 shrink-0" /> {r.sensor_note || SENSOR_NOTE}</p>
    {r.artificial && <p className="mt-2 text-xs text-ink/65">Marked as an artificial defect: this tests the check and is not a finding about a real part.</p>}

    {r.parts && <PartDamage p={r.parts} />}
    {r.remedies?.crack && <Remedy r={r.remedies.crack} open />}
    {r.remedies?.dent && <Remedy r={r.remedies.dent} />}
    <div className="mt-4 grid gap-3 lg:grid-cols-3">
      <section className="rounded-2xl bg-ink/5 p-3.5">
        <h3 className="text-sm font-semibold">Mesh</h3>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <Stat k="Vertices" v={num(r.mesh?.vertices, 0)} />
          <Stat k="Faces" v={num(r.mesh?.faces, 0)} />
          <Stat k="Size" v={extentText(r.mesh?.extent_mm)} />
          <Stat k="Format" v={r.mesh?.format ?? 'unknown'} />
          <Stat k="Texture" v={r.mesh?.has_texture ? 'yes' : 'no'} />
          <Stat k="Vertex colours" v={r.mesh?.has_colors ? 'yes' : 'no'} />
        </dl>
      </section>
      <Check title="Cracks" c={r.cracks}>
        <Stat k="Regions" v={num(r.cracks?.regions, 0)} />
        <Stat k="Faces flagged" v={num(r.cracks?.faces_flagged, 0)} />
        <Stat k="Share of surface" v={pct(r.cracks?.area_frac ?? 0, 2)} />
      </Check>
      <Check title="Dents" c={r.dents}>
        <Stat k="Largest deviation" v={`${num(r.dents?.max_deviation_mm, 1)} mm`} />
        <Stat k="95th percentile" v={`${num(r.dents?.p95_deviation_mm, 1)} mm`} />
        <Stat k={`Area above ${r.dents?.threshold_mm ?? ''} mm`} v={`${num(r.dents?.area_above_threshold_cm2, 1)} cm2`} />
      </Check>
    </div>
  </section>
);

// ---------------------------------------------------------------- history

const asList = (d) => (Array.isArray(d) ? d : d?.scans ?? d?.inspections ?? d?.items ?? []);

const History = ({ q, currentId, onOpen }) => (
  <section className="card">
    <CardTitle sub="Earlier scans, newest first.">Inspection history</CardTitle>
    {!q.data ? (
      <StatusCard q={q} what="The inspection history" />
    ) : asList(q.data).length === 0 ? (
      <p className="text-sm text-ink/60">No scans analyzed yet.</p>
    ) : (
      <ul className="flex max-h-80 flex-col gap-1 overflow-y-auto">
        {asList(q.data).map((s) => (
          <li key={s.id}>
            <button type="button" onClick={() => onOpen(s.id)} aria-current={s.id === currentId ? 'true' : undefined} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${s.id === currentId ? 'bg-accent-soft' : 'hover:bg-ink/5'}`}>
              <Box size={16} className="shrink-0 text-ink/55" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{s.inputs?.mesh || s.name || s.mesh_name || s.mesh?.name || `Scan ${String(s.id).slice(0, 8)}`}</span>
                <span className="block text-xs text-ink/55">{whenIso(s.created)}{s.mesh?.format ? `, ${s.mesh.format}` : ''}</span>
              </span>
              {s.artificial && <span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">artificial defect</span>}
              {s.status && <span className="rounded-full bg-ink/8 px-2 py-0.5 text-[11px] font-semibold text-ink/65">{s.status}</span>}
            </button>
          </li>
        ))}
      </ul>
    )}
  </section>
);

const MODES = ['View damage (3D model)', 'Surface scan'];

// #/inspection/<id>: a_ / demo_ ids are 3D models (View damage), i_ ids are surface scans.
// Phones the alert number now; the Sarvam agent reads out this inspection's findings and takes questions.
const PlaceCall = ({ itemId }) => {
  const [state, setState] = useState({ busy: false, ok: null, text: '', callId: null });
  useEffect(() => setState({ busy: false, ok: null, text: '', callId: null }), [itemId]);
  const call = async () => {
    setState({ busy: true, ok: null, text: '' });
    try {
      const r = await post('/api/alerts/call', { id: itemId }, { signal: AbortSignal.timeout(30000) });
      const res = r.results?.[0];
      setState({ busy: false, ok: !!res?.ok, callId: res?.ok ? res.attempt_id : null,
        text: res?.ok ? `${r.findings} finding${r.findings === 1 ? '' : 's'} reported` : res?.result || 'Call not placed' });
    } catch (e) {
      setState({ busy: false, ok: false, text: errText(e) });
    }
  };
  return (
    <div className="flex items-center gap-3">
      {state.callId && <CallStatus id={state.callId} />}
      {state.text && (
        <span role="status" className={`hidden max-w-xs truncate text-sm font-medium sm:block ${state.ok ? 'text-white/80' : 'text-bad'}`} title={state.text}>
          {state.text}
        </span>
      )}
      <div className="rounded-full bg-black/25 p-1 ring-1 ring-white/10">
        <button
          type="button"
          onClick={call}
          disabled={!itemId || state.busy}
          title={itemId ? "Call the alert number with this inspection's report" : 'Open a model or scan first'}
          className="flex items-center gap-2 rounded-full bg-accent px-3.5 py-1.5 text-sm font-medium text-on-accent transition-opacity disabled:opacity-40"
        >
          {state.busy ? <LoaderCircle size={15} className="animate-spin" /> : state.ok ? <CheckIcon size={15} /> : <PhoneCall size={15} />}
          {state.busy ? 'Calling...' : 'Place call'}
        </button>
      </div>
    </div>
  );
};

const Inspection = ({ id }) => {
  const scanId = id?.startsWith('i_') ? id : null;
  const [mode, setMode] = useState(scanId ? MODES[1] : MODES[0]);
  const [current, setCurrent] = useState({});
  const track = (m) => (itemId) => setCurrent((c) => (c[m] === itemId ? c : { ...c, [m]: itemId }));
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone="info">
        <strong>Separate capability, not part of root-cause analysis.</strong> These views look at a part&apos;s 3D model or scan. They do not feed the ranking, the safe windows or the savings. Sample models carry simulated damage and thermal data; scans are analyzed after upload.
      </Banner>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs dark tabs={MODES} active={mode} onChange={setMode} />
        <PlaceCall itemId={current[mode]} />
      </div>
      {mode === MODES[0] ? <DamagePanel id={scanId ? undefined : id} onCurrent={track(MODES[0])} /> : <SurfaceScan openId={scanId} onCurrent={track(MODES[1])} />}
    </div>
  );
};

const SurfaceScan = ({ openId, onCurrent }) => {
  const [tab, setTab] = useState(TABS[0]);
  const [result, setResult] = useState(null);
  useEffect(() => onCurrent?.(result?.id), [result?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const history = useApi('/api/inspection');
  useLiveRefetch('inspections', history.refetch);

  const onResult = (r) => {
    setResult(r);
    history.refetch();
  };
  const open = async (id) => {
    setError('');
    try {
      setResult(await api(`/api/inspection/${encodeURIComponent(id)}`));
    } catch (e) {
      setError(`Could not open that scan: ${errText(e)}`);
    }
  };
  useEffect(() => {
    if (openId) open(openId);
  }, [openId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <div className="grid gap-[var(--gap)] xl:grid-cols-[minmax(0,1fr)_minmax(0,1.7fr)]">
        <div className="flex flex-col gap-[var(--gap)]">
          <section className="card" aria-busy={busy}>
            <CardTitle sub={SENSOR_NOTE}>Scan a part</CardTitle>
            <div className="mb-4"><Tabs tabs={TABS} active={tab} onChange={setTab} /></div>
            {tab === TABS[0] ? <UploadForm busy={busy} setBusy={setBusy} setError={setError} onResult={onResult} /> : <SampleForm busy={busy} setBusy={setBusy} setError={setError} onResult={onResult} />}
            {busy && <p role="status" className="mt-3 flex items-center gap-2 text-sm text-ink/65"><LoaderCircle size={15} className="animate-spin" /> Analyzing the scan. Large meshes can take a while.</p>}
          </section>
          <History q={history} currentId={result?.id} onOpen={open} />
        </div>
        <div className="flex min-w-0 flex-col gap-[var(--gap)]">
          {error && <p role="alert" className="rounded-2xl bg-bad/20 px-4 py-3 text-sm font-medium text-white ring-1 ring-bad/40">{error}</p>}
          {result ? (
            <Result r={result} />
          ) : (
            <section className="card grid place-items-center py-16 text-center">
              <span className="grid size-12 place-items-center rounded-2xl bg-accent/15 text-accent-deep"><Box size={22} /></span>
              <p className="mt-4 font-medium">No scan analyzed yet</p>
              <p className="mt-1 max-w-sm text-sm text-ink/60">Upload a scan or pick one from the samples. The 3D view and the crack and dent summaries appear here.</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
};

export default Inspection;

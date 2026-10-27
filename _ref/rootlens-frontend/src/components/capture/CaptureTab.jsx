import { useLiveRefetch } from '../../lib/useLiveRefetch';
import { useState } from 'react';
import { Camera, CircleAlert, CircleCheck, CircleX, ExternalLink, ImageUp, LoaderCircle, RotateCw } from 'lucide-react';
import { CardTitle } from '../ui';
import Gate, { StatusCard } from '../ui/Gate';
import WebcamCard from './WebcamCard';
import { BandChip, ScoreBody } from '../RunResult';
import { api, apiUrl, post, postForm } from '../../lib/api';
import { pct } from '../../lib/format';
import { useApi } from '../../lib/useApi';

const STATUS = {
  ok: { label: 'Read OK', cls: 'bg-good/12 text-good' },
  needs_review: { label: 'Needs review', cls: 'bg-warn/15 text-warn' },
  failed: { label: 'Failed', cls: 'bg-bad/12 text-bad' },
};

const StatusChip = ({ status }) => {
  const s = STATUS[status] ?? { label: status, cls: 'bg-ink/8 text-ink/65' };
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${s.cls}`}>{s.label}</span>;
};

const whenIso = (ts) => {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? String(ts ?? '') : d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
};

const errText = (e) => (e?.name === 'TimeoutError' ? 'The API took too long to answer.' : e?.message || 'Could not reach the API.');

// ---------------------------------------------------------------- upload + demo sheet

const DemoSheet = () => {
  const runs = useApi('/api/runs?split=test&fails_only=true&limit=200');
  const list = runs.data?.runs ?? [];
  const index = list.length ? list[list.length - 1].index : null;
  if (index === null) return null;
  return (
    <a href={apiUrl(`/api/run-sheet?index=${index}&format=png`)} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-deep underline-offset-2 hover:underline">
      Get demo run sheet (failed run {index}) <ExternalLink size={13} />
    </a>
  );
};

const UploadCard = ({ onFile, busy }) => {
  const pick = (e) => {
    const f = e.target.files?.[0];
    if (f) onFile(f);
    e.target.value = '';
  };
  return (
    <section className="card">
      <CardTitle sub="Photograph a run sheet on the phone app, or pick a photo here. The vision model reads numbers only.">Upload a photo</CardTitle>
      <label className={`flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-ink/15 px-4 py-9 text-center text-sm transition-colors hover:border-accent hover:bg-accent-soft/40 ${busy ? 'pointer-events-none opacity-60' : ''}`}>
        {busy ? <LoaderCircle size={24} className="animate-spin text-ink/55" /> : <ImageUp size={24} className="text-ink/55" />}
        <span className="font-semibold">{busy ? 'Reading the sheet...' : 'Choose a photo of the run sheet'}</span>
        <span className="text-xs text-ink/55">JPG or PNG. It is sent to your own RootLens API.</span>
        <input type="file" accept="image/jpeg,image/png" capture="environment" onChange={pick} className="sr-only" disabled={busy} />
      </label>
      <p className="mt-3"><DemoSheet /></p>
    </section>
  );
};

// ---------------------------------------------------------------- result

const ChainLog = ({ log, provider, model }) => {
  if (!log?.length) return null;
  return (
    <div className="mt-4">
      <h3 className="text-sm font-semibold">Which provider answered</h3>
      <p className="text-xs text-ink/60">{provider ? `${provider}${model ? ` / ${model}` : ''} gave the final reading.` : 'No provider produced a reading.'} Providers are tried in order until one reads the sheet.</p>
      <ol className="mt-2 flex flex-col gap-1 text-xs">
        {log.map((c, i) => (
          <li key={i} className="grid grid-cols-[1rem_1fr_auto] items-start gap-2 rounded-lg bg-ink/5 px-2.5 py-1.5">
            {c.ok ? <CircleCheck size={14} className="mt-px text-good" /> : <CircleX size={14} className="mt-px text-bad" />}
            <span className="min-w-0"><span className="font-semibold">{c.provider}</span> <span className="text-ink/55">{c.model}</span>{c.error && <span className="block break-words text-bad">{c.error}</span>}</span>
            <span className="tabular text-ink/55">{Math.round(c.ms)} ms</span>
          </li>
        ))}
      </ol>
    </div>
  );
};

const ValuesTable = ({ cap, rescoring, onRescore }) => {
  const ex = cap.extracted ?? { values: {}, unreadable: [] };
  const unreadable = new Set(ex.unreadable ?? []);
  const unknown = new Set(cap.result?.unknown_parameters ?? []);
  const flagged = new Set(Array.isArray(cap.result?.needs_review) ? cap.result.needs_review : []);
  const ids = [...new Set([...Object.keys(ex.values ?? {}), ...unreadable])];
  const [draft, setDraft] = useState(() => Object.fromEntries(ids.map((id) => [id, ex.values?.[id] ?? ''])));
  const filled = Object.entries(draft).filter(([, v]) => v !== '' && Number.isFinite(Number(v)));
  const changed = filled.length !== Object.keys(ex.values ?? {}).length || filled.some(([id, v]) => Number(v) !== ex.values?.[id]);
  if (!ids.length) return <p className="text-sm text-ink/60">No values were read from this photo.</p>;
  return (
    <div>
      <div className="max-h-80 overflow-y-auto rounded-xl ring-1 ring-ink/10">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-card text-xs text-ink/55">
            <tr><th className="px-3 py-2 font-medium">Parameter</th><th className="px-3 py-2 font-medium">Value read</th><th className="px-3 py-2 font-medium">Check</th></tr>
          </thead>
          <tbody>
            {ids.map((id) => {
              const bad = unreadable.has(id);
              const odd = unknown.has(id);
              const review = !bad && !odd && flagged.has(id);
              return (
                <tr key={id} className={`border-t border-ink/10 ${bad ? 'bg-bad/10' : odd || review ? 'bg-warn/10' : ''}`}>
                  <td className="px-3 py-1.5 font-mono font-semibold">{id}</td>
                  <td className="px-3 py-1.5">
                    <input
                      type="number"
                      step="any"
                      aria-label={`Value of ${id}`}
                      value={draft[id] ?? ''}
                      onChange={(e) => setDraft((d) => ({ ...d, [id]: e.target.value }))}
                      placeholder={bad ? 'unreadable' : ''}
                      className={`tabular h-8 w-32 rounded-lg border bg-white px-2 text-sm ${bad ? 'border-bad' : 'border-line'} focus:border-accent focus:outline-none`}
                    />
                  </td>
                  <td className="px-3 py-1.5 text-xs font-semibold">
                    {bad ? <span className="text-bad">Unreadable, enter by hand</span> : odd ? <span className="text-warn">Not a model parameter</span> : review ? <span className="text-warn">Check against the photo</span> : <span className="text-ink/45">Read</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button type="button" disabled={rescoring || !filled.length} onClick={() => onRescore(Object.fromEntries(filled.map(([id, v]) => [id, Number(v)])), ex.run_id)} className="btn-primary mt-3">
        {rescoring ? <LoaderCircle size={16} className="animate-spin" /> : <RotateCw size={16} />} Re-score{changed ? ' with my edits' : ''}
      </button>
    </div>
  );
};

const Result = ({ cap, onRescore, rescoring, rescoreError }) => {
  const r = cap.result;
  return (
    <section className="card" aria-live="polite">
      <CardTitle
        sub={`${whenIso(cap.created)}, via ${cap.source}${cap.provider ? `, read by ${cap.provider}${cap.model ? ` / ${cap.model}` : ''}` : ''}.${cap.label ? ` ${cap.label}` : ''}`}
        action={<span className="flex items-center gap-2"><StatusChip status={cap.status} />{r && <BandChip band={r.risk_band} />}</span>}
      >
        Capture result
      </CardTitle>
      {cap.status === 'needs_review' && (
        <p className="mb-3 flex items-start gap-2 rounded-xl bg-warn/15 px-3 py-2 text-sm font-medium"><CircleAlert size={16} className="mt-0.5 shrink-0" /> Some values could not be read with confidence. Compare the table with the photo, fix anything wrong and re-score.</p>
      )}
      {cap.status === 'failed' && (
        <p role="alert" className="mb-3 flex items-start gap-2 rounded-xl bg-bad/12 px-3 py-2 text-sm font-medium"><CircleX size={16} className="mt-0.5 shrink-0" /> The sheet could not be read. Retake the photo, or enter the values by hand below.</p>
      )}
      <div className={`grid gap-5 ${cap.image_url ? 'lg:grid-cols-[minmax(0,14rem)_1fr]' : ''}`}>
        {cap.image_url && <img src={apiUrl(cap.image_url)} alt="The photo that was read" className="max-h-72 w-full rounded-xl object-contain ring-1 ring-ink/10 lg:max-h-none" />}
        <div className="min-w-0">
          <h3 className="mb-2 text-sm font-semibold">Values read from the sheet</h3>
          <ValuesTable key={cap.id} cap={cap} rescoring={rescoring} onRescore={onRescore} />
          {rescoreError && <p role="alert" className="mt-2 text-sm font-medium text-bad">{rescoreError}</p>}
        </div>
      </div>
      <ChainLog log={cap.chain_log} provider={cap.provider} model={cap.model} />
      {r ? (
        <div className="mt-5 border-t border-ink/10 pt-4">
          <ScoreBody r={r} />
          {r.unknown_parameters?.length > 0 && <p className="mt-2 text-xs text-warn">Not used for the score because the model does not know them: {r.unknown_parameters.join(', ')}.</p>}
          {r.suspect_sensors?.length > 0 && <p className="mt-2 text-xs text-warn">Check these sensors before trusting this run: {r.suspect_sensors.map((x) => `${x.sensor} (${x.reasons[0]})`).join('; ')}. The sensor health monitor flags them as bad; their readings were still used.</p>}
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink/60">No score yet. Fix the values above or use manual entry.</p>
      )}
    </section>
  );
};

// ---------------------------------------------------------------- manual entry + history

const ManualForm = ({ onSubmit, busy }) => {
  const q = useApi('/api/run-sheet/fields');
  const [vals, setVals] = useState({});
  const [runId, setRunId] = useState('');
  return (
    <section className="card">
      <CardTitle sub="No photo, or the reading was poor: type the values from the sheet. Leave out anything you cannot read.">Manual entry</CardTitle>
      <Gate q={q} what="The run-sheet fields">
        {({ fields }) => {
          const filled = Object.entries(vals).filter(([, v]) => v !== '' && Number.isFinite(Number(v)));
          return (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                onSubmit(Object.fromEntries(filled.map(([k, v]) => [k, Number(v)])), runId.trim() || undefined);
              }}
            >
              <div className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-3">
                {fields.map((f) => (
                  <label key={f} className="flex flex-col gap-1 text-xs">
                    <span className="font-mono font-semibold">{f}</span>
                    <input type="number" step="any" value={vals[f] ?? ''} onChange={(e) => setVals((v) => ({ ...v, [f]: e.target.value }))} className="field tabular h-9" />
                  </label>
                ))}
              </div>
              <label className="mt-3 flex max-w-xs flex-col gap-1 text-xs">
                <span className="font-medium">Run id (optional)</span>
                <input value={runId} onChange={(e) => setRunId(e.target.value)} className="field h-9" />
              </label>
              <button type="submit" disabled={busy || !filled.length} className="btn-primary mt-3">
                {busy ? <LoaderCircle size={16} className="animate-spin" /> : <Camera size={16} />} Score these values
              </button>
            </form>
          );
        }}
      </Gate>
    </section>
  );
};

const History = ({ q, currentId, onOpen }) => (
  <section className="card">
    <CardTitle sub="Earlier captures, newest first. Open one to see its reading and score again.">Capture history</CardTitle>
    {!q.data ? (
      <StatusCard q={q} what="The capture history" />
    ) : q.data.captures.length === 0 ? (
      <p className="text-sm text-ink/60">Nothing captured yet.</p>
    ) : (
      <ul className="flex max-h-[26rem] flex-col gap-1 overflow-y-auto">
        {q.data.captures.map((c) => (
          <li key={c.id}>
            <button type="button" onClick={() => onOpen(c.id)} aria-current={c.id === currentId ? 'true' : undefined} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${c.id === currentId ? 'bg-accent-soft' : 'hover:bg-ink/5'}`}>
              <Camera size={16} className="shrink-0 text-ink/55" />
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{c.run_id ? `Run ${c.run_id}` : 'Capture'} <span className="font-normal text-ink/55">({c.source})</span></span>
                <span className="block text-xs text-ink/55">{whenIso(c.created)}</span>
              </span>
              {typeof c.fail_probability === 'number' && <span className="tabular text-sm font-semibold" title="model-estimated">{pct(c.fail_probability, 0)}</span>}
              <BandChip band={c.risk_band} className="hidden sm:inline" />
              <StatusChip status={c.status} />
            </button>
          </li>
        ))}
      </ul>
    )}
  </section>
);

const CaptureTab = () => {
  const [cap, setCap] = useState(null);
  const [busy, setBusy] = useState(false); // reading a photo
  const [scoring, setScoring] = useState(false); // manual values or a re-score
  const [error, setError] = useState('');
  const [rescoreError, setRescoreError] = useState('');
  const history = useApi('/api/captures');
  useLiveRefetch('captures', history.refetch);

  const done = (r) => {
    setCap(r);
    history.refetch();
  };

  const send = async (blob, source, name) => {
    setBusy(true);
    setError('');
    setCap(null);
    try {
      const form = new FormData();
      form.append('file', blob, name);
      form.append('source', source);
      done(await postForm('/api/captures', form));
    } catch (e) {
      setError(`The photo could not be read: ${errText(e)}`);
    } finally {
      setBusy(false);
    }
  };

  const score = async (values, runId, fromResult) => {
    setScoring(true);
    setError('');
    setRescoreError('');
    try {
      done(await post('/api/captures/manual', { values, ...(runId ? { run_id: runId } : {}) }));
    } catch (e) {
      (fromResult ? setRescoreError : setError)(`Could not score those values: ${errText(e)}`);
    } finally {
      setScoring(false);
    }
  };

  const open = async (id) => {
    setError('');
    try {
      setCap(await api(`/api/captures/${encodeURIComponent(id)}`));
    } catch (e) {
      setError(`Could not open that capture: ${errText(e)}`);
    }
  };

  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <div className="grid gap-[var(--gap)] lg:grid-cols-2">
        <UploadCard busy={busy} onFile={(f) => send(f, 'upload', f.name)} />
        <WebcamCard busy={busy} onCapture={(blob) => send(blob, 'webcam', 'webcam.jpg')} />
      </div>
      {error && <p role="alert" className="rounded-2xl bg-bad/20 px-4 py-3 text-sm font-medium text-white ring-1 ring-bad/40">{error}</p>}
      {cap && <Result key={cap.id} cap={cap} rescoring={scoring} rescoreError={rescoreError} onRescore={(v, run) => score(v, run, true)} />}
      <div className="grid gap-[var(--gap)] xl:grid-cols-2">
        <ManualForm busy={scoring} onSubmit={(v, run) => score(v, run, false)} />
        <History q={history} currentId={cap?.id} onOpen={open} />
      </div>
    </div>
  );
};

export default CaptureTab;

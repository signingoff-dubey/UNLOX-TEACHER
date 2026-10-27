import { useState } from 'react';
import { Camera } from 'lucide-react';
import { CardTitle, ChipToggle, Tabs } from '../components/ui';
import Gate, { StatusCard } from '../components/ui/Gate';
import CaptureTab from '../components/capture/CaptureTab';
import { BandChip, ScoreBody } from '../components/RunResult';
import { pct } from '../lib/format';
import { navigate } from '../lib/router';
import { useApi } from '../lib/useApi';

// "2008-10-06 03:50:00" is a plain local timestamp, so it is shown as written rather than shifted by the browser's zone.
const when = (ts) => ts.slice(0, 16);

const Result = ({ c }) => (
  <section className="card" aria-live="polite">
    <CardTitle sub={`${when(c.timestamp)}, recorded as ${c.fail ? 'failed' : 'passed'}. Alert threshold ${pct(c.threshold, 0)}.`} action={<BandChip band={c.risk_band} />}>
      Run {c.index}
    </CardTitle>
    <ScoreBody r={c} />
  </section>
);

const Detail = ({ id }) => {
  const q = useApi(`/api/runs/${encodeURIComponent(id)}`);
  return <Gate q={q} what="This run">{(c) => <Result c={c} />}</Gate>;
};

const RunHistory = ({ id, runs, onlyFails, setOnlyFails }) => {
  const list = runs.runs;
  // A run opened from a link may not be in the filtered list; it is still fetched by id.
  const selected = id && id !== 'history' ? id : list.length ? String(list[list.length - 1].index) : undefined;
  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_1.4fr]">
      <section className="card">
        <CardTitle
          sub="Runs in the test window, newest first. The probability beside each run is the model's own estimate."
          action={<ChipToggle multiple={false} value={onlyFails ? 'fails' : 'all'} onChange={(v) => setOnlyFails(v === 'fails')} options={[{ id: 'fails', label: 'Failed runs' }, { id: 'all', label: 'All runs' }]} />}
        >
          Run history
        </CardTitle>
        <ul className="flex max-h-[34rem] flex-col gap-1 overflow-y-auto">
          {[...list].reverse().map((c) => (
            <li key={c.index}>
              <button
                type="button"
                onClick={() => navigate('captures', String(c.index))}
                aria-current={String(c.index) === selected ? 'true' : undefined}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${String(c.index) === selected ? 'bg-accent-soft' : 'hover:bg-ink/5'}`}
              >
                <Camera size={16} className="shrink-0 text-ink/55" />
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">Run {c.index}</span>
                  <span className="block text-xs text-ink/55">{when(c.timestamp)}</span>
                </span>
                <span className="tabular text-sm font-semibold" title="model-estimated">{pct(c.fail_prob, 0)}</span>
                <BandChip band={c.risk_band} className="hidden sm:inline" />
                <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${c.fail ? 'bg-bad text-white' : 'bg-ink/8 text-ink/65'}`}>{c.fail ? 'Failed' : 'Passed'}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {selected ? <Detail key={selected} id={selected} /> : <section className="card text-sm text-ink/65">No runs to show.</section>}
    </div>
  );
};

const History = ({ id }) => {
  const [onlyFails, setOnlyFails] = useState(true);
  const q = useApi(`/api/runs?split=test&fails_only=${onlyFails}&limit=300`);
  if (!q.data) return <StatusCard q={q} what="The run history" />;
  return <RunHistory id={id} runs={q.data} onlyFails={onlyFails} setOnlyFails={setOnlyFails} />;
};

const TABS = ['Capture a sheet', 'Run history'];

// #/captures opens the capture tab; #/captures/<run index> and #/captures/history open the run history.
const Captures = ({ id }) => {
  const [tab, setTab] = useState(id ? TABS[1] : TABS[0]);
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Tabs tabs={TABS} active={tab} onChange={setTab} dark />
      {tab === TABS[0] ? <CaptureTab /> : <History id={id} />}
    </div>
  );
};

export default Captures;

import { useEffect, useRef, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { Banner, CardTitle, Tabs } from '../components/ui';
import Gate from '../components/ui/Gate';
import { num, pct, rupees } from '../lib/format';
import { post } from '../lib/api';
import { isRecommended } from '../components/RunResult';
import { useApi } from '../lib/useApi';

const SLIDERS = [
  { key: 'volume_per_day', label: 'Parts per day', min: 100, max: 20000, step: 100, fmt: (v) => num(v, 0) },
  { key: 'pilot_share', label: 'Share of output used for the pilot', min: 0.05, max: 0.5, step: 0.05, fmt: (v) => pct(v, 0) },
  { key: 'cost_per_pilot_part', label: 'Extra cost per pilot part', min: 0, max: 500, step: 5, fmt: rupees },
  { key: 'scrap_cost_per_part', label: 'Scrap cost per part', min: 50, max: 10000, step: 50, fmt: rupees },
  { key: 'power', label: 'Power (chance to detect a real effect)', min: 0.6, max: 0.95, step: 0.05, fmt: (v) => pct(v, 0) },
];

const SCENARIOS = [
  { id: 'optimistic', label: 'Optimistic', sub: 'Largest plausible effect' },
  { id: 'central', label: 'Central', sub: 'Best-estimate effect' },
  { id: 'pessimistic', label: 'Pessimistic', sub: 'Smallest plausible effect' },
];

const Slider = ({ s, value, onChange }) => (
  <label className="block text-sm">
    <span className="flex justify-between gap-3">
      <span className="font-medium">{s.label}</span>
      <span className="tabular shrink-0 font-semibold">{s.fmt(value)}</span>
    </span>
    <input type="range" min={s.min} max={s.max} step={s.step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="mt-1.5" />
  </label>
);

const Scenario = ({ meta, sc, strong }) => (
  <div className={`rounded-2xl p-4 ${strong ? 'bg-accent text-on-accent' : 'bg-ink/5'}`}>
    <p className="text-sm font-semibold">{meta.label}</p>
    <p className={`text-xs ${strong ? 'opacity-80' : 'text-ink/55'}`}>{meta.sub}</p>
    {sc.feasible ? (
      <>
        <p className="tabular mt-3 text-2xl font-bold tracking-tight">{num(sc.parts_per_arm, 0)} <span className="text-sm font-medium">parts per arm</span></p>
        <dl className={`mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs ${strong ? '' : 'text-ink/70'}`}>
          <div><dt className="opacity-70">Total parts</dt><dd className="tabular text-sm font-semibold">{num(sc.total_parts, 0)}</dd></div>
          <div><dt className="opacity-70">Days</dt><dd className="tabular text-sm font-semibold">{num(sc.days, 1)}</dd></div>
          <div><dt className="opacity-70">Pilot cost</dt><dd className="tabular text-sm font-semibold">{rupees(sc.pilot_cost)}</dd></div>
          <div><dt className="opacity-70">Fail rate to confirm</dt><dd className="tabular text-sm font-semibold">{pct(sc.p_control)} to {pct(sc.p_treat)}</dd></div>
        </dl>
        {typeof sc.scrap_saved_during_pilot === 'number' && (
          <p className={`mt-3 text-xs ${strong ? 'opacity-80' : 'text-ink/60'}`}>Scrap avoided during the pilot: {rupees(sc.scrap_saved_during_pilot)} (model estimate)</p>
        )}
      </>
    ) : (
      <p className="mt-3 text-sm font-medium">{sc.reason || 'Not feasible: the effect is too small to confirm at this volume.'}</p>
    )}
  </div>
);

const Body = ({ data, windows }) => {
  const defaults = data.defaults;
  const features = data.plans.map((p) => p.feature);
  const [feature, setFeature] = useState(features[0]);
  const [p, setP] = useState(defaults);
  const [res, setRes] = useState({ plan: null, error: null, busy: false });
  const untouched = useRef(true);
  const set = (k) => (v) => {
    untouched.current = false;
    setP((cur) => ({ ...cur, [k]: v }));
  };

  const initial = data.plans.find((x) => x.feature === feature) ?? data.plans[0];

  // The first answer is already in /api/pilots. Once a slider moves, ask the backend; its formula is the source of truth.
  useEffect(() => {
    if (untouched.current) {
      setRes({ plan: null, error: null, busy: false });
      return undefined;
    }
    const ctl = new AbortController();
    const t = setTimeout(() => {
      setRes((r) => ({ ...r, busy: true }));
      post('/api/pilot', { feature, ...p }, { signal: ctl.signal })
        .then((plan) => setRes({ plan, error: null, busy: false }))
        .catch((error) => !ctl.signal.aborted && setRes((r) => ({ ...r, error, busy: false })));
    }, 250);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [feature, p]);

  const plan = res.plan ?? initial;
  const win = windows?.find((w) => w.feature === feature);
  const reset = () => {
    untouched.current = true;
    setP(defaults);
    setRes({ plan: null, error: null, busy: false });
  };

  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone="info">A pilot does not prove the suggestion works on its own; it confirms or rejects a statistically suspected effect on the line, with the run counts below.</Banner>
      {win && !isRecommended(win) && (
        <Banner tone="warn">The safe window for {feature} is not recommended ({win.status}). A pilot here would test a suspected effect that did not hold up in the checks, so treat the numbers below as what it would take to find out, not as a go-ahead.</Banner>
      )}
      <Tabs tabs={features} active={feature} onChange={(f) => { setFeature(f); setRes((r) => ({ ...r, plan: null })); }} dark />
      <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_1.6fr]">
        <section className="card">
          <CardTitle sub={`Window under test: ${num(plan.window[0], 3)} to ${num(plan.window[1], 3)}.`} action={<button type="button" onClick={reset} className="btn-ghost h-8 px-3 text-xs"><RotateCcw size={13} /> Reset</button>}>
            Pilot settings for <span className="font-mono">{feature}</span>
          </CardTitle>
          <div className="flex flex-col gap-4">
            {SLIDERS.map((s) => <Slider key={s.key} s={s} value={p[s.key]} onChange={set(s.key)} />)}
          </div>
          <p className="mt-4 text-xs text-ink/55">Significance level {pct(p.alpha ?? defaults.alpha, 0)}. Settings go only to your own RootLens API.</p>
        </section>

        <div className="flex flex-col gap-[var(--gap)]">
          <section className="card" aria-busy={res.busy}>
            <CardTitle sub="Three assumptions about how big the real effect is. A smaller effect needs more parts." action={<span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">model estimate</span>}>
              What the pilot takes
            </CardTitle>
            <div className={`grid gap-3 md:grid-cols-3 ${res.busy ? 'opacity-60' : ''}`}>
              {SCENARIOS.map((m) => plan.scenarios[m.id] && <Scenario key={m.id} meta={m} sc={plan.scenarios[m.id]} strong={m.id === 'central'} />)}
            </div>
            {res.error && <p role="alert" className="mt-3 rounded-xl bg-bad/12 px-3 py-2 text-sm font-medium">Could not update the plan: {res.error.message}. Showing the last result.</p>}
          </section>
          <section className="card">
            <CardTitle>In one sentence</CardTitle>
            <p className="text-sm leading-relaxed">{plan.summary}</p>
            <p className="mt-2 text-xs text-ink/60">{plan.label}. Run the two arms side by side, in the same period, so shifts in the line do not look like an effect.</p>
          </section>
        </div>
      </div>
    </div>
  );
};

const Pilot = () => {
  const q = useApi('/api/pilots');
  const sw = useApi('/api/safe-windows');
  return <Gate q={q} what="The pilot planner">{(d) => (d.plans?.length ? <Body data={d} windows={sw.data?.windows} /> : <section className="card text-sm text-ink/65">No recommended window to pilot yet.</section>)}</Gate>;
};

export default Pilot;

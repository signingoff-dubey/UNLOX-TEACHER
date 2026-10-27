import { useEffect, useRef, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { CardTitle, Toggle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { COST_LIMITS } from '../lib/cost';
import { num, pct, rupees } from '../lib/format';
import { post } from '../lib/api';
import { useApi } from '../lib/useApi';

const LIMITS = { ...COST_LIMITS, falseAlarmsPerDay: { min: 0, max: 200, step: 1 } };

// The backend (backend/ml/cost.py) is the source of truth for the savings formula; this page only sends the assumptions.
const toRequest = (p) => ({
  volume_per_day: p.volumePerDay,
  scrap_cost_per_part: p.scrapCostPerPart,
  false_alarm_cost: p.falseAlarmCost,
  days_per_month: p.daysPerMonth,
  false_alarms_per_day: p.gated ? p.falseAlarmsPerDay : 0,
});

// Same defaults as the API's SavingsRequest.
const DEFAULTS = { volumePerDay: 1000, scrapCostPerPart: 500, falseAlarmCost: 50, daysPerMonth: 26, falseAlarmsPerDay: 0, gated: false };

const fromAssumptions = (a) => ({
  volumePerDay: a.volume_per_day,
  scrapCostPerPart: a.scrap_cost_per_part,
  falseAlarmCost: a.false_alarm_cost,
  daysPerMonth: a.days_per_month,
  falseAlarmsPerDay: a.false_alarms_per_day,
  gated: a.false_alarms_per_day > 0,
});

const SLIDERS = [
  { key: 'volumePerDay', label: 'Parts per day', fmt: (v) => num(v, 0) },
  { key: 'scrapCostPerPart', label: 'Scrap cost per part', fmt: rupees },
  { key: 'daysPerMonth', label: 'Working days per month', fmt: (v) => v },
  { key: 'falseAlarmCost', label: 'Cost of one false alarm', fmt: rupees, gated: true },
  { key: 'falseAlarmsPerDay', label: 'False alarms per day', fmt: (v) => num(v, 0), gated: true },
];

const Slider = ({ s, value, onChange, disabled }) => {
  const lim = LIMITS[s.key];
  return (
    <label className={`block text-sm ${disabled ? 'opacity-45' : ''}`}>
      <span className="flex justify-between">
        <span className="font-medium">{s.label}</span>
        <span className="tabular font-semibold">{s.fmt(value)}</span>
      </span>
      <input type="range" min={lim.min} max={lim.max} step={lim.step} value={value} disabled={disabled} onChange={(e) => onChange(Number(e.target.value))} className="mt-1.5" />
    </label>
  );
};

const Result = ({ label, r, strong }) => (
  <div className={`rounded-2xl p-4 ${strong ? 'bg-accent text-on-accent' : 'bg-ink/5'}`}>
    <p className={`text-xs font-medium ${strong ? 'opacity-80' : 'text-ink/60'}`}>{label}</p>
    <p className="tabular mt-1 text-2xl font-bold tracking-tight">{rupees(r.savings_per_month)}</p>
    <p className={`tabular mt-1 text-xs ${strong ? 'opacity-80' : 'text-ink/60'}`}>{num(r.avoided_scrap_parts_per_month, 0)} scrap parts avoided</p>
  </div>
);

const Body = ({ initial, verdicts, baseline }) => {
  const priced = Boolean(initial.low); // the default endpoint answers 200 with only a note when no window can be priced
  const defaults = priced ? fromAssumptions(initial.assumptions) : DEFAULTS;
  const [p, setP] = useState(defaults);
  const [res, setRes] = useState({ data: priced ? initial : null, error: priced ? null : { status: 404, message: initial.note }, busy: false });
  const initialP = useRef(p);
  const set = (k) => (v) => setP((cur) => ({ ...cur, [k]: v }));

  // Ask the backend whenever the assumptions settle. The first render already has the default answer.
  useEffect(() => {
    if (p === initialP.current) return undefined;
    const ctl = new AbortController();
    const t = setTimeout(() => {
      setRes((r) => ({ ...r, busy: true }));
      post('/api/savings', toRequest(p), { signal: ctl.signal })
        .then((data) => setRes({ data, error: null, busy: false }))
        .catch((error) => !ctl.signal.aborted && setRes((r) => ({ ...r, data: error.status === 404 ? null : r.data, error, busy: false })));
    }, 250);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [p]);

  const out = res.data;
  const a = out?.assumptions;
  const verdict = out && verdicts[out.based_on];
  const noWindow = res.error?.status === 404;
  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_1.2fr]">
      <section className="card">
        <CardTitle
          sub="Your line's numbers. They are sent only to your own RootLens API."
          action={
            <button type="button" onClick={() => setP(defaults)} className="btn-ghost h-8 px-3 text-xs">
              <RotateCcw size={13} /> Reset
            </button>
          }
        >
          Assumptions
        </CardTitle>
        <div className="flex flex-col gap-4">
          {SLIDERS.map((s) => <Slider key={s.key} s={s} value={p[s.key]} onChange={set(s.key)} disabled={s.gated && !p.gated} />)}
          <div className="flex items-center justify-between gap-3 rounded-xl border border-ink/10 px-3 py-2.5 text-sm">
            <span>
              <span className="font-medium">The model gates parts</span>
              <span className="block text-xs text-ink/60">Flagged parts are pulled for inspection, so false alarms cost money.</span>
            </span>
            <Toggle checked={p.gated} onChange={set('gated')} label="The model gates parts" />
          </div>
        </div>
      </section>

      <div className="flex flex-col gap-[var(--gap)]">
        <section className="card" aria-busy={res.busy}>
          <CardTitle
            sub={out ? `Per month, in ${out.currency}, after false-alarm cost. Low and high come from the confidence interval of the fail-rate reduction. Based on ${out.based_on}.` : 'Per month, as a low to high range.'}
            action={<span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">{out?.label ?? 'model estimate'}</span>}
          >
            Model-estimated savings
          </CardTitle>
          {out && (
            <div className={`grid gap-3 sm:grid-cols-3 ${res.busy ? 'opacity-60' : ''}`}>
              <Result label={`Low (${pct(a.reduction_low, 0)} fewer fails)`} r={out.low} />
              <Result label={`Mid (${pct(a.reduction_mid, 0)} fewer fails)`} r={out.mid} strong />
              <Result label={`High (${pct(a.reduction_high, 0)} fewer fails)`} r={out.high} />
            </div>
          )}
          {out && out.low.savings_per_month < 0 && <p className="mt-3 rounded-xl bg-bad/12 px-3 py-2 text-sm font-medium">At the low end the false alarms cost more than the scrap saved.</p>}
          {noWindow && (
            <p role="alert" className="rounded-xl bg-warn/15 px-3 py-2 text-sm font-medium">
              Nothing to price: {res.error.message}. RootLens will not put a rupee figure on a window it does not recommend.
            </p>
          )}
          {res.error && !noWindow && <p role="alert" className="mt-3 rounded-xl bg-bad/12 px-3 py-2 text-sm font-medium">Could not update the estimate: {res.error.message}. Showing the last result.</p>}
          {verdict && !/held on test/i.test(verdict) && (
            <p className="mt-3 rounded-xl bg-warn/15 px-3 py-2 text-sm font-medium">On the later test window the {out.based_on} window {verdict}, so treat this range as optimistic.</p>
          )}
        </section>
        <section className="card">
          <CardTitle sub="The same formula runs in the backend; this page does not recompute it.">How it is worked out</CardTitle>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm text-ink/80">
            <li>Baseline fail rate is the observed rate on train and validation: <span className="tabular font-semibold">{pct(a?.baseline_fail_rate ?? baseline)}</span>.</li>
            <li>Scrap avoided per day = parts per day × baseline × reduction in fail rate if runs sit inside the recommended window{out ? ` (${out.based_on})` : ''}.</li>
            <li>Gross saving = scrap avoided × scrap cost × working days.</li>
            <li>{p.gated ? <>Minus false alarms: false alarms per day × false-alarm cost × working days {out && <>(<span className="tabular font-semibold">{rupees(out.false_alarm_cost_per_month)}</span> a month)</>}.</> : 'No false-alarm cost: the model is not gating parts.'}</li>
          </ol>
          <p className="mt-3 text-xs text-ink/60">A model estimate under the assumptions above, not a promise. The reduction comes from historical association; a pilot on the line would confirm it.</p>
        </section>
      </div>
    </div>
  );
};

const Savings = () => {
  const q = useApi(['/api/savings/default', '/api/safe-windows']);
  return (
    <Gate q={q} what="The savings model">
      {([def, sw]) => <Body initial={def} baseline={sw.baseline_fail_rate} verdicts={Object.fromEntries(sw.windows.filter((w) => w.test_window_check).map((w) => [w.feature, w.test_window_check.verdict]))} />}
    </Gate>
  );
};

export default Savings;

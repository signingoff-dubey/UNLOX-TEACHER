import { useState } from 'react';
import { Banner, CardTitle, Tabs } from '../components/ui';
import Gate from '../components/ui/Gate';
import { num, pct } from '../lib/format';
import { navigate } from '../lib/router';
import { isRecommended } from '../components/RunResult';
import { useApi } from '../lib/useApi';

// API window -> the shape the cards below draw. bound is the observed operating range (p5 to p95).
const adapt = (x) => ({
  feature: x.feature,
  status: x.status,
  recommended: isRecommended(x),
  bound: x.operating_range,
  median: x.current_median,
  window: x.window,
  nIn: x.fit.n_in,
  rateIn: { value: x.fit.rate_in, ci: x.fit.rate_in_ci },
  nOut: x.fit.n_out,
  rateOut: { value: x.fit.rate_out, ci: x.fit.rate_out_ci },
  bins: x.bins,
  test: x.test_window_check,
  modelEst: x.model_estimate,
  text: x.text,
});

// Position of a value on the bound strip, 0..100.
const at = (w, v) => ((v - w.bound[0]) / (w.bound[1] - w.bound[0])) * 100;

// The observed range (p5..p95) as a strip, the safe window as an accent band, the current median as a tick,
// and an optional what-if marker. Nothing can be drawn outside the strip: the bound is the whole axis.
const Strip = ({ w, value }) => (
  <div>
    <div className="relative h-9 rounded-xl bg-ink/6" aria-hidden="true">
      <span className="absolute inset-y-1 rounded-lg bg-accent/35 ring-1 ring-accent" style={{ left: `${at(w, w.window[0])}%`, width: `${at(w, w.window[1]) - at(w, w.window[0])}%` }} />
      <span className="absolute inset-y-0 w-0.5 bg-ink" style={{ left: `${at(w, w.median)}%` }} />
      {value !== undefined && <span className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-ink shadow" style={{ left: `${at(w, value)}%` }} />}
    </div>
    <div className="tabular mt-1 flex justify-between text-[11px] text-ink/55">
      <span>p5 {num(w.bound[0], 3)}</span>
      <span>p95 {num(w.bound[1], 3)}</span>
    </div>
  </div>
);

// Failure rate with its Wilson CI as a bar on a 0..12% scale.
const RateBar = ({ label, n, rate, strong }) => {
  const s = (v) => `${Math.min(v / 0.12, 1) * 100}%`;
  return (
    <div className="text-xs">
      <div className="flex justify-between">
        <span className="font-medium">{label}</span>
        <span className="tabular text-ink/65">{pct(rate.value)} ({pct(rate.ci[0])} to {pct(rate.ci[1])}), n={n}</span>
      </div>
      <div className="relative mt-1 h-2 rounded-full bg-ink/8">
        <span className={`absolute inset-y-0 rounded-full ${strong ? 'bg-accent/40' : 'bg-ink/20'}`} style={{ left: s(rate.ci[0]), width: `calc(${s(rate.ci[1])} - ${s(rate.ci[0])})` }} />
        <span className={`absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${strong ? 'bg-accent' : 'bg-ink/60'}`} style={{ left: s(rate.value) }} />
      </div>
    </div>
  );
};

const WindowCard = ({ w, active, onPick }) => (
  <section className={`card ${active ? 'ring-2 ring-accent' : ''}`}>
    <CardTitle
      sub={`Current median ${num(w.median, 3)}; lowest-failure window ${num(w.window[0], 3)} to ${num(w.window[1], 3)}.`}
      action={
        <span className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${w.recommended ? 'bg-good/12 text-good' : 'bg-ink/8 text-ink/65'}`}>{w.recommended ? 'Recommended' : 'Not recommended'}</span>
          {onPick && <button type="button" onClick={onPick} className="btn-ghost h-8 px-3 text-xs">Try it</button>}
        </span>
      }
    >
      <span className="font-mono">{w.feature}</span>
    </CardTitle>
    <Strip w={w} />
    <div className="mt-4 flex flex-col gap-2.5">
      <RateBar label="Inside the window" n={w.nIn} rate={w.rateIn} strong />
      <RateBar label="Outside" n={w.nOut} rate={w.rateOut} />
    </div>
    {!w.recommended && <p className="mt-3 text-xs font-medium text-bad">Status: {w.status}. Do not act on this window.</p>}
    <p className="mt-3 rounded-xl bg-ink/5 p-2.5 text-xs text-ink/70">
      Test window check (not used to pick the window): {pct(w.test.rate_in)} inside (n={w.test.n_in}) versus {pct(w.test.rate_out)} outside (n={w.test.n_out}).{' '}
      <span className={`font-semibold ${/held on test/i.test(w.test.verdict) ? 'text-good' : 'text-bad'}`}>{w.test.verdict[0].toUpperCase() + w.test.verdict.slice(1)}.</span>
    </p>
  </section>
);

// What-if: move one driver within its observed range, others fixed. The slider cannot leave p5..p95 (CLAUDE.md rule 6).
const WhatIf = ({ w }) => {
  const [value, setValue] = useState(w.median);
  const inside = value >= w.window[0] && value <= w.window[1];
  // Historical rate in the bin the slider sits in; falls back to inside/outside the window when the bins are missing.
  const bin = w.bins?.find((b, i) => value >= b.window[0] && (value < b.window[1] || (i === w.bins.length - 1 && value <= b.window[1])));
  const hist = bin ? { value: bin.rate, ci: bin.rate_ci } : inside ? w.rateIn : w.rateOut;
  const step = (w.bound[1] - w.bound[0]) / 200;
  return (
    <section className="card">
      <CardTitle sub="Others stay at their medians. The slider stops at the range the line has run.">
        What if <span className="font-mono">{w.feature}</span> moved?
      </CardTitle>
      <Strip w={w} value={value} />
      <label className="mt-3 block text-sm">
        <span className="sr-only">Value of {w.feature}</span>
        <input type="range" min={w.bound[0]} max={w.bound[1]} step={step} value={value} onChange={(e) => setValue(Number(e.target.value))} />
      </label>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl bg-ink/5 p-3">
          <p className="text-xs text-ink/60">Value</p>
          <p className="tabular text-lg font-bold">{num(value, 3)}</p>
          <p className={`text-xs font-semibold ${inside ? 'text-good' : 'text-ink/60'}`}>{inside ? 'Inside the safe window' : 'Outside the safe window'}</p>
        </div>
        <div className="rounded-xl bg-ink/5 p-3">
          <p className="text-xs text-ink/60">Historical fail rate {bin ? `in this range (n=${bin.n})` : 'here'}</p>
          <p className="tabular text-lg font-bold">{pct(hist.value)}</p>
          <p className="tabular text-xs text-ink/60">CI {pct(hist.ci[0])} to {pct(hist.ci[1])}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-ink/65">
        <span className="rounded bg-warn/15 px-1.5 py-0.5 font-semibold text-warn">Model-estimated</span> mean fail probability of the {w.modelEst.rows_shifted} runs outside the window: {pct(w.modelEst.mean_fail_prob_before)} now, {pct(w.modelEst.mean_fail_prob_after)} if they were moved inside. The model scoring its own suggestion is circular; trust the historical rate first.
      </p>
      <p className="mt-2 text-xs font-medium text-ink/70">Association, not proof. Confirm with a pilot on the line.</p>
    </section>
  );
};

const Body = ({ sw, id }) => {
  const windows = sw.windows.filter((x) => x.fit).map(adapt);
  // the URL is the selection: switching parameter (tab, card or back button) never rebuilds the page
  const w = windows.find((x) => x.feature === id) ?? windows[0];
  const pick = (f) => navigate('windows', f);
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone="warn">
        {sw.caveat} Only recommended windows are meant to be acted on; the rest are listed so you can see why they were rejected. Baseline fail rate {pct(sw.baseline_fail_rate)}.
      </Banner>
      <Tabs tabs={windows.map((x) => x.feature)} active={w.feature} onChange={pick} dark />
      <div className="grid gap-[var(--gap)] xl:grid-cols-2">
        <WhatIf key={w.feature} w={w} />
        <div className="flex flex-col gap-[var(--gap)]">
          <WindowCard w={w} active />
          <p className="rounded-2xl bg-black/25 px-4 py-3 text-xs text-white/75 ring-1 ring-white/10">{w.text}</p>
        </div>
      </div>
      <h2 className="mt-2 text-sm font-semibold text-white/75">Other parameters</h2>
      <div className="grid gap-[var(--gap)] lg:grid-cols-2 2xl:grid-cols-3">
        {windows.filter((x) => x.feature !== w.feature).map((x) => <WindowCard key={x.feature} w={x} onPick={() => pick(x.feature)} />)}
      </div>
    </div>
  );
};

const SafeWindows = ({ id }) => {
  const q = useApi('/api/safe-windows');
  return <Gate q={q} what="Safe windows">{(sw) => <Body sw={sw} id={id} />}</Gate>;
};

export default SafeWindows;

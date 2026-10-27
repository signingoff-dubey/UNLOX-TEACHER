import { useState } from 'react';
import { CheckCircle2, Database, Download } from 'lucide-react';
import { apiUrl } from '../lib/api';
import { CardTitle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { useApi } from '../lib/useApi';
import { num, pct } from '../lib/format';

// Missing values and outliers: what cleaning did, fitted on the training window only, and the check that the
// training data kept its shape. Problem statement: "handle missing and imbalanced data".
const Stat = ({ k, v, sub }) => (
  <div className="rounded-xl bg-ink/5 px-3 py-2.5">
    <p className="text-xs text-ink/55">{k}</p>
    <p className="tabular text-lg font-semibold">{v}</p>
    {sub && <p className="text-[11px] text-ink/55">{sub}</p>}
  </div>
);

const Drift = () => {
  const q = useApi('/api/drift');
  return (
    <Gate q={q} what="The drift report">
      {({ report: r, experiment: e }) => (
        <>
          <section className="card">
            <CardTitle sub={`Recorded ${r.data_period.first_run.slice(0, 10)} to ${r.data_period.last_run.slice(0, 10)}; test window from ${r.data_period.test[0].slice(0, 10)}. Real dates are never extended.`}>Drift between training and later runs</CardTitle>
            <div className="grid grid-cols-3 gap-2">
              <Stat k="Train vs test separable" v={num(r.adversarial.auc, 3)} sub={`AUC, ${r.adversarial.badge}`} />
              <Stat k="Sensors shifted" v={`${num(r.sensors_shifted_psi_gt_0_25, 0)} / ${num(r.sensors_checked, 0)}`} sub="PSI above 0.25" />
              <Stat k="Most shifted" v={r.most_shifted[0]?.feature ?? '-'} sub={`KS ${num(r.most_shifted[0]?.ks ?? 0, 2)}`} />
            </div>
            <p className="mt-3 text-xs text-ink/60">How we manage it: split by time only, a re-check of every safe window on the later test window, rolling-origin evaluation and the Timeline view. Windows that do not hold later are marked not recommended.</p>
          </section>
          <section className="card">
            <CardTitle sub={e.chosen_on}>Can training adapt to drift?</CardTitle>
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-ink/55"><tr><th className="py-1">Variant</th><th className="text-right">Validation PR-AUC</th><th className="text-right">Test PR-AUC</th></tr></thead>
              <tbody>
                {Object.entries(e.variants).map(([k, v]) => (
                  <tr key={k} className={`border-t border-ink/8 ${k === e.best_on_validation ? 'font-semibold' : ''}`}>
                    <td className="py-1.5 capitalize">{k === 'interpolation' ? 'Interpolated extra runs' : k === 'recency' ? 'Recent runs weighted more' : 'Current model'}</td>
                    <td className="tabular text-right">{num(v.val_pr_auc, 3)} ± {num(v.val_sd, 3)}</td>
                    <td className="tabular text-right">{num(v.test_pr_auc, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 rounded-xl bg-ink/5 px-3 py-2 text-sm font-medium">{e.decision}</p>
            <p className="mt-2 text-xs text-ink/55">{e.note} Each variant here trains on the training window only, so its scores are lower than the final model's, which also learns from validation.</p>
          </section>
        </>
      )}
    </Gate>
  );
};


// Sensor health: recent readings vs training. Flags sensors to check; nothing is dropped automatically.
const TONE = { bad: 'bg-red-500/15 text-red-300', watch: 'bg-amber-500/15 text-amber-300', ok: 'bg-emerald-500/15 text-emerald-300', 'no signal': 'bg-ink/10 text-ink/60' };

const Spark = ({ trace }) => {
  const pts = trace.map((t, i) => [i, t.median_z]).filter(([, v]) => v != null);
  if (pts.length < 2) return <span className="text-xs text-ink/40">-</span>;
  const ys = pts.map(([, v]) => Math.max(-4, Math.min(4, v)));
  const w = 72, h = 22, n = trace.length - 1;
  const d = pts.map(([i], k) => `${k ? 'L' : 'M'}${((i / n) * w).toFixed(1)},${(h / 2 - (ys[k] / 4) * (h / 2 - 2)).toFixed(1)}`).join(' ');
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true" className="overflow-visible">
      <line x1="0" x2={w} y1={h / 2} y2={h / 2} className="stroke-ink/15" strokeDasharray="2 3" />
      <path d={d} fill="none" className="stroke-accent" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
};

const SensorHealth = () => {
  const q = useApi('/api/sensors/health');
  const [show, setShow] = useState('bad');
  return (
    <Gate q={q} what="Sensor health">
      {(h) => {
        const rows = h.sensors.filter((s) => show === 'all' ? s.status !== 'no signal' : s.status === show).slice(0, 60);
        return (
          <section className="card xl:col-span-2">
            <CardTitle sub={`${h.compared}. ${h.rule}`}>Sensor health</CardTitle>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat k="Bad" v={num(h.counts.bad, 0)} sub="stuck, silent or mostly out of range" />
              <Stat k="Watch" v={num(h.counts.watch, 0)} sub="drifted, spikes or more gaps" />
              <Stat k="OK" v={num(h.counts.ok, 0)} sub="behaves as in training" />
              <Stat k="No signal" v={num(h.counts['no signal'], 0)} sub="constant in training" />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {['bad', 'watch', 'all'].map((k) => (
                <button key={k} type="button" onClick={() => setShow(k)} aria-pressed={show === k}
                  className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${show === k ? 'bg-ink text-panel' : 'bg-ink/10 text-ink/70 hover:bg-ink/15'}`}>{k}</button>
              ))}
              <span className="ml-auto flex gap-2">
                <a className="btn-ghost text-xs" href={apiUrl('/api/export/sensors.csv')} download><Download size={14} /> Sensor dictionary (CSV)</a>
                <a className="btn-ghost text-xs" href={apiUrl('/api/export/runs.csv')} download><Download size={14} /> Labelled runs (CSV)</a>
              </span>
            </div>
            <div className="mt-3 max-h-[28rem] overflow-y-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-panel/95 text-xs text-ink/55"><tr><th className="py-1">Sensor</th><th>Status</th><th>Why</th><th className="text-right">Missing now</th><th className="text-right">Median over time</th></tr></thead>
                <tbody>
                  {rows.map((s) => (
                    <tr key={s.sensor} className="border-t border-ink/8 align-top">
                      <td className="py-1.5 font-mono">{s.sensor}</td>
                      <td><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${TONE[s.status]}`}>{s.status}</span></td>
                      <td className="pr-3 text-xs text-ink/70">{s.reasons.join('; ') || '-'}</td>
                      <td className="tabular text-right">{pct(s.missing_recent, 0)}</td>
                      <td className="text-right"><Spark trace={s.trace} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rows.length && <p className="py-4 text-sm text-ink/55">None.</p>}
            </div>
            <p className="mt-2 text-xs text-ink/55">Sensor names, units and products are not published in SECOM, so they are not invented here. The CSVs add what RootLens knows about every column and every run.</p>
          </section>
        );
      }}
    </Gate>
  );
};

const DataQuality = () => {
  const q = useApi('/api/data-quality');
  return (
    <Gate q={q} what="The data quality report">
      {(d) => (
        <div className="grid gap-[var(--gap)] xl:grid-cols-2">
          <section className="card xl:col-span-2">
            <CardTitle sub={`${d.method.imputed_with}; outliers ${d.method.outliers}; ${d.method.fitted_on}.`}>
              <span className="flex items-center gap-2"><Database size={17} /> How missing values and outliers are handled</span>
            </CardTitle>
            <ol className="flex flex-col gap-1.5 text-sm">
              {d.steps.map((s, i) => (
                <li key={s} className="flex gap-2"><span className="tabular font-semibold text-accent-deep">{i + 1}.</span> {s}</li>
              ))}
            </ol>
          </section>

          <section className="card">
            <CardTitle sub="Gaps filled and outliers clipped in each split, using the training window's statistics only.">Per split</CardTitle>
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-ink/55">
                <tr><th className="py-1">Split</th><th className="text-right">Runs</th><th className="text-right">Fail rate</th><th className="text-right">Gaps filled</th><th className="text-right">Gaps left</th><th className="text-right">Outliers clipped</th></tr>
              </thead>
              <tbody>
                {Object.entries(d.splits).map(([k, s]) => (
                  <tr key={k} className="border-t border-ink/8">
                    <td className="py-1.5 font-medium capitalize">{k}</td>
                    <td className="tabular text-right">{num(s.rows, 0)}</td>
                    <td className="tabular text-right">{pct(s.fail_rate)}</td>
                    <td className="tabular text-right">{num(s.missing_before, 0)}</td>
                    <td className="tabular text-right">{num(s.missing_after, 0)}</td>
                    <td className="tabular text-right">{num(s.outliers_clipped, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-ink/60">Imbalance: {d.imbalance.handled_by}.</p>
          </section>

          <section className="card">
            <CardTitle sub={d.shape_check.note}>Did cleaning change the training data?</CardTitle>
            <div className="grid grid-cols-3 gap-2">
              <Stat k="Typical mean shift" v={`${num(d.shape_check.median_mean_shift_sd, 3)} sd`} sub="median over sensors" />
              <Stat k="Worst 5% shift" v={`${num(d.shape_check.p95_mean_shift_sd, 3)} sd`} sub="95th percentile" />
              <Stat k="Spread kept" v={pct(d.shape_check.median_std_ratio, 0)} sub="median std after / before" />
            </div>
            <p className="mt-3 flex items-start gap-2 rounded-xl bg-good/12 px-3 py-2 text-sm">
              <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-good" />
              {d.shape_check.features} sensors kept. A typical sensor&apos;s mean moves by about a hundredth of a standard deviation, so filling and clipping do not reshape the training data; clipping trims only the extreme tails.
            </p>
          </section>

          <Drift />
          <SensorHealth />

          <section className="card xl:col-span-2">
            <CardTitle sub="Sensors kept despite gaps: the fill value and the clip range are learned on the training window.">Most-missing sensors</CardTitle>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-left text-sm">
                <thead className="text-xs text-ink/55">
                  <tr><th className="py-1">Sensor</th><th className="text-right">Missing (train)</th><th className="text-right">Filled with</th><th className="text-right">Clip range</th><th className="text-right">Was-missing flag</th></tr>
                </thead>
                <tbody>
                  {d.most_missing.map((f) => (
                    <tr key={f.feature} className="border-t border-ink/8">
                      <td className="py-1.5 font-mono">{f.feature}</td>
                      <td className="tabular text-right">{pct(f.missing_train)}</td>
                      <td className="tabular text-right">{num(f.fill_value, 4)}</td>
                      <td className="tabular text-right">{num(f.clip_low, 3)} to {num(f.clip_high, 3)}</td>
                      <td className="text-right">{f.flagged ? 'yes' : 'no'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </Gate>
  );
};

export default DataQuality;

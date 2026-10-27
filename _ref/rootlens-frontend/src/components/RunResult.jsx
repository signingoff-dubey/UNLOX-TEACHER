import { CircleAlert, CircleCheck } from 'lucide-react';
import { num, pct } from '../lib/format';

export const BAND = {
  high: { label: 'High risk', cls: 'bg-bad text-white' },
  elevated: { label: 'Elevated risk', cls: 'bg-warn text-ink' },
  low: { label: 'Low risk', cls: 'bg-good text-white' },
};

export const BandChip = ({ band, className = '' }) => {
  const b = BAND[band];
  return b ? <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${b.cls} ${className}`}>{b.label}</span> : null;
};

// Half-circle gauge for fail probability, 0..50% scale (SECOM fails are rare).
export const RiskGauge = ({ p }) => {
  const len = Math.PI * 40;
  const ratio = Math.min(p / 0.5, 1);
  return (
    <svg viewBox="0 0 100 58" className="w-40" role="img" aria-label={`Model-estimated fail probability ${pct(p, 0)}`}>
      <path d="M10 52 A40 40 0 0 1 90 52" fill="none" stroke="rgb(31 26 20 / 0.1)" strokeWidth="9" strokeLinecap="round" />
      <path d="M10 52 A40 40 0 0 1 90 52" fill="none" stroke="var(--color-accent)" strokeWidth="9" strokeLinecap="round" strokeDasharray={`${len * ratio} ${len}`} />
      <text x="50" y="48" textAnchor="middle" fontSize="18" fontWeight="700" fill="#1f1a14">{pct(p, 0)}</text>
    </svg>
  );
};

// The API now sends a boolean `recommended` on windows; contributors may carry it too. Older payloads only had a status string.
export const isRecommended = (x) => {
  if (typeof x?.recommended === 'boolean') return x.recommended;
  if (typeof x?.window_recommended === 'boolean') return x.window_recommended;
  return x?.window_status === 'recommended' || x?.status === 'recommended';
};

export const Counterfactual = ({ cf }) => {
  const est = cf.model_estimate;
  const diffs = cf.biggest_differences.slice(0, 4);
  return (
    <div className="mt-4 rounded-2xl bg-ink/5 p-3">
      <h3 className="text-sm font-semibold">Compared with the {cf.neighbours.length} nearest passing runs</h3>
      <p className="mt-0.5 text-xs text-ink/60">{cf.label}</p>
      {est && (
        <p className="mt-2 text-sm">
          <span className="mr-1.5 rounded bg-warn/15 px-1.5 py-0.5 text-xs font-semibold text-warn">Model-estimated</span>{" "}
          fail probability {pct(est.fail_prob_now, 0)} now, {pct(est.fail_prob_with_nearest_pass_profile, 0)} with the nearest passing profile. The model scoring its own suggestion is circular.
        </p>
      )}
      <ul className="mt-2 flex flex-col gap-1 text-xs text-ink/75">
        {diffs.map((d) => (
          <li key={d.feature} className="tabular flex flex-wrap justify-between gap-x-3">
            <span className="font-mono font-semibold">{d.feature}</span>
            <span>now {num(d.current, 3)}, neighbours {num(d.neighbour_median, 3)} ({num(d.neighbour_range[0], 3)} to {num(d.neighbour_range[1], 3)})</span>
          </li>
        ))}
      </ul>
    </div>
  );
};

// Gauge, top contributors and counterfactual for one scored run. Shared by the run history and the capture result.
export const ScoreBody = ({ r }) => {
  const contributors = r.top_contributors ?? [];
  const maxShap = Math.max(...contributors.map((t) => Math.abs(t.shap)), 0.01);
  return (
    <>
      <div className="flex flex-wrap items-center gap-5">
        <RiskGauge p={r.fail_probability} />
        <p className="max-w-xs text-sm text-ink/70">Model-estimated chance this run fails, from its process values.</p>
      </div>
      <h3 className="mt-4 text-sm font-semibold">Top contributors</h3>
      <ul className="mt-2 flex flex-col gap-2">
        {contributors.map((t) => {
          const rec = isRecommended(t);
          return (
            <li key={t.feature} className="grid grid-cols-[4rem_1fr_auto] items-center gap-3 rounded-xl bg-ink/5 px-3 py-2 text-sm">
              <span className="font-mono font-semibold">{t.feature}</span>
              <span>
                <span className="tabular block text-xs text-ink/65">
                  {t.value === null || t.value === undefined ? 'value not recorded' : `value ${num(t.value, 3)}`}
                  {t.safe_window && `, safe window ${num(t.safe_window[0], 3)} to ${num(t.safe_window[1], 3)}${rec ? '' : ' (not recommended)'}`}
                </span>
                <span className="mt-1 block h-1.5 rounded-full bg-ink/8">
                  <span className={`block h-full rounded-full ${t.shap > 0 ? 'bg-bad' : 'bg-good'}`} style={{ width: `${(Math.abs(t.shap) / maxShap) * 100}%` }} />
                </span>
              </span>
              {typeof t.in_safe_window === 'boolean' && rec ? (
                <span className={`inline-flex items-center gap-1 text-xs font-semibold ${t.in_safe_window ? 'text-good' : 'text-bad'}`}>
                  {t.in_safe_window ? <CircleCheck size={14} /> : <CircleAlert size={14} />}
                  {t.in_safe_window ? 'Inside' : 'Outside'}
                </span>
              ) : (
                <span className="text-xs text-ink/45">{t.safe_window ? 'No advice' : ''}</span>
              )}
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs text-ink/60">Bar length is SHAP size. Red pushes toward failure, green away from it.</p>
      {r.counterfactual && <Counterfactual cf={r.counterfactual} />}
      {r.disclaimer && <p className="mt-3 text-xs font-medium text-ink/70">{r.disclaimer}</p>}
    </>
  );
};

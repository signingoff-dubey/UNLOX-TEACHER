import { ArrowRight } from 'lucide-react';
import { Banner, CardTitle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { SERIES_COLORS } from '../components/charts';
import { num, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

const AXIS = 'rgb(28 28 31 / 0.55)';
const shortDate = (ts) => ts.slice(5, 10);

// Windows run left to right, features top to bottom. Cell darkness is the feature's share of attribution in that window.
const HeatGrid = ({ tl }) => {
  const feats = tl.features;
  const rows = tl.matrix;
  const max = Math.max(...rows.flatMap((r) => feats.map((f) => r[f] ?? 0)), 1e-9);
  const L = 54, T = 8, ch = 28, B = 42;
  const W = 760, cw = (W - L - 6) / rows.length;
  const H = T + feats.length * ch + B;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Heatmap of each feature's share of attribution, by time window" className="w-full">
      {feats.map((f, r) => (
        <g key={f}>
          <text x={L - 8} y={T + r * ch + ch / 2 + 4} textAnchor="end" fontSize="13" fontFamily="ui-monospace, monospace" fontWeight="600" fill="rgb(28 28 31 / 0.8)">{f}</text>
          {rows.map((row, c) => {
            const v = row[f];
            const x = L + c * cw + 1.5, y = T + r * ch + 1.5;
            if (v === null || v === undefined) {
              return <rect key={c} x={x} y={y} width={cw - 3} height={ch - 3} rx="5" fill="none" stroke={AXIS} strokeDasharray="3 3" opacity="0.5"><title>{`${f}, window ${c + 1}: not in this window`}</title></rect>;
            }
            const t = v / max;
            return (
              <g key={c}>
                <rect x={x} y={y} width={cw - 3} height={ch - 3} rx="5" fill="var(--color-accent)" opacity={0.07 + 0.93 * t}>
                  <title>{`${f}, ${shortDate(row.start)} to ${shortDate(row.end)}: ${pct(v)} of attribution`}</title>
                </rect>
                {cw > 40 && <text x={x + (cw - 3) / 2} y={y + (ch - 3) / 2 + 4} textAnchor="middle" fontSize="11" fill="rgb(28 28 31 / 0.85)" pointerEvents="none">{(v * 100).toFixed(1)}</text>}
              </g>
            );
          })}
        </g>
      ))}
      {rows.map((row, c) => {
        const w = tl.windows[c];
        return (
          <g key={c}>
            <text x={L + c * cw + cw / 2} y={T + feats.length * ch + 16} textAnchor="middle" fontSize="12" fill={AXIS}>{shortDate(row.start)}</text>
            {w && <text x={L + c * cw + cw / 2} y={T + feats.length * ch + 32} textAnchor="middle" fontSize="11" fill={w.fail_rate > 0.12 ? 'var(--color-bad)' : AXIS}>{pct(w.fail_rate, 0)}</text>}
          </g>
        );
      })}
      <text x={L - 8} y={T + feats.length * ch + 32} textAnchor="end" fontSize="11" fill={AXIS}>fail rate</text>
    </svg>
  );
};

// One small chart per parameter: its own scale, gaps where a week had no readings.
const Spark = ({ name, values, periods, color }) => {
  const W = 300, H = 88, L = 6, R = 6, T = 8, B = 8;
  const real = values.filter((v) => v !== null && v !== undefined);
  const lo = Math.min(...real), hi = Math.max(...real);
  if (!real.length) return null;
  const span = hi - lo || 1;
  const x = (i) => L + (i * (W - L - R)) / Math.max(values.length - 1, 1);
  const y = (v) => T + (1 - (v - lo) / span) * (H - T - B);
  let d = '';
  let pen = false;
  values.forEach((v, i) => {
    if (v === null || v === undefined) {
      pen = false;
      return;
    }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
    pen = true;
  });
  return (
    <div className="rounded-2xl bg-ink/5 p-3">
      <p className="flex items-baseline justify-between text-sm"><span className="font-mono font-semibold">{name}</span><span className="tabular text-xs text-ink/55">{num(lo, 3)} to {num(hi, 3)}</span></p>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Weekly average of ${name}, from ${num(lo, 3)} to ${num(hi, 3)}`} className="mt-1 w-full">
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke="rgb(28 28 31 / 0.12)" />
        <path d={d} fill="none" stroke={color} strokeWidth="2.25" strokeLinejoin="round" strokeLinecap="round" />
        {values.map((v, i) => (v === null || v === undefined ? null : <circle key={i} cx={x(i)} cy={y(v)} r="2.6" fill="#fff" stroke={color} strokeWidth="1.5"><title>{`${periods[i]}: ${num(v, 4)}`}</title></circle>))}
      </svg>
      <p className="mt-0.5 flex justify-between text-[11px] text-ink/50"><span>{periods[0]?.slice(5, 10)}</span><span>{periods[periods.length - 1]?.slice(5, 10)}</span></p>
    </div>
  );
};

const Chips = ({ items, tone }) =>
  items?.length ? (
    <span className="inline-flex flex-wrap gap-1">
      {items.map((f) => <span key={f} className={`rounded-md px-1.5 py-0.5 font-mono text-xs font-semibold ${tone === 'in' ? 'bg-good/12 text-good' : 'bg-ink/8 text-ink/65'}`}>{f}</span>)}
    </span>
  ) : (
    <span className="text-xs text-ink/45">none</span>
  );

const Body = ({ tl }) => {
  const pd = tl.parameter_drift;
  const bad = tl.windows.filter((w) => w.status && w.status !== 'ok');
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone="warn">{tl.label} Each window holds {tl.window_size} runs and moves on by {tl.step}, so windows overlap.</Banner>

      <section className="card">
        <CardTitle sub="Darker means a larger share of that window's attribution. Dashed cells were not scored in that window. Bottom row: share of runs that failed.">Attribution share by time window</CardTitle>
        <HeatGrid tl={tl} />
        {bad.length > 0 && <p className="mt-2 text-xs text-warn">{bad.length} window{bad.length > 1 ? 's' : ''} flagged: {bad.map((w) => `${shortDate(w.start)} (${w.status})`).join(', ')}.</p>}
      </section>

      <div className="grid gap-[var(--gap)] xl:grid-cols-2">
        <section className="card">
          <CardTitle sub="One line per window: the leading feature and the failure rate.">Story</CardTitle>
          <ol className="flex flex-col gap-2 text-sm">
            {tl.story.map((line, i) => (
              <li key={i} className="flex gap-3 rounded-xl bg-ink/5 px-3 py-2">
                <span className="tabular w-5 shrink-0 text-xs font-semibold text-ink/45">{i + 1}</span>
                <span>{line}</span>
              </li>
            ))}
          </ol>
        </section>

        <section className="card">
          <CardTitle sub="How the top 5 changed between consecutive windows. Rank agreement is how similar the two rankings are.">Drift between windows</CardTitle>
          <ul className="flex flex-col gap-2 text-sm">
            {tl.drift.map((d, i) => (
              <li key={i} className="rounded-xl bg-ink/5 px-3 py-2.5">
                <p className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="tabular flex items-center gap-1.5 font-semibold">{shortDate(d.from)} <ArrowRight size={12} /> {shortDate(d.to)}</span>
                  <span className="tabular text-ink/60">rank agreement {d.rank_agreement.toFixed(2)}, {d.top5_overlap} of 5 kept</span>
                </p>
                <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                  <span className="flex flex-wrap items-center gap-1.5"><span className="text-ink/55">entered</span><Chips items={d.entered_top5} tone="in" /></span>
                  <span className="flex flex-wrap items-center gap-1.5"><span className="text-ink/55">left</span><Chips items={d.left_top5} /></span>
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {pd?.series && (
        <section className="card">
          <CardTitle sub="Weekly average of the leading parameters, each on its own scale. Movement alongside a rising failure rate is a lead to check, not proof.">Parameter drift</CardTitle>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Object.entries(pd.series).map(([name, values], i) => <Spark key={name} name={name} values={values} periods={pd.period} color={SERIES_COLORS[i % SERIES_COLORS.length]} />)}
          </div>
        </section>
      )}
    </div>
  );
};

const Timeline = () => {
  const q = useApi('/api/timeline');
  return <Gate q={q} what="The timeline">{(tl) => <Body tl={tl} />}</Gate>;
};

export default Timeline;

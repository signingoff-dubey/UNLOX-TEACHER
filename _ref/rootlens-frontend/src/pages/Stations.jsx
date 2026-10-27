import { useMemo, useState } from 'react';
import { Banner, CardTitle, ChipToggle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { StableChip } from './Overview';
import { num, pct } from '../lib/format';
import { useApi } from '../lib/useApi';

const COOL = '#7a8aa0';
const AXIS = 'rgb(28 28 31 / 0.55)';

const stationNo = (id) => Number(/S(\d+)$/.exec(id)?.[1] ?? 0);

// Colour for a fail rate, relative to the line average: grey-blue at half the average or lower, red at three times or more.
const heat = (rate, base) => {
  const t = Math.min(Math.max((rate / base - 0.5) / 2.5, 0), 1);
  return `color-mix(in srgb, var(--color-bad) ${Math.round(t * 100)}%, ${COOL})`;
};

// Lay the route out as a Sankey: columns by the longest path from a start station, stations in station-number order inside a column,
// node height and link width in proportion to parts. Everything is computed here from the API's nodes and links.
const layoutSankey = (route, H) => {
  const ids = [...route.nodes].sort((a, b) => stationNo(a) - stationNo(b));
  const order = new Map(ids.map((id, i) => [id, i]));
  const links = route.links.filter((l) => order.has(l.source) && order.has(l.target) && order.get(l.source) < order.get(l.target));
  const skipped = route.links.length - links.length;

  const depth = new Map(ids.map((id) => [id, 0]));
  for (const id of ids) for (const l of links) if (l.target === id) depth.set(id, Math.max(depth.get(id), depth.get(l.source) + 1));

  const nodes = new Map(ids.map((id) => [id, { id, col: depth.get(id), inSum: 0, outSum: 0 }]));
  for (const l of links) {
    nodes.get(l.source).outSum += l.parts_est;
    nodes.get(l.target).inSum += l.parts_est;
  }
  nodes.forEach((n) => { n.value = Math.max(n.inSum, n.outSum, 1); });

  const GAP = 16;
  const cols = [];
  nodes.forEach((n) => { (cols[n.col] ??= []).push(n); });
  const scale = Math.min(...cols.filter(Boolean).map((c) => (H - GAP * (c.length - 1)) / c.reduce((a, n) => a + n.value, 0)));
  for (const c of cols) {
    if (!c) continue;
    c.forEach((n) => { n.h = Math.max(n.value * scale, 4); });
    const total = c.reduce((a, n) => a + n.h, 0) + GAP * (c.length - 1);
    let y = Math.max((H - total) / 2, 0);
    for (const n of c) {
      n.y = y;
      y += n.h + GAP;
    }
  }

  const outOff = new Map(), inOff = new Map();
  const laid = links.map((l) => ({ ...l, w: Math.max(l.parts_est * scale, 1) }));
  const bySource = [...laid].sort((a, b) => nodes.get(a.target).y - nodes.get(b.target).y);
  for (const l of bySource) {
    const s = nodes.get(l.source);
    l.sy = s.y + (outOff.get(s.id) ?? 0);
    outOff.set(s.id, (outOff.get(s.id) ?? 0) + l.w);
  }
  const byTarget = [...laid].sort((a, b) => nodes.get(a.source).y - nodes.get(b.source).y);
  for (const l of byTarget) {
    const t = nodes.get(l.target);
    l.ty = t.y + (inOff.get(t.id) ?? 0);
    inOff.set(t.id, (inOff.get(t.id) ?? 0) + l.w);
  }
  return { nodes: [...nodes.values()], links: laid, columns: cols.length, skipped };
};

const Sankey = ({ route, rates, base, stable }) => {
  const H = 470, NW = 10, COL = 58, PAD = 14;
  const [hover, setHover] = useState(null);
  const g = useMemo(() => layoutSankey(route, H), [route]);
  const W = PAD * 2 + (g.columns - 1) * COL + NW + 20;
  const rateOf = useMemo(() => new Map(rates.map((r) => [r.station, r])), [rates]);
  const nodeX = (n) => PAD + n.col * COL;
  const byId = useMemo(() => new Map(g.nodes.map((n) => [n.id, n])), [g]);
  const active = hover ? g.links[hover.i] : null;
  return (
    <div>
      <div className="overflow-x-auto pb-2">
        <svg viewBox={`0 0 ${W} ${H + 8}`} width={W} height={H + 8} role="img" aria-label="Part flow between Bosch stations. Link width is parts, colour is fail rate." className="max-w-none" style={{ minWidth: W }}>
          <g fill="none">
            {g.links.map((l, i) => {
              const s = byId.get(l.source), t = byId.get(l.target);
              const x0 = nodeX(s) + NW, x1 = nodeX(t), xm = (x0 + x1) / 2;
              const y0 = l.sy + l.w / 2, y1 = l.ty + l.w / 2;
              return (
                <path
                  key={i}
                  d={`M${x0},${y0} C${xm},${y0} ${xm},${y1} ${x1},${y1}`}
                  strokeWidth={l.w}
                  stroke={heat(l.fail_rate, base)}
                  opacity={hover ? (hover.i === i ? 0.95 : 0.2) : 0.6}
                  onMouseEnter={() => setHover({ i })}
                  onMouseLeave={() => setHover(null)}
                >
                  <title>{`${l.source} to ${l.target}: about ${num(l.parts_est, 0)} parts, fail rate ${pct(l.fail_rate, 2)}`}</title>
                </path>
              );
            })}
          </g>
          {g.nodes.map((n) => {
            const r = rateOf.get(n.id);
            const x = nodeX(n);
            return (
              <g key={n.id}>
                <rect x={x} y={n.y} width={NW} height={n.h} rx="2" fill={r ? heat(r.fail_rate, base) : COOL} stroke={stable.has(n.id) ? 'var(--color-accent)' : 'rgb(28 28 31 / 0.5)'} strokeWidth={stable.has(n.id) ? 2.5 : 0.5}>
                  <title>{`${n.id}${r ? `: fail rate ${pct(r.fail_rate, 2)}` : ''}${stable.has(n.id) ? ', stable suspected station' : ''}`}</title>
                </rect>
                <text x={x - 2} y={n.y - 3} fontSize="10" fontFamily="ui-monospace, monospace" fill="rgb(28 28 31 / 0.85)" stroke="rgb(251 248 241 / 0.9)" strokeWidth="3" paintOrder="stroke">{n.id}</text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-xs text-ink/65">
        <p className="min-h-4 tabular" aria-live="polite">
          {active ? `${active.source} to ${active.target}: about ${num(active.parts_est, 0)} parts, fail rate ${pct(active.fail_rate, 2)}` : 'Hover a link for its parts and fail rate. Scroll sideways for the later stations.'}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-2">
            <span>0.5x line average</span>
            <span className="h-2.5 w-28 rounded-full" style={{ background: `linear-gradient(90deg, ${COOL}, var(--color-bad))` }} />
            <span>3x or more</span>
          </span>
          <span className="flex items-center gap-1.5"><span className="size-3 rounded-sm border-2 border-accent" /> stable suspected station</span>
        </div>
      </div>
      {g.skipped > 0 && <p className="mt-1 text-xs text-ink/50">{g.skipped} link{g.skipped > 1 ? 's' : ''} not drawn because they run against the station order.</p>}
    </div>
  );
};

// Station fail rates with their confidence interval on one shared scale; the dashed line is the line-wide average.
const RateRows = ({ rows, base }) => {
  const max = Math.max(...rows.map((r) => r.fail_rate_ci[1]), base) * 1.08;
  const at = (v) => `${Math.min(v / max, 1) * 100}%`;
  return (
    <ul className="flex max-h-[30rem] flex-col gap-1 overflow-y-auto pr-1">
      {rows.map((r) => (
        <li key={r.station} className="grid grid-cols-[4.5rem_1fr_9.5rem] items-center gap-3 text-xs">
          <span className="font-mono font-semibold">{r.station}</span>
          <span className="relative block h-3 rounded-full bg-ink/8" aria-hidden="true">
            <span className="absolute inset-y-0 w-px border-l border-dashed border-ink/40" style={{ left: at(base) }} />
            <span className="absolute inset-y-0.5 rounded-full bg-accent/35" style={{ left: at(r.fail_rate_ci[0]), width: `calc(${at(r.fail_rate_ci[1])} - ${at(r.fail_rate_ci[0])})` }} />
            <span className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white bg-accent" style={{ left: at(r.fail_rate) }} />
          </span>
          <span className="tabular text-right text-ink/70">{pct(r.fail_rate, 2)} <span className="text-ink/45">({pct(r.fail_rate_ci[0], 2)} to {pct(r.fail_rate_ci[1], 2)})</span></span>
        </li>
      ))}
    </ul>
  );
};

const Ranking = ({ ranking }) => {
  const [all, setAll] = useState(false);
  const list = all ? ranking.stations : ranking.stations.slice(0, 12);
  const h = ranking.holdout;
  return (
    <section className="card">
      <CardTitle sub={ranking.method}>Station ranking: statistically suspected, stability-checked</CardTitle>
      <ol className="flex flex-col gap-2">
        {list.map((s, i) => (
          <li key={s.station} className="rounded-2xl bg-ink/5 px-3 py-2.5">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="tabular w-6 text-xs font-semibold text-ink/45">{i + 1}</span>
              <span className="font-mono text-sm font-semibold">{s.station}</span>
              <StableChip stable={s.stable} />
              <span className="tabular ml-auto text-xs text-ink/60">mean rank {s.mean_rank.toFixed(1)} ± {s.rank_std.toFixed(1)}, top 10 in {pct(s.top_k_freq, 0)} of refits</span>
            </div>
            {s.top_parameters?.length > 0 && (
              <p className="mt-1.5 flex flex-wrap gap-1.5 pl-9">
                {s.top_parameters.slice(0, 4).map((p) => (
                  <span key={p.feature} className="tabular rounded-md bg-white/70 px-1.5 py-0.5 font-mono text-[11px] text-ink/75" title="mean |SHAP|">{p.feature} <span className="text-ink/45">{p.mean_abs_shap.toFixed(3)}</span></span>
                ))}
              </p>
            )}
          </li>
        ))}
      </ol>
      {ranking.stations.length > 12 && (
        <button type="button" onClick={() => setAll((v) => !v)} className="btn-ghost mt-3 h-8 px-3 text-xs">{all ? 'Show the top 12' : `Show all ${ranking.stations.length}`}</button>
      )}
      <p className="mt-3 rounded-xl bg-ink/5 p-2.5 text-xs text-ink/70">
        Check on held-out data: PR-AUC {h.pr_auc_sample.toFixed(3)} against a failure rate of {pct(h.prevalence_sample, 1)} in the sample. {h.note} {ranking.label}
      </p>
    </section>
  );
};

const Body = ({ d }) => {
  const [sort, setSort] = useState('station');
  const base = d.sample_info.true_fail_rate;
  const stable = useMemo(() => new Set(d.station_ranking.stations.filter((s) => s.stable).map((s) => s.station)), [d]);
  const rows = useMemo(() => [...d.station_rates].sort(sort === 'rate' ? (a, b) => b.fail_rate - a.fail_rate : (a, b) => stationNo(a.station) - stationNo(b.station)), [d, sort]);
  const si = d.sample_info;
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone="warn">
        These rates are re-weighted from a subsample: all {num(si.positives_total, 0)} failures plus {pct(si.negative_fraction, 0)} of passing parts, each pass counted {num(si.negative_weight, 1)} times. Read them as estimates, and compare stations with each other rather than trusting one absolute figure. The line-wide failure rate is about {pct(base, 2)}.
      </Banner>

      <section className="card">
        <CardTitle sub={d.route.label}>Part flow through {d.n_stations} stations</CardTitle>
        <Sankey route={d.route} rates={d.station_rates} base={base} stable={stable} />
      </section>

      <div className="grid gap-[var(--gap)] xl:grid-cols-[1fr_1.1fr]">
        <section className="card">
          <CardTitle
            sub="Point is the estimated rate, band is its confidence interval, dashed line is the line average."
            action={<ChipToggle multiple={false} value={sort} onChange={setSort} options={[{ id: 'station', label: 'By station' }, { id: 'rate', label: 'By fail rate' }]} />}
          >
            Fail rate by station
          </CardTitle>
          <RateRows rows={rows} base={base} />
        </section>
        <Ranking ranking={d.station_ranking} />
      </div>
    </div>
  );
};

const Stations = () => {
  const q = useApi('/api/stations');
  return <Gate q={q} what="The Bosch station analysis">{(d) => <Body d={d} />}</Gate>;
};

export default Stations;

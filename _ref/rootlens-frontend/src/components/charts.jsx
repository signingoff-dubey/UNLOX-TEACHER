import { useId, useMemo, useState } from 'react';

// Small SVG charts with no chart library. Colours come from CSS variables, so they follow the owner's accent.
// Every chart has a text summary for screen readers and a "View as a table" fold with the same numbers.

export const SERIES_COLORS = ['var(--color-accent)', '#3d7be0', '#14a89a', '#e0457b', '#8b5cf6'];
const GRID = 'rgb(28 28 31 / 0.10)';
const AXIS = 'rgb(28 28 31 / 0.55)';

const nice = (max) => {
  if (max <= 0) return 1;
  const pow = 10 ** Math.floor(Math.log10(max));
  const n = max / pow;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * pow;
};
export const compact = (n) => (n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : `${Math.round(n)}`);

export const ChartCard = ({ title, sub, sample = false, live = false, badge, children, table, className = '' }) => (
  <section className={`card ${className}`}>
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div className="min-w-0">
        <h3 className="font-semibold">{title}</h3>
        {sub && <p className="mt-0.5 text-xs text-ink/55">{sub}</p>}
      </div>
      {(sample || live || badge) && (
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${live || badge ? 'bg-good/12 text-good' : 'bg-ink/8 text-ink/60'}`}>{badge || (live ? 'Live' : 'Sample data')}</span>
      )}
    </div>
    <div className="mt-3">{children}</div>
    {table && (
      <details className="mt-3 text-xs text-ink/60">
        <summary className="cursor-pointer select-none font-medium hover:text-ink">View as a table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[320px] text-left">
            <thead><tr>{table.head.map((h) => <th key={h} className="pb-1 pr-3 font-medium">{h}</th>)}</tr></thead>
            <tbody>{table.rows.map((r, i) => <tr key={i} className="border-t border-ink/8">{r.map((c, j) => <td key={j} className="py-1 pr-3">{c}</td>)}</tr>)}</tbody>
          </table>
        </div>
      </details>
    )}
  </section>
);

const Legend = ({ items }) => (
  <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink/70">
    {items.map((it, i) => (
      <li key={it} className="flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} />{it}</li>
    ))}
  </ul>
);

// ---------------------------------------------------------------- line / area
export const LineChart = ({ labels, series, height = 200, label, format = (v) => Math.round(v).toLocaleString('en-IN'), markers = [] }) => {
  const id = useId();
  const [hover, setHover] = useState(null);
  const W = 640, H = height, L = 38, R = 10, T = 10, B = 24;
  const max = nice(Math.max(...series.flatMap((s) => s.values), 1));
  const x = (i) => L + (i * (W - L - R)) / Math.max(labels.length - 1, 1);
  const y = (v) => T + (1 - v / max) * (H - T - B);
  const path = (vals) => vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.min(labels.length - 1, Math.max(0, Math.round(((px - L) / (W - L - R)) * (labels.length - 1)))));
  };
  return (
    <div>
      <Legend items={series.map((s) => s.name)} />
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="w-full" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke={GRID} />
              <text x={L - 6} y={y(t) + 4} textAnchor="end" fontSize="13" fill={AXIS}>{format(t)}</text>
            </g>
          ))}
          {markers.map((m) => (
            <g key={m.label}>
              <line x1={x(m.at)} x2={x(m.at)} y1={T} y2={H - B} stroke={AXIS} strokeDasharray="4 4" />
              <text x={x(m.at) + 4} y={T + 12} fontSize="12" fill={AXIS}>{m.label}</text>
            </g>
          ))}
          {labels.map((l, i) => (i % Math.ceil(labels.length / 7) === 0 ? <text key={l} x={x(i)} y={H - 6} textAnchor={i === 0 ? 'start' : i === labels.length - 1 ? 'end' : 'middle'} fontSize="13" fill={AXIS}>{l}</text> : null))}
          {series.map((s, k) => (
            <g key={s.name}>
              <defs>
                <linearGradient id={`${id}-${k}`} x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor={SERIES_COLORS[k % SERIES_COLORS.length]} stopOpacity="0.22" />
                  <stop offset="100%" stopColor={SERIES_COLORS[k % SERIES_COLORS.length]} stopOpacity="0" />
                </linearGradient>
              </defs>
              {k === 0 && <path d={`${path(s.values)} L${x(labels.length - 1)},${y(0)} L${x(0)},${y(0)} Z`} fill={`url(#${id}-${k})`} />}
              <path d={path(s.values)} fill="none" stroke={SERIES_COLORS[k % SERIES_COLORS.length]} strokeWidth="2.25" strokeLinejoin="round" strokeLinecap="round" />
            </g>
          ))}
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} stroke={AXIS} strokeDasharray="3 3" />
              {series.map((s, k) => <circle key={s.name} cx={x(hover)} cy={y(s.values[hover])} r="4" fill="#fff" stroke={SERIES_COLORS[k % SERIES_COLORS.length]} strokeWidth="2" />)}
            </g>
          )}
        </svg>
        {hover !== null && (
          <div className="pointer-events-none absolute top-0 z-10 rounded-lg bg-ink px-2.5 py-1.5 text-xs text-white shadow-lg" style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > labels.length / 2 ? '-105%' : '5%'})` }}>
            <p className="font-semibold">{labels[hover]}</p>
            {series.map((s) => <p key={s.name}>{s.name}: {format(s.values[hover])}</p>)}
          </div>
        )}
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- bars (vertical or horizontal)
export const BarChart = ({ items, horizontal = false, height = 220, label, format = (v) => Math.round(v).toLocaleString('en-IN'), color = 0 }) => {
  const max = nice(Math.max(...items.map((i) => i.value), 1));
  if (horizontal) {
    return (
      <ul role="img" aria-label={label} className="flex flex-col gap-2.5">
        {items.map((it) => (
          <li key={it.label} className="grid grid-cols-[7.5rem_1fr_auto] items-center gap-2 text-xs">
            <span className="truncate text-ink/70">{it.label}</span>
            <span className="h-3.5 overflow-hidden rounded-full bg-ink/8">
              <span className="block h-full rounded-full" style={{ width: `${(it.value / max) * 100}%`, background: it.color || SERIES_COLORS[color] }} />
            </span>
            <span className="w-14 text-right font-semibold tabular-nums">{format(it.value)}</span>
          </li>
        ))}
      </ul>
    );
  }
  const W = 640, H = height, L = 38, R = 8, T = 10, B = 28;
  const slot = (W - L - R) / items.length;
  const bw = Math.min(46, slot * 0.64);
  const ticks = [0, 0.5, 1].map((f) => f * max);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="w-full">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={T + (1 - t / max) * (H - T - B)} y2={T + (1 - t / max) * (H - T - B)} stroke={GRID} />
          <text x={L - 6} y={T + (1 - t / max) * (H - T - B) + 4} textAnchor="end" fontSize="13" fill={AXIS}>{compact(t)}</text>
        </g>
      ))}
      {items.map((it, i) => {
        const h = (it.value / max) * (H - T - B);
        const cx = L + slot * i + slot / 2;
        return (
          <g key={it.label}>
            <rect x={cx - bw / 2} y={T + (H - T - B) - h} width={bw} height={Math.max(h, 1)} rx="5" fill={it.color || SERIES_COLORS[color]}><title>{`${it.label}: ${format(it.value)}`}</title></rect>
            <text x={cx} y={T + (H - T - B) - h - 5} textAnchor="middle" fontSize="13" fontWeight="600" fill="rgb(28 28 31 / 0.8)">{format(it.value)}</text>
            <text x={cx} y={H - 9} textAnchor="middle" fontSize="13" fill={AXIS}>{it.label.length > 11 ? `${it.label.slice(0, 10)}…` : it.label}</text>
          </g>
        );
      })}
    </svg>
  );
};

// ---------------------------------------------------------------- histogram
export const bin = (values, count, lo = Math.min(...values), hi = Math.max(...values)) => {
  const step = (hi - lo) / count || 1;
  const counts = Array(count).fill(0);
  values.forEach((v) => { counts[Math.min(count - 1, Math.floor((v - lo) / step))] += 1; });
  return counts.map((n, i) => ({ from: lo + i * step, to: lo + (i + 1) * step, n }));
};

export const Histogram = ({ bins, height = 200, label, unit = '' }) => {
  const W = 640, H = height, L = 30, R = 8, T = 10, B = 34;
  const max = nice(Math.max(...bins.map((b) => b.n), 1));
  const bw = (W - L - R) / bins.length;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="w-full">
      {[0, 0.5, 1].map((f) => (
        <g key={f}>
          <line x1={L} x2={W - R} y1={T + (1 - f) * (H - T - B)} y2={T + (1 - f) * (H - T - B)} stroke={GRID} />
          <text x={L - 6} y={T + (1 - f) * (H - T - B) + 4} textAnchor="end" fontSize="13" fill={AXIS}>{Math.round(f * max)}</text>
        </g>
      ))}
      {bins.map((b, i) => {
        const h = (b.n / max) * (H - T - B);
        return (
          <g key={i}>
            <rect x={L + i * bw + 1.5} y={T + (H - T - B) - h} width={bw - 3} height={Math.max(h, 1)} rx="3" fill="var(--color-accent)" opacity={b.n ? 1 : 0.2}>
              <title>{`${compact(b.from)} to ${compact(b.to)}${unit}: ${b.n}`}</title>
            </rect>
            {i % 2 === 0 && <text x={L + i * bw} y={H - 18} fontSize="13" fill={AXIS} textAnchor="start">{compact(b.from)}</text>}
          </g>
        );
      })}
      
    </svg>
  );
};

// ---------------------------------------------------------------- heatmap (day x hour)
export const Heatmap = ({ days, hours, grid, label }) => {
  const max = Math.max(...grid.flat(), 1);
  const W = 640, L = 34, T = 6, cw = (W - L - 4) / hours.length, ch = 22, H = T + days.length * ch + 22;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="w-full">
      {days.map((d, r) => (
        <g key={d}>
          <text x={L - 6} y={T + r * ch + ch / 2 + 4} textAnchor="end" fontSize="13" fill={AXIS}>{d}</text>
          {hours.map((h, c) => {
            const v = grid[r][c];
            return (
              <rect key={h} x={L + c * cw + 1} y={T + r * ch + 1} width={cw - 2} height={ch - 2} rx="4" fill="var(--color-accent)" opacity={0.08 + 0.92 * (v / max)}>
                <title>{`${d} ${h}: ${v.toFixed(1)}% engagement`}</title>
              </rect>
            );
          })}
        </g>
      ))}
      {hours.map((h, c) => (c % 3 === 0 ? <text key={h} x={L + c * cw + cw / 2} y={H - 6} textAnchor="middle" fontSize="13" fill={AXIS}>{h}</text> : null))}
    </svg>
  );
};

// ---------------------------------------------------------------- donut
export const Donut = ({ items, label, size = 160 }) => {
  const total = items.reduce((a, i) => a + i.value, 0) || 1;
  const R = 54, C = 2 * Math.PI * R;
  const arcs = useMemo(() => {
    let acc = 0;
    return items.map((it) => { const len = (it.value / total) * C; const a = { ...it, len, off: -acc }; acc += len; return a; });
  }, [items, total, C]);
  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg viewBox="0 0 140 140" width={size} height={size} role="img" aria-label={label}>
        <circle cx="70" cy="70" r={R} fill="none" stroke={GRID} strokeWidth="18" />
        {arcs.map((a, i) => (
          <circle key={a.label} cx="70" cy="70" r={R} fill="none" stroke={SERIES_COLORS[i % SERIES_COLORS.length]} strokeWidth="18"
            strokeDasharray={`${Math.max(a.len - 1.5, 0)} ${C}`} strokeDashoffset={a.off} transform="rotate(-90 70 70)"><title>{`${a.label}: ${Math.round((a.value / total) * 100)}%`}</title></circle>
        ))}
        <text x="70" y="68" textAnchor="middle" fontSize="20" fontWeight="700" fill="#1c1c1f">{compact(total)}</text>
        <text x="70" y="84" textAnchor="middle" fontSize="11" fill={AXIS}>total</text>
      </svg>
      <ul className="flex flex-col gap-1.5 text-sm">
        {items.map((it, i) => (
          <li key={it.label} className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: SERIES_COLORS[i % SERIES_COLORS.length] }} />{it.label}<span className="ml-1 font-semibold tabular-nums">{Math.round((it.value / total) * 100)}%</span></li>
        ))}
      </ul>
    </div>
  );
};

// ---------------------------------------------------------------- funnel
export const FunnelChart = ({ steps, label }) => {
  const top = Math.max(steps[0]?.value || 1, 1);
  return (
    <ol role="img" aria-label={label} className="flex flex-col gap-1.5">
      {steps.map((s, i) => (
        <li key={s.label} className="grid grid-cols-[8rem_1fr_auto] items-center gap-2 text-xs">
          <span className="truncate text-ink/70">{s.label}</span>
          <span className="h-6 rounded-md bg-ink/6">
            <span className="flex h-full items-center rounded-md px-2 font-semibold text-on-accent" style={{ width: `${Math.max((s.value / top) * 100, 6)}%`, background: 'var(--color-accent)', opacity: 1 - i * 0.1 }} />
          </span>
          <span className="w-20 text-right tabular-nums"><strong>{s.value}</strong>{i > 0 && <span className="text-ink/50"> ({Math.round((s.value / steps[i - 1].value) * 100)}%)</span>}</span>
        </li>
      ))}
    </ol>
  );
};

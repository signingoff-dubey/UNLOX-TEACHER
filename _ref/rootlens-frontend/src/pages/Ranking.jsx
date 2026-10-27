import Solutions from '../components/Solutions';
import { useState } from 'react';
import { ArrowRight, Info } from 'lucide-react';
import { CardTitle, ChipToggle } from '../components/ui';
import { num } from '../lib/format';
import { StableChip } from './Overview';
import Gate from '../components/ui/Gate';
import { navigate } from '../lib/router';
import { isRecommended } from '../components/RunResult';
import { useApi } from '../lib/useApi';

const AXIS_MAX = 60; // rank axis: 1 (best) to 60; anything ranked lower is drawn at the right edge

// One row: mean rank as a dot, ± std as a bar, on a shared rank axis. Lower is better, so the axis runs left to right from rank 1.
const RankBar = ({ r }) => {
  const x = (v) => `${(Math.min(Math.max(v, 1), AXIS_MAX) - 1) / (AXIS_MAX - 1) * 100}%`;
  const lo = r.mean_rank - r.rank_std;
  const hi = r.mean_rank + r.rank_std;
  return (
    <span className="relative block h-5" aria-hidden="true">
      <span className="absolute inset-x-0 top-1/2 h-px bg-ink/12" />
      <span className="absolute inset-y-0 w-px bg-ink/15" style={{ left: x(10) }} />
      <span className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-accent/35" style={{ left: x(lo), width: `calc(${x(hi)} - ${x(lo)})` }} />
      <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-accent shadow" style={{ left: x(r.mean_rank) }} />
    </span>
  );
};

const Detail = ({ r, ranking, windows }) => {
  const w = windows.find((s) => s.feature === r.feature);
  const recommended = Boolean(w) && isRecommended(w);
  const members = ranking.groups.find((g) => g.group === r.group)?.features ?? [];
  const peers = members.filter((f) => f !== r.feature);
  const shown = peers.slice(0, 6);
  return (
    <section className="card" aria-live="polite">
      <CardTitle sub={`Correlation group ${r.group}${shown.length ? `, with ${shown.join(', ')}${peers.length > shown.length ? ` and ${peers.length - shown.length} more` : ''}` : ''}`} action={<StableChip stable={r.stable} />}>
        <span className="font-mono">{r.feature}</span>
      </CardTitle>
      <dl className="grid grid-cols-2 gap-3 text-sm">
        {[
          ['Mean rank', `${r.mean_rank.toFixed(1)} ± ${r.rank_std.toFixed(1)}`],
          ['In top 10', `${Math.round(r.top_k_freq * 100)}% of ${ranking.n_bootstrap} refits`],
          ['Mean |SHAP|', r.mean_abs_shap.toFixed(3)],
          ['Safe window', recommended ? `${num(w.window[0], 3)} to ${num(w.window[1], 3)}` : w ? `Not recommended (${w.status})` : r.stable ? 'Not enough runs per bin' : 'Only for stable drivers'],
        ].map(([k, v]) => (
          <div key={k} className="rounded-xl bg-ink/5 p-3">
            <dt className="text-xs text-ink/60">{k}</dt>
            <dd className="tabular mt-0.5 font-semibold">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs leading-relaxed text-ink/60">
        Features are anonymised, so RootLens does not say what {r.feature} physically measures. A high rank means failures move with it in this data; it may also track another variable.
      </p>
      {w && (
        <button type="button" onClick={() => navigate('windows', r.feature)} className="btn-primary mt-3">
          {recommended ? 'See its safe window' : 'See its window, not recommended'} <ArrowRight size={15} />
        </button>
      )}
    </section>
  );
};

const Body = ({ ranking, windows }) => {
  const RANKING = ranking.features;
  const [filter, setFilter] = useState('all');
  const [picked, setPicked] = useState(RANKING[0].feature);
  const rows = filter === 'stable' ? RANKING.filter((r) => r.stable) : RANKING;
  const current = RANKING.find((r) => r.feature === picked) ?? RANKING[0];

  return (
    <div className="grid gap-[var(--gap)] 2xl:grid-cols-[1.5fr_1fr]">
      <section className="card">
        <CardTitle
          sub={`${ranking.method}. Dot: mean rank. Bar: ± one standard deviation. Top ${RANKING.length} of the modelled parameters shown.`}
          action={<ChipToggle multiple={false} value={filter} onChange={setFilter} options={[{ id: 'all', label: 'All' }, { id: 'stable', label: 'Stable only' }]} />}
        >
          Suspected drivers of failure
        </CardTitle>
        <div className="mb-1 hidden grid-cols-[2rem_5rem_1fr_4.5rem_6rem] items-center gap-3 px-2 text-[11px] font-medium text-ink/55 sm:grid">
          <span>#</span><span>Feature</span><span className="flex justify-between"><span>rank 1</span><span>10</span><span>{AXIS_MAX}+</span></span><span className="text-right">Top 10</span><span />
        </div>
        <ul className="flex flex-col gap-1">
          {rows.map((r) => {
            const i = RANKING.indexOf(r);
            const on = r.feature === current.feature;
            return (
              <li key={r.feature}>
                <button
                  type="button"
                  onClick={() => setPicked(r.feature)}
                  aria-pressed={on}
                  aria-label={`${r.feature}, mean rank ${r.mean_rank.toFixed(1)} plus or minus ${r.rank_std.toFixed(1)}, in top 10 ${Math.round(r.top_k_freq * 100)}% of refits, ${r.stable ? 'stable' : 'unstable'}`}
                  className={`grid w-full grid-cols-[2rem_5rem_1fr_6rem] items-center gap-3 rounded-xl px-2 py-2 text-left text-sm transition-colors sm:grid-cols-[2rem_5rem_1fr_4.5rem_6rem] ${on ? 'bg-accent-soft' : 'hover:bg-ink/5'}`}
                >
                  <span className="tabular font-semibold text-ink/45">{i + 1}</span>
                  <span className="font-mono font-semibold">{r.feature}</span>
                  <RankBar r={r} />
                  <span className="tabular hidden text-right text-ink/70 sm:block">{Math.round(r.top_k_freq * 100)}%</span>
                  <span className="justify-self-end"><StableChip stable={r.stable} /></span>
                </button>
              </li>
            );
          })}
        </ul>
        <p className="mt-4 flex items-start gap-2 rounded-xl bg-ink/5 p-3 text-xs text-ink/70">
          <Info size={14} className="mt-0.5 shrink-0" />
          Cross-check: L1 stability selection agrees on {ranking.l1_overlap.overlap.length} of the SHAP top {ranking.l1_overlap.shap_top.length}. {ranking.label}
        </p>
      </section>
      <div className="2xl:sticky 2xl:top-0 2xl:self-start">
        <Detail r={current} ranking={ranking} windows={windows} />
      </div>
    </div>
  );
};

const Ranking = () => {
  const q = useApi(['/api/ranking', '/api/safe-windows']);
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Gate q={q} what="The ranking">{([ranking, sw]) => <Body ranking={ranking} windows={sw.windows} />}</Gate>
      <Solutions />
    </div>
  );
};

export default Ranking;

import { Target, Scale, Crosshair, ShieldCheck } from 'lucide-react';
import { navigate } from '../../lib/router';
import { ci, pct } from '../../lib/format';

const CardShell = ({ title, icon: Icon, iconClass, children, foot }) => (
  <article className="flex flex-col justify-between gap-3 rounded-2xl bg-white p-4 text-ink">
    <div className="flex items-center justify-between gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <span className={`grid size-7 place-items-center rounded-full ${iconClass}`}>
        <Icon size={14} strokeWidth={2.5} />
      </span>
    </div>
    <div className="flex items-end justify-between gap-3">{children}</div>
    {foot && <p className="text-xs text-ink/60">{foot}</p>}
  </article>
);

const Value = ({ value, unit }) => (
  <p className="min-w-0">
    <span className="tabular text-2xl font-bold tracking-tight">{value}</span> <span className="text-xs font-medium text-ink/55">{unit}</span>
  </p>
);

const Gauge = ({ ratio }) => {
  const length = Math.PI * 16;
  return (
    <svg viewBox="0 0 40 24" className="h-10 w-16 shrink-0" aria-hidden="true">
      <path d="M4 20 A16 16 0 0 1 36 20" fill="none" stroke="#e7e7ea" strokeWidth="5" strokeLinecap="round" />
      <path d="M4 20 A16 16 0 0 1 36 20" fill="none" stroke="var(--color-good)" strokeWidth="5" strokeLinecap="round" strokeDasharray={`${length * ratio} ${length}`} />
    </svg>
  );
};

// Test-window metrics from metrics.json. PR-AUC and MCC, never accuracy (CLAUDE.md rule 4).
const StatCards = ({ metrics, stable, total, refits = 50 }) => {
  const m = metrics;
  return (
    <div className="grid grid-cols-1 gap-[var(--gap)] sm:grid-cols-2 2xl:grid-cols-4">
      <CardShell title="PR-AUC" icon={Target} iconClass="bg-info/12 text-info" foot={`95% CI ${ci(m.prAuc.ci)}. Chance level is ${pct(m.positiveRate)}.`}>
        <Value value={m.prAuc.value.toFixed(2)} unit={`vs ${m.baseline.prAuc.value.toFixed(2)} logistic baseline`} />
      </CardShell>
      <CardShell title="MCC" icon={Scale} iconClass="bg-warn/15 text-warn" foot={`95% CI ${ci(m.mcc.ci)}. 0 means no better than chance.`}>
        <Value value={m.mcc.value.toFixed(2)} unit={`vs ${m.baseline.mcc.value.toFixed(2)} logistic baseline`} />
      </CardShell>
      <CardShell title={`Recall at ${pct(m.recallAtP.precision, 0)} precision`} icon={Crosshair} iconClass="bg-rose/12 text-rose" foot="Single point on the test window; no interval computed.">
        <Value value={pct(m.recallAtP.value, 0)} unit="of fails caught" />
      </CardShell>
      <CardShell title="Stable drivers" icon={ShieldCheck} iconClass="bg-good/12 text-good" foot={`Top 10 in at least 70% of ${refits} refits, and above the label-permutation noise floor.`}>
        <Value value={`${stable}/${total}`} unit="ranked" />
        <div className="flex items-center gap-2">
          <Gauge ratio={total ? stable / total : 0} />
          <button type="button" onClick={() => navigate('ranking')} className="btn-dark h-8 shrink-0 px-3.5 text-xs">
            Ranking
          </button>
        </div>
      </CardShell>
    </div>
  );
};

export default StatCards;

import Solutions from '../components/Solutions';
import { ArrowRight, ShieldCheck, ShieldQuestion } from 'lucide-react';
import StatCards from '../components/dashboard/StatCards';
import { ChartCard, LineChart } from '../components/charts';
import { Banner, CardTitle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { navigate } from '../lib/router';
import { useApi, dailyFrom, RUN_PATHS } from '../lib/useApi';
import { day } from '../lib/dataset';

// Index of the week a date falls in, for the split markers on the trend chart.
const weekOf = (start, date) => Math.floor((new Date(`${date}T00:00:00`) - new Date(`${start}T00:00:00`)) / (7 * 864e5));

// Fail rate per 7-day bucket, from the daily run counts.
const weekly = (daily) => {
  const out = [];
  for (let i = 0; i < daily.length; i += 7) {
    const w = daily.slice(i, i + 7);
    const runs = w.reduce((a, x) => a + x.runs, 0);
    const fails = w.reduce((a, x) => a + x.fails, 0);
    out.push({ label: new Date(`${w[0].date}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' }), rate: runs ? (100 * fails) / runs : 0, runs, fails });
  }
  return out;
};

export const StableChip = ({ stable }) => (
  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${stable ? 'bg-good/12 text-good' : 'bg-ink/8 text-ink/65'}`}>
    {stable ? <ShieldCheck size={12} /> : <ShieldQuestion size={12} />}
    {stable ? 'Stable' : 'Unstable'}
  </span>
);

const TopDrivers = ({ ranking }) => (
  <section className="card">
    <CardTitle
      sub={`Mean rank over ${ranking.n_bootstrap} refits. Statistically suspected, not a proven cause.`}
      action={
        <button type="button" onClick={() => navigate('ranking')} className="btn-ghost h-8 px-3 text-xs">
          Full ranking <ArrowRight size={13} />
        </button>
      }
    >
      Where to look first
    </CardTitle>
    <ol className="flex flex-col divide-y divide-ink/8">
      {ranking.features.slice(0, 5).map((r, i) => (
        <li key={r.feature} className="flex items-center gap-3 py-2.5">
          <span className="tabular w-5 text-sm font-semibold text-ink/45">{i + 1}</span>
          <span className="min-w-0 flex-1">
            <span className="font-mono text-sm font-semibold">{r.feature}</span>
            <span className="ml-2 text-xs text-ink/55">group {r.group}</span>
          </span>
          <span className="tabular text-xs text-ink/60">rank {r.mean_rank.toFixed(1)} ± {r.rank_std.toFixed(1)}</span>
          <StableChip stable={r.stable} />
        </li>
      ))}
    </ol>
  </section>
);

const DataHandling = ({ metrics, overview }) => (
  <section className="card">
    <CardTitle sub="Cleaning applied before modelling, and the time-based split.">Data handling</CardTitle>
    <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
      {[
        ['Columns kept', metrics.preprocessing.kept],
        ['Dropped, constant', metrics.preprocessing.dropped_constant],
        ['Dropped, >60% missing', metrics.preprocessing.dropped_too_missing],
        ['Missingness flags', metrics.preprocessing.missing_flags],
      ].map(([k, v]) => (
        <div key={k} className="rounded-xl bg-ink/5 p-3">
          <dd className="tabular text-xl font-bold">{v}</dd>
          <dt className="text-xs text-ink/60">{k}</dt>
        </div>
      ))}
    </dl>
    <table className="mt-4 w-full text-left text-sm">
      <caption className="sr-only">Time-based split</caption>
      <thead className="text-xs text-ink/55">
        <tr><th className="pb-1 font-medium">Window</th><th className="pb-1 font-medium">Dates</th><th className="pb-1 text-right font-medium">Runs</th><th className="pb-1 text-right font-medium">Fails</th></tr>
      </thead>
      <tbody className="tabular">
        {[['Train', overview.split.train], ['Validation', overview.split.val], ['Test', overview.split.test]].map(([k, w]) => (
          <tr key={k} className="border-t border-ink/8">
            <td className="py-1.5 font-medium">{k}</td>
            <td className="py-1.5 text-ink/65">{day(w.start)} to {day(w.end)}</td>
            <td className="py-1.5 text-right">{w.n}</td>
            <td className="py-1.5 text-right">{w.fails}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </section>
);

const Confusion = ({ test }) => {
  const { tp, fp, fn, tn } = test.confusion;
  const cell = (n, label, strong) => (
    <div className={`rounded-xl p-3 ${strong ? 'bg-accent-soft' : 'bg-ink/5'}`}>
      <p className="tabular text-xl font-bold">{n}</p>
      <p className="text-xs text-ink/60">{label}</p>
    </div>
  );
  return (
    <section className="card">
      <CardTitle sub={`Test window, threshold ${test.threshold.toFixed(2)} chosen from the cost of a missed defect versus a false alarm.`}>Confusion matrix</CardTitle>
      <div className="grid grid-cols-2 gap-2">
        {cell(tp, 'Fails caught', true)}
        {cell(fn, 'Fails missed')}
        {cell(fp, 'False alarms')}
        {cell(tn, 'Passes cleared')}
      </div>
    </section>
  );
};

const Body = ({ overview, metrics, ranking, daily }) => {
  const test = metrics.lightgbm.test;
  const base = metrics.logistic_baseline.test;
  const stable = ranking.features.filter((r) => r.stable).length;
  const weeks = weekly(daily);
  const start = day(overview.data.time_start);
  const stats = {
    prAuc: { value: test.pr_auc.point, ci: [test.pr_auc.low, test.pr_auc.high] },
    mcc: { value: test.mcc.point, ci: [test.mcc.low, test.mcc.high] },
    recallAtP: { precision: 0.3, value: test['recall_at_precision_0.3'] },
    baseline: { prAuc: { value: base.pr_auc.point }, mcc: { value: base.mcc.point } },
    positiveRate: test.prevalence,
  };
  const beaten = /does not beat/i.test(metrics.verdict);
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone={beaten ? 'warn' : 'info'}>
        <strong>{metrics.verdict}.</strong> Test-window scores rest on {test.positives} failures, so the intervals are wide. Random-split PR-AUC is {metrics.leakage_contrast.random_split_pr_auc.toFixed(2)}, shown only as a leaky contrast. {metrics.leakage_contrast.note}
      </Banner>
      <StatCards metrics={stats} stable={stable} total={ranking.features.length} refits={ranking.n_bootstrap} />
      <div className="grid gap-[var(--gap)] 2xl:grid-cols-[1.4fr_1fr]">
        <ChartCard
          title="Weekly fail rate"
          sub="Share of runs that failed, by week. Dashed lines mark where validation and test begin."
          live
          table={{ head: ['Week of', 'Runs', 'Fails', 'Fail rate'], rows: weeks.map((w) => [w.label, w.runs, w.fails, `${w.rate.toFixed(1)}%`]) }}
        >
          <LineChart
            labels={weeks.map((w) => w.label)}
            series={[{ name: 'Fail rate', values: weeks.map((w) => w.rate) }]}
            format={(v) => `${v.toFixed(1)}%`}
            markers={[{ at: weekOf(start, day(overview.split.val.start)), label: 'Validation' }, { at: weekOf(start, day(overview.split.test.start)), label: 'Test' }]}
            label="Weekly fail rate across the data period"
          />
        </ChartCard>
        <TopDrivers ranking={ranking} />
      </div>
      <Solutions />
      <div className="grid gap-[var(--gap)] xl:grid-cols-2">
        <DataHandling metrics={metrics} overview={overview} />
        <Confusion test={test} />
      </div>
    </div>
  );
};

const Overview = () => {
  const q = useApi(['/api/overview', '/api/metrics', '/api/ranking']);
  const runs = useApi(RUN_PATHS);
  const all = { ...q, data: q.data && runs.data ? [...q.data, dailyFrom(runs.data)] : null, loading: q.loading || runs.loading, error: q.error || runs.error, refetch: () => (q.refetch(), runs.refetch()) };
  return <Gate q={all} what="The overview">{([overview, metrics, ranking, daily]) => <Body overview={overview} metrics={metrics} ranking={ranking} daily={daily} />}</Gate>;
};

export default Overview;

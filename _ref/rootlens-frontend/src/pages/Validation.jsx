import { CircleCheck, CircleX } from 'lucide-react';
import { Banner, CardTitle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { pct } from '../lib/format';
import { useApi } from '../lib/useApi';

const MODES = { TWF: 'Tool wear', HDF: 'Heat dissipation', PWF: 'Power', OSF: 'Overstrain' };

// One feature id, coloured by what it is: a planted cause that was found, or a flag that was not planted.
const Flag = ({ id, hit }) => (
  <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-xs font-semibold ${hit ? 'bg-good/15 text-good' : 'bg-bad/12 text-bad'}`}>
    {hit ? <CircleCheck size={11} /> : <CircleX size={11} />}
    {id}
  </span>
);

const Big = ({ value, label, strong }) => (
  <div className={`rounded-2xl p-4 ${strong ? 'bg-accent text-on-accent' : 'bg-ink/5'}`}>
    <p className="tabular text-3xl font-bold tracking-tight">{value}</p>
    <p className={`mt-1 text-xs ${strong ? 'opacity-80' : 'text-ink/60'}`}>{label}</p>
  </div>
);

const Side = ({ title, sub, recall, falseFlags, nullFlags, strong }) => (
  <section className={`card ${strong ? 'ring-2 ring-accent' : ''}`}>
    <CardTitle sub={sub}>{title}</CardTitle>
    <div className="grid gap-3 sm:grid-cols-3">
      <Big value={pct(recall, 0)} label="Planted causes recovered (recall)" strong={strong} />
      <Big value={falseFlags.toFixed(1)} label="False flags per scenario" strong={strong} />
      <Big value={nullFlags} label="Flags when the labels are pure noise" strong={strong} />
    </div>
  </section>
);

const Planted = ({ data }) => {
  const s = data.summary;
  return (
    <>
      <Banner tone="info">
        {data.description} {data.n_scenarios} scenarios, {data.causes_per_scenario} planted causes each. A method passes by finding the planted causes without flagging others.
      </Banner>

      <div className="grid gap-[var(--gap)] xl:grid-cols-2">
        <Side title="Plain SHAP top-10" sub="Rank features by one model's SHAP size and take the top 10." recall={s.naive_shap_recall} falseFlags={s.naive_shap_false_flags_per_scenario} nullFlags={s.null_naive_flags} />
        <Side title="RootLens" sub={`Only features in the top 10 in at least ${pct(data.stable_threshold ?? 0.7, 0)} of bootstrap refits are flagged.`} recall={s.rootlens_recall} falseFlags={s.rootlens_false_flags_per_scenario} nullFlags={s.null_rootlens_stable} strong />
      </div>

      <section className="card">
        <CardTitle>What this shows</CardTitle>
        <p className="text-sm leading-relaxed text-ink/80">
          On pure noise, plain SHAP still names {s.null_naive_flags} features and RootLens names {s.null_rootlens_stable}. Across the planted scenarios RootLens raises {s.rootlens_false_flags_per_scenario.toFixed(1)} false flags per scenario against {s.naive_shap_false_flags_per_scenario.toFixed(1)}.
          {s.rootlens_recall < s.naive_shap_recall && <> The price is recall: RootLens recovers {pct(s.rootlens_recall, 0)} of planted causes against {pct(s.naive_shap_recall, 0)}, because it only reports drivers that stay in the top 10 across resamples.</>}
        </p>
        <p className="mt-2 text-xs text-ink/60">The labels here are synthetic, so this tests the method, not the plant. Statistically suspected, stability-checked: an association, never a proven cause.</p>
      </section>

      <section className="card">
        <CardTitle sub="Green is a planted cause that was found, red is a flag that was not planted.">Scenario by scenario</CardTitle>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead>
              <tr className="text-xs text-ink/55">
                <th className="pb-2 pr-3 font-medium">#</th>
                <th className="pb-2 pr-3 font-medium">Planted causes</th>
                <th className="pb-2 pr-3 font-medium">Plain SHAP flagged</th>
                <th className="pb-2 font-medium">RootLens flagged</th>
              </tr>
            </thead>
            <tbody>
              {data.scenarios.map((sc, i) => {
                const truth = new Set(sc.planted);
                return (
                  <tr key={i} className="border-t border-ink/10 align-top">
                    <td className="tabular py-3 pr-3 font-semibold">{i + 1}</td>
                    <td className="py-3 pr-3">
                      <ul className="flex flex-col gap-1">
                        {sc.planted.map((id) => {
                          const e = sc.effects?.find((x) => x.feature === id);
                          return (
                            <li key={id} className="text-xs">
                              <span className="font-mono font-semibold">{id}</span>
                              {e && <span className="ml-1.5 text-ink/55">{e.type}, {e.direction}</span>}
                              {sc.rootlens.planted_top_k_freq?.[id] !== undefined && <span className="tabular ml-1.5 text-ink/55">top-10 in {pct(sc.rootlens.planted_top_k_freq[id], 0)} of refits</span>}
                            </li>
                          );
                        })}
                      </ul>
                    </td>
                    <td className="py-3 pr-3">
                      <div className="flex flex-wrap gap-1">{sc.naive_shap.top_k.map((id) => <Flag key={id} id={id} hit={truth.has(id)} />)}</div>
                      <p className="tabular mt-1.5 text-xs text-ink/60">{sc.naive_shap.recovered} of {sc.planted.length} found, {sc.naive_shap.false_flags} false</p>
                    </td>
                    <td className="py-3">
                      {sc.rootlens.stable.length ? <div className="flex flex-wrap gap-1">{sc.rootlens.stable.map((id) => <Flag key={id} id={id} hit={truth.has(id)} />)}</div> : <p className="text-xs text-ink/55">Nothing reached the stability bar.</p>}
                      <p className="tabular mt-1.5 text-xs text-ink/60">{sc.rootlens.recovered} of {sc.planted.length} found, {sc.rootlens.false_flags} false</p>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {data.null_scenario && (
        <section className="card">
          <CardTitle sub={data.null_scenario.note}>Null scenario: labels are noise</CardTitle>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-xs font-semibold text-ink/60">Plain SHAP flagged {data.null_scenario.naive_shap_top_k.length}</p>
              <div className="mt-2 flex flex-wrap gap-1">{data.null_scenario.naive_shap_top_k.map((id) => <Flag key={id} id={id} hit={false} />)}</div>
            </div>
            <div>
              <p className="text-xs font-semibold text-ink/60">RootLens flagged {data.null_scenario.rootlens_stable.length}</p>
              {data.null_scenario.rootlens_stable.length ? (
                <div className="mt-2 flex flex-wrap gap-1">{data.null_scenario.rootlens_stable.map((id) => <Flag key={id} id={id} hit={false} />)}</div>
              ) : (
                <p className="mt-2 text-sm text-good">No driver passed the stability check, which is the right answer for noise.</p>
              )}
            </div>
          </div>
        </section>
      )}
    </>
  );
};

const Ai4i = ({ data }) => {
  const modes = Object.entries(data.per_failure_mode);
  return (
    <section className="card">
      <CardTitle sub={data.description}>AI4I 2020: do the ranked inputs match the known failure rules?</CardTitle>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="text-xs text-ink/55">
              <th className="pb-2 pr-3 font-medium">Failure mode</th>
              <th className="pb-2 pr-3 font-medium">Inputs that define it</th>
              <th className="pb-2 pr-3 font-medium">Ranked highest</th>
              <th className="pb-2 pr-3 font-medium">Recovered</th>
              <th className="pb-2 font-medium">Failures</th>
            </tr>
          </thead>
          <tbody>
            {modes.map(([mode, m]) => {
              const known = new Set(m.known_inputs);
              return (
                <tr key={mode} className="border-t border-ink/10 align-top">
                  <td className="py-3 pr-3"><span className="font-semibold">{mode}</span><span className="block text-xs text-ink/55">{MODES[mode]}</span></td>
                  <td className="py-3 pr-3"><div className="flex flex-wrap gap-1">{m.known_inputs.map((id) => <span key={id} className="rounded-md bg-ink/8 px-1.5 py-0.5 font-mono text-xs">{id}</span>)}</div></td>
                  <td className="py-3 pr-3"><div className="flex flex-wrap gap-1">{m.ranked_top.map((id) => <Flag key={id} id={id} hit={known.has(id)} />)}</div></td>
                  <td className="tabular py-3 pr-3 font-semibold">{m.recovered} of {m.known_inputs.length}</td>
                  <td className="tabular py-3">{m.n_failures}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h3 className="mt-5 text-sm font-semibold">Overall ranking across all failure modes</h3>
      <ol className="mt-2 grid gap-1.5 text-sm sm:grid-cols-2">
        {data.overall_ranking.map((r, i) => (
          <li key={r.feature} className="flex items-center gap-3 rounded-xl bg-ink/5 px-3 py-2">
            <span className="tabular w-5 text-xs text-ink/50">{i + 1}</span>
            <span className="min-w-0 flex-1 truncate font-mono text-xs font-semibold">{r.feature}</span>
            <span className="tabular text-xs text-ink/60">rank {r.mean_rank.toFixed(1)}, top-10 in {pct(r.top_k_freq, 0)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
};

const Validation = () => {
  const planted = useApi('/api/validation/planted');
  const ai4i = useApi('/api/validation/ai4i');
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Gate q={planted} what="The planted-fault benchmark">{(d) => <Planted data={d} />}</Gate>
      <Gate q={ai4i} what="The AI4I check">{(d) => <Ai4i data={d} />}</Gate>
    </div>
  );
};

export default Validation;

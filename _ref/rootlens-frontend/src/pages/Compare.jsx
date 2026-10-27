import { ExternalLink } from 'lucide-react';
import { Banner, CardTitle } from '../components/ui';
import Gate from '../components/ui/Gate';
import { useApi } from '../lib/useApi';

const STATUS = {
  yes: { label: 'Yes', cls: 'bg-good/15 text-good' },
  partial: { label: 'Partial', cls: 'bg-warn/15 text-warn' },
  no: { label: 'No', cls: 'bg-ink/10 text-ink/65' },
};

const Chip = ({ status }) => {
  const s = STATUS[status] ?? STATUS.no;
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.cls}`}>{s.label}</span>;
};

const Others = ({ o }) => {
  if (!o) return <span className="text-xs text-ink/45">Not checked</span>;
  const none = o.found_in === 0;
  return (
    <div>
      <p className="tabular text-sm font-semibold">
        {none ? `We did not find this in the ${o.checked} sources we checked` : `Found in ${o.found_in} of ${o.checked} public projects we checked`}
      </p>
      {o.note && !(none && /did not find/i.test(o.note)) && <p className="mt-0.5 text-xs text-ink/60">{o.note}</p>}
    </div>
  );
};

const Body = ({ d }) => (
  <div className="flex flex-col gap-[var(--gap)]">
    {d.wording && <Banner tone="info">{d.wording}</Banner>}
    <section className="card">
      <CardTitle sub="Counts come from the public projects listed below, read at one point in time. A project not listed may do any of this.">What each capability covers</CardTitle>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr className="text-xs text-ink/55">
              <th className="pb-2 pr-4 font-medium">Capability</th>
              <th className="pb-2 pr-4 font-medium">RootLens</th>
              <th className="pb-2 font-medium">Public projects we checked</th>
            </tr>
          </thead>
          <tbody>
            {d.rows.map((r) => (
              <tr key={r.capability} className="border-t border-ink/10 align-top">
                <td className="w-1/4 py-3 pr-4 font-semibold">{r.capability}</td>
                <td className="w-2/5 py-3 pr-4">
                  <Chip status={r.rootlens?.status} />
                  {r.rootlens?.evidence && <p className="mt-1.5 text-xs text-ink/65">{r.rootlens.evidence}</p>}
                </td>
                <td className="py-3"><Others o={r.others} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
    {d.sources?.length > 0 && (
      <section className="card">
        <CardTitle sub="Where the counts above come from.">Sources</CardTitle>
        <ul className="grid gap-2 sm:grid-cols-2">
          {d.sources.map((s) => (
            <li key={s.url ?? s.name}>
              {/^https?:\/\//i.test(s.url ?? '') ? (
                <a href={s.url} target="_blank" rel="noreferrer noopener" className="flex items-center justify-between gap-2 rounded-xl bg-ink/5 px-3 py-2 text-sm font-medium hover:bg-ink/10">
                  <span className="min-w-0 truncate">{s.name}</span>
                  <ExternalLink size={14} className="shrink-0 text-ink/50" />
                </a>
              ) : (
                <span className="block rounded-xl bg-ink/5 px-3 py-2 text-sm font-medium">{s.name}</span>
              )}
            </li>
          ))}
        </ul>
      </section>
    )}
  </div>
);

const Compare = () => {
  const q = useApi('/api/compare');
  return <Gate q={q} what="The comparison">{(d) => <Body d={d} />}</Gate>;
};

export default Compare;

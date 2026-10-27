import { CircleCheck, CircleSlash, Factory, Wrench } from 'lucide-react';
import { CardTitle } from './ui';
import Gate from './ui/Gate';
import { useApi } from '../lib/useApi';
import { pct } from '../lib/format';
import { navigate } from '../lib/router';
import { askAssistant } from './AssistantDock';

// "What to change": the line's corrective windows and the stations to start with, from /api/solutions.
// Shown on Overview, Root cause and Inspection so every screen ends with an action.
const Solutions = ({ compact = false, title = 'What to change' }) => {
  const q = useApi('/api/solutions');
  return (
    <section className="card">
      <CardTitle
        sub="Statistically suspected, stability-checked. Confirm each change with a pilot before rolling it out."
        action={<button type="button" onClick={() => askAssistant('What should we fix first, why, and what is it worth?')} className="btn-ghost h-9 px-3 text-sm">Ask AI why</button>}
      >
        <span className="flex items-center gap-2"><Wrench size={17} /> {title}</span>
      </CardTitle>
      <Gate q={q} what="The solutions">
        {(d) => (
          <div className="flex flex-col gap-3">
            <ul className="flex flex-col gap-2">
              {d.line.filter((s) => s.do).map((s) => (
                <li key={s.parameter} className={`rounded-xl p-3 text-sm ${s.do ? 'bg-good/12 ring-1 ring-good/30' : 'bg-ink/5'}`}>
                  <p className="flex items-center gap-2 font-semibold">
                    {s.do ? <CircleCheck size={16} className="text-good" /> : <CircleSlash size={16} className="text-ink/50" />}
                    {s.action}
                  </p>
                  <p className="mt-1 text-xs text-ink/65">
                    Failure rate {pct(s.evidence.fail_rate_inside)} inside the window vs {pct(s.evidence.fail_rate_outside)} outside ({s.evidence.runs_inside} runs).
                    {s.do ? ' Held on the later test window.' : ` Not recommended yet: ${s.reason_not}.`}
                  </p>
                  {!compact && s.do && (
                    <button type="button" onClick={() => navigate('pilot')} className="mt-2 text-xs font-semibold text-accent-deep hover:underline">Plan a pilot for {s.parameter} →</button>
                  )}
                </li>
              ))}
            </ul>
            {d.line.some((s) => !s.do) && (
              <details className="rounded-xl bg-ink/5 px-3 py-2 text-sm">
                <summary className="cursor-pointer font-medium text-ink/70">
                  {d.line.filter((s) => !s.do).length} more suspected parameters: not recommended yet
                </summary>
                <ul className="mt-2 flex flex-col gap-1 text-xs text-ink/65">
                  {d.line.filter((s) => !s.do).map((s) => (
                    <li key={s.parameter}><span className="font-semibold">{s.parameter}</span>: {s.reason_not}. Inside its window {pct(s.evidence.fail_rate_inside)} vs {pct(s.evidence.fail_rate_outside)} outside.</li>
                  ))}
                </ul>
              </details>
            )}
            {d.stations.length > 0 && !compact && (
              <div>
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink/55"><Factory size={13} /> Bosch line: where to start</p>
                <ul className="mt-2 flex flex-col gap-1.5">
                  {d.stations.slice(0, 3).map((s) => (
                    <li key={s.station} className="rounded-xl bg-ink/5 px-3 py-2 text-sm">
                      <span className="font-semibold">{s.station}</span>: review {s.parameters.join(', ')}
                      {s.fail_rate != null && <span className="text-xs text-ink/55"> · fail rate {pct(s.fail_rate, 2)}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Gate>
    </section>
  );
};

export default Solutions;

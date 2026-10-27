import { Wrench } from 'lucide-react';

// Why a defect type happens, what to check and what to change (backend/assembly/remedies.py).
// General engineering reference for the defect type; the line's own suspected parameters are in Solutions.
const Remedy = ({ r, open = false }) => {
  if (!r) return null;
  return (
    <details open={open} className="mt-2 rounded-xl bg-white/60 px-3 py-2 text-xs text-ink/80">
      <summary className="flex cursor-pointer items-center gap-1.5 font-semibold text-ink">
        <Wrench size={12} /> Fix: {r.actions[0]}
      </summary>
      <p className="mt-1.5 text-ink/60">Process stage: {r.stage}</p>
      <div className="mt-1.5 grid gap-2 sm:grid-cols-3">
        <div>
          <p className="font-semibold">Likely causes</p>
          <ul className="mt-0.5 list-disc pl-4">{r.causes.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
        <div>
          <p className="font-semibold">Parameters to check</p>
          <ul className="mt-0.5 list-disc pl-4">{r.checks.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
        <div>
          <p className="font-semibold">What to change</p>
          <ul className="mt-0.5 list-disc pl-4">{r.actions.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      </div>
      <p className="mt-1.5 text-[11px] text-ink/50">{r.source}</p>
    </details>
  );
};

export default Remedy;

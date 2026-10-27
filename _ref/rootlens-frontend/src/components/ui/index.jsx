import { Check, Cpu, Info, AlertTriangle, CircleAlert } from 'lucide-react';

export const ProviderChip = ({ name, latency, dark = true }) => (
  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${dark ? 'bg-white/10 text-white/75' : 'bg-ink/5 text-ink/70'}`}>
    <Cpu size={12} />
    {name}
    {latency && <span className={dark ? 'text-white/45' : 'text-ink/45'}>{latency}</span>}
  </span>
);

export const SyncDot = ({ state }) => {
  const map = {
    connected: { cls: 'bg-good', label: 'Synced' },
    reconnecting: { cls: 'bg-warn', label: 'Reconnecting' },
    offline: { cls: 'bg-white/40', label: 'Offline' },
  };
  const s = map[state];
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-white/60">
      <span className={`size-2 rounded-full ${s.cls}`} />
      {s.label}
    </span>
  );
};

// Win rate with confidence interval and repeat count (docs: ScoreBar).
export const ScoreBar = ({ score, label }) => {
  if (!score) return <span className="text-xs text-ink/45">Not scored yet</span>;
  const [lo, hi] = score.ci;
  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-semibold">{label ?? 'Win rate'} {Math.round(score.win_rate * 100)}%</span>
        <span className="text-ink/50">{Math.round(lo * 100)}–{Math.round(hi * 100)}% over {score.repeats} runs</span>
      </div>
      <div className="relative mt-1.5 h-2 rounded-full bg-ink/8">
        <span className="absolute inset-y-0 rounded-full bg-accent/30" style={{ left: `${lo * 100}%`, width: `${(hi - lo) * 100}%` }} />
        <span className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-accent" style={{ left: `${score.win_rate * 100}%` }} />
        <span className="absolute inset-y-[-3px] w-px bg-ink/30" style={{ left: '50%' }} title="50%: no preference" />
      </div>
    </div>
  );
};

// Three bars: rate-limit time, money, review effort, each against its cap.

export const Banner = ({ tone = 'info', children, action }) => {
  const map = {
    info: { icon: Info, cls: 'bg-info/15 text-white ring-info/30' },
    warn: { icon: AlertTriangle, cls: 'bg-warn/20 text-white ring-warn/40' },
    bad: { icon: CircleAlert, cls: 'bg-bad/20 text-white ring-bad/40' },
    good: { icon: Check, cls: 'bg-good/20 text-white ring-good/40' },
  };
  const { icon: Icon, cls } = map[tone];
  return (
    <div className={`flex flex-wrap items-center gap-3 rounded-2xl px-4 py-3 text-sm ring-1 ${cls}`} role="status">
      <Icon size={18} className="shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
      {action}
    </div>
  );
};

export const CardTitle = ({ children, action, sub }) => (
  <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
    <div>
      <h2 className="font-semibold">{children}</h2>
      {sub && <p className="mt-0.5 text-xs text-ink/55">{sub}</p>}
    </div>
    {action}
  </div>
);

export const SectionTitle = ({ children, action }) => (
  <div className="mb-3 flex items-center justify-between gap-3">
    <h2 className="font-semibold">{children}</h2>
    {action}
  </div>
);

export const Tabs = ({ tabs, active, onChange, dark = false }) => (
  <div role="tablist" className={`flex flex-wrap gap-1 rounded-full p-1 ${dark ? 'bg-black/25 ring-1 ring-white/10' : 'bg-ink/5'}`}>
    {tabs.map((t) => (
      <button
        key={t}
        type="button"
        role="tab"
        aria-selected={active === t}
        onClick={() => onChange(t)}
        className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
          active === t ? 'bg-accent text-on-accent' : dark ? 'text-white/60 hover:text-white' : 'text-ink/60 hover:text-ink'
        }`}
      >
        {t}
      </button>
    ))}
  </div>
);

// Multi-select chip group used for languages, channels, days and filters.
export const ChipToggle = ({ options, value, onChange, multiple = true }) => (
  <div className="flex flex-wrap gap-2">
    {options.map((o) => {
      const on = multiple ? value.includes(o.id) : value === o.id;
      return (
        <button
          key={o.id}
          type="button"
          aria-pressed={on}
          onClick={() => onChange(multiple ? (on ? value.filter((v) => v !== o.id) : [...value, o.id]) : o.id)}
          className={`inline-flex h-9 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium transition-colors ${
            on ? 'bg-ink text-white' : 'bg-ink/5 text-ink/70 hover:bg-ink/10'
          }`}
        >
          {on && multiple && <Check size={14} />}
          {o.label}
        </button>
      );
    })}
  </div>
);

export const Field = ({ label, hint, children, error }) => (
  <label className="flex flex-col gap-1.5 text-sm">
    <span className="font-medium">{label}</span>
    {children}
    {error ? <span className="text-xs font-medium text-bad">{error}</span> : hint && <span className="text-xs text-ink/50">{hint}</span>}
  </label>
);

export const Toggle = ({ checked, onChange, label, disabled = false }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    disabled={disabled}
    onClick={() => !disabled && onChange?.(!checked)}
    className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${checked ? 'bg-accent' : 'bg-ink/20'} ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
  >
    <span className={`absolute left-0.5 top-0.5 size-5 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0'}`} />
  </button>
);

export const Empty = ({ icon: Icon, title, children, action }) => (
  <div className="grid place-items-center rounded-3xl border border-dashed border-white/15 px-6 py-12 text-center">
    {Icon && (
      <span className="grid size-12 place-items-center rounded-2xl bg-accent/15 text-accent">
        <Icon size={22} />
      </span>
    )}
    <p className="mt-4 font-medium">{title}</p>
    {children && <p className="mt-1 max-w-sm text-sm text-white/55">{children}</p>}
    {action && <div className="mt-5">{action}</div>}
  </div>
);

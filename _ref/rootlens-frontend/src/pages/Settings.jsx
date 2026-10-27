import { useState } from 'react';
import { Check, RotateCcw, Loader2, PlugZap, Play } from 'lucide-react';
import ColorPicker from '../components/ColorPicker.jsx';
import AlertsTab from '../components/settings/AlertsTab.jsx';
import IntegrationsTab from '../components/settings/IntegrationsTab.jsx';
import { OPENING_OFF_KEY, REPLAY_EVENT } from '../components/Opening.jsx';
import { CardTitle, Field, Tabs, Toggle } from '../components/ui';
import { ACCENTS, BACKDROPS, DEFAULTS, DENSITIES, SURFACES, TEXT_SIZES, THEMES, useAppearance } from '../lib/appearance';
import { API_DEFAULTS, health, readApiSettings, saveApiSettings } from '../lib/api';

const TABS = ['Appearance', 'Alerts', 'Integrations', 'Data', 'About'];

const Choices = ({ name, options, value, onChange }) => (
  <div role="radiogroup" aria-label={name} className="flex flex-col gap-2">
    {options.map((o) => (
      <label key={o.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors ${value === o.id ? 'border-accent bg-accent-soft/60' : 'border-ink/10 hover:bg-ink/5'}`}>
        <input type="radio" name={name} checked={value === o.id} onChange={() => onChange(o.id)} className="mt-1 accent-[var(--color-accent)]" />
        <span><span className="font-medium">{o.label}</span>{o.hint && <span className="block text-xs text-ink/60">{o.hint}</span>}</span>
      </label>
    ))}
  </div>
);

// Segmented control for short option lists (density, text size).
const Segments = ({ name, options, value, onChange }) => (
  <div role="radiogroup" aria-label={name} className="inline-flex rounded-full bg-ink/5 p-1">
    {options.map((o) => (
      <button key={o.id} type="button" role="radio" aria-checked={value === o.id} onClick={() => onChange(o.id)} className={`h-9 rounded-full px-4 text-sm font-medium transition-colors ${value === o.id ? 'bg-accent text-on-accent' : 'text-ink/65 hover:text-ink'}`}>
        {o.label}
      </button>
    ))}
  </div>
);

const Row = ({ title, hint, children, dim = false }) => (
  <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ink/10 px-3 py-2.5 text-sm ${dim ? 'opacity-50' : ''}`}>
    <span className="min-w-0">
      <span className="font-medium">{title}</span>
      {hint && <span className="block text-xs text-ink/60">{hint}</span>}
    </span>
    {children}
  </div>
);

// A small swatch of the theme: backdrop gradient, a panel, and the accent.
const ThemeCard = ({ theme, on, onPick }) => (
  <button
    type="button"
    role="radio"
    aria-checked={on}
    onClick={onPick}
    className={`flex flex-col overflow-hidden rounded-2xl border text-left transition-colors ${on ? 'border-ink ring-2 ring-accent' : 'border-ink/10 hover:border-ink/30'}`}
  >
    <span className="relative block h-20" style={{ background: `linear-gradient(135deg, ${theme.vars['--bg-0']}, ${theme.vars['--bg-2']} 60%, ${theme.vars['--bg-3']})` }}>
      <span className="absolute inset-x-3 bottom-3 top-3 rounded-lg border border-white/15" style={{ background: `rgb(${theme.vars['--panel-rgb']} / 0.55)` }}>
        <span className="absolute left-2 top-2 h-1.5 w-10 rounded-full bg-white/50" />
        <span className="absolute bottom-2 left-2 h-3 w-8 rounded-full" style={{ background: theme.accent }} />
      </span>
      {on && (
        <span className="absolute right-2 top-2 grid size-6 place-items-center rounded-full bg-white text-ink">
          <Check size={14} strokeWidth={3} />
        </span>
      )}
    </span>
    <span className="px-3 py-2.5">
      <span className="text-sm font-semibold">{theme.label}</span>
      <span className="block text-xs text-ink/60">{theme.hint}</span>
    </span>
  </button>
);

// Saved on this device only. Changes show straight away across the whole app.
const readOpeningOn = () => {
  try {
    return localStorage.getItem(OPENING_OFF_KEY) !== '1';
  } catch {
    return true;
  }
};

const AppearanceTab = () => {
  const [look, setLook, reset] = useAppearance();
  const [opening, setOpening] = useState(readOpeningOn);
  const toggleOpening = (on) => {
    try {
      localStorage.setItem(OPENING_OFF_KEY, on ? '0' : '1');
    } catch {
      /* storage blocked: the setting lasts for this visit only */
    }
    setOpening(on);
  };
  const preset = ACCENTS.find((a) => a.hex === look.accent.toLowerCase());
  const isDefault = Object.keys(DEFAULTS).every((k) => look[k] === DEFAULTS[k]);

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-2">
      <section className="card xl:col-span-2">
        <CardTitle
          sub="Sets the background, the panel tint and a matching accent. Pick a different accent below to mix."
          action={
            <button type="button" disabled={isDefault} onClick={reset} className="btn-ghost h-9 px-4 text-sm">
              <RotateCcw size={14} /> Reset all
            </button>
          }
        >
          Theme
        </CardTitle>
        <div role="radiogroup" aria-label="Theme" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
          {THEMES.map((t) => <ThemeCard key={t.id} theme={t} on={look.theme === t.id} onPick={() => setLook({ theme: t.id })} />)}
        </div>
      </section>

      <section className="card xl:col-span-2">
        <CardTitle sub="Buttons, the active page, toggles, sliders and highlights all use this colour.">Accent colour</CardTitle>
        <div role="radiogroup" aria-label="Accent colour" className="flex flex-wrap gap-2">
          {ACCENTS.map((a) => {
            const on = preset?.id === a.id;
            return (
              <button
                key={a.id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setLook({ accent: a.hex })}
                className={`flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3.5 text-sm font-medium transition-colors ${on ? 'border-ink bg-ink/5' : 'border-ink/10 hover:bg-ink/5'}`}
              >
                <span className="grid size-7 place-items-center rounded-full ring-1 ring-ink/10" style={{ background: a.hex }}>
                  {on && <Check size={15} strokeWidth={3} className="text-on-accent" />}
                </span>
                {a.label}
              </button>
            );
          })}
          <ColorPicker value={look.accent} onChange={(accent) => setLook({ accent })} presets={ACCENTS} active={!preset} />
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-2xl bg-ink/5 p-3">
          <span className="text-xs font-medium text-ink/55">Preview</span>
          <span className="btn-primary pointer-events-none">Primary button</span>
          <Toggle checked onChange={() => {}} label="Preview toggle" />
          <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-deep">Highlight</span>
        </div>
      </section>

      <section className="card">
        <CardTitle sub="How see-through the panels and cards are.">Surfaces</CardTitle>
        <Choices name="Surfaces" options={SURFACES} value={look.surface} onChange={(surface) => setLook({ surface })} />
      </section>

      <section className="card">
        <CardTitle sub="What sits behind the glass.">Background</CardTitle>
        <Choices name="Background" options={BACKDROPS} value={look.backdrop} onChange={(backdrop) => setLook({ backdrop })} />
        <div className="mt-3">
          <Row
            title="Reacts to the cursor"
            hint={look.backdrop === 'animated' ? 'The gradient swirls and glows where you move the pointer.' : 'Only works with the moving gradient.'}
            dim={look.backdrop !== 'animated'}
          >
            <Toggle checked={look.reactive} onChange={(reactive) => setLook({ reactive })} label="Background reacts to the cursor" />
          </Row>
        </div>
      </section>

      <section className="card xl:col-span-2">
        <CardTitle sub="Layout and reading comfort.">Display</CardTitle>
        <div className="flex flex-col gap-2">
          <Row title="Density" hint="Compact fits more cards on a laptop screen.">
            <Segments name="Density" options={DENSITIES} value={look.density} onChange={(density) => setLook({ density })} />
          </Row>
          <Row title="Text size" hint="Scales every screen. Large helps on projectors.">
            <Segments name="Text size" options={TEXT_SIZES} value={look.text} onChange={(text) => setLook({ text })} />
          </Row>
          <Row title="Animations" hint="Page transitions, the sliding panels and the moving background. Your system's reduce-motion setting always wins.">
            <Toggle checked={look.motion} onChange={(motion) => setLook({ motion })} label="Animations" />
          </Row>
          <Row title="Opening animation" hint="The RootLens logo builds, finds the fault and opens onto the dashboard. Plays every time the page loads.">
            <span className="flex items-center gap-3">
              <button type="button" onClick={() => dispatchEvent(new Event(REPLAY_EVENT))} className="btn-ghost h-9 px-3 text-sm"><Play size={14} /> Replay</button>
              <Toggle checked={opening} onChange={toggleOpening} label="Opening animation" />
            </span>
          </Row>
        </div>
      </section>
    </div>
  );
};

const DataTab = () => {
  const [cfg, setCfg] = useState(readApiSettings);
  const [check, setCheck] = useState(null); // { busy } | { ok, text }

  const save = (patch) => setCfg(saveApiSettings(patch));
  const test = async () => {
    setCheck({ busy: true });
    try {
      await health();
      setCheck({ ok: true, text: 'The API answered /api/health.' });
    } catch (e) {
      setCheck({ ok: false, text: `No answer from ${cfg.url}. Start it with "make api", or check the address. (${e.message})` });
    }
  };

  return (
    <div className="grid gap-[var(--gap)] xl:grid-cols-2">
      <section className="card">
        <CardTitle sub="Where the FastAPI backend runs. The phone app uploads to the same address.">API</CardTitle>
        <div className="flex flex-col gap-3">
          <Field label="API address" hint={`Default ${API_DEFAULTS.url}. On the demo hotspot use the laptop's IP, for example http://192.168.137.1:8000.`}>
            <input type="url" value={cfg.url} onChange={(e) => save({ url: e.target.value.trim() })} className="field font-mono" spellCheck="false" />
          </Field>
          <Field label="Live panel refresh" hint="How often Captures asks for the newest photo result.">
            <select value={cfg.pollMs} onChange={(e) => save({ pollMs: Number(e.target.value) })} className="field">
              {[1000, 2000, 5000, 10000].map((ms) => <option key={ms} value={ms}>Every {ms / 1000} s</option>)}
            </select>
          </Field>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={test} disabled={check?.busy} className="btn-primary">
              {check?.busy ? <Loader2 size={15} className="animate-spin" /> : <PlugZap size={15} />} Test connection
            </button>
            <button type="button" onClick={() => save(API_DEFAULTS)} className="btn-ghost">Use default</button>
          </div>
          {check && !check.busy && <p role="status" className={`rounded-xl px-3 py-2 text-sm font-medium ${check.ok ? 'bg-good/12' : 'bg-bad/12'}`}>{check.text}</p>}
        </div>
      </section>
      <section className="card">
        <CardTitle sub="Fixed by docs/ML_SPEC.md. Shown here so nobody has to guess.">Analysis settings</CardTitle>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          {[
            ['Split', 'By time: 70% train, 15% validation, 15% test. No shuffling.'],
            ['Model', 'LightGBM with class weights. Baseline: logistic regression.'],
            ['Metrics', 'PR-AUC and MCC with bootstrap CIs. Never accuracy.'],
            ['Stability', '50 bootstrap refits. Stable when in the top 10 at least 70% of the time and above the label-permutation noise floor.'],
            ['Safe window', 'Inside p5 to p95 of observed values. At least 30 runs per bin.'],
          ].map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="font-medium">{k}</dt>
              <dd className="text-ink/70">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
};

const AboutTab = () => (
  <section className="card max-w-3xl">
    <CardTitle sub="From docs/HONESTY_RULES.md. Every screen follows these.">What RootLens claims, and what it does not</CardTitle>
    <ul className="flex flex-col gap-2 text-sm leading-relaxed text-ink/80">
      <li>Rankings show statistically suspected drivers, checked for stability. The data is anonymised and observational, so they show association, not cause.</li>
      <li>Corrective values never leave the range the line has already run (p5 to p95).</li>
      <li>Savings are always a range under stated assumptions, and labelled as a model estimate.</li>
      <li>Anything from the model scoring its own suggestion is labelled model-estimated. The observed inside-versus-outside rate on the test window is the more credible number.</li>
      <li>The phone demo reads a staged process sheet made from real dataset rows. It is not a live factory link.</li>
      <li>A pilot on the real line would confirm the corrections.</li>
    </ul>
  </section>
);

const Settings = () => {
  const [tab, setTab] = useState('Appearance');
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Tabs tabs={TABS} active={tab} onChange={setTab} dark />
      {tab === 'Appearance' && <AppearanceTab />}
      {tab === 'Alerts' && <AlertsTab />}
      {tab === 'Integrations' && <IntegrationsTab />}
      {tab === 'Data' && <DataTab />}
      {tab === 'About' && <AboutTab />}
    </div>
  );
};

export default Settings;

import { useEffect, useRef, useState } from 'react';
import { Bot, CircleCheck, CircleX, LoaderCircle, Microscope, SendHorizontal, User, Wrench } from 'lucide-react';
import { Banner, CardTitle, ChipToggle } from '../components/ui';
import { AiBadge, RichText, asText } from '../components/ai';
import { api, post } from '../lib/api';
import { VoiceInput } from '../components/VoiceInput';
import { FIREBASE, firestore } from '../lib/firebase';
import { useApi } from '../lib/useApi';

const PROVIDERS = [
  { id: 'auto', label: 'Auto' },
  { id: 'groq', label: 'Groq' },
  { id: 'gemini', label: 'Gemini' },
];

const AI_TIMEOUT = 90000; // a full investigation can take 10 to 40 s; asking a question is usually a few seconds

const argText = (args) => {
  if (args === null || args === undefined) return '';
  try {
    const s = typeof args === 'string' ? args : JSON.stringify(args);
    return s === '{}' ? '' : s;
  } catch {
    return '';
  }
};

const errorText = (e) => (e?.name === 'TimeoutError' ? 'The model took too long to answer. Try again, or pick the other provider.' : e?.message || 'Could not reach the API.');

const Trace = ({ trace, label = 'Tools used' }) => {
  if (!trace?.length) return null;
  return (
    <details className="mt-2 text-xs text-ink/65">
      <summary className="cursor-pointer select-none font-medium hover:text-ink">
        <Wrench size={12} className="mr-1 inline" /> {label} ({trace.length})
      </summary>
      <ul className="mt-2 flex flex-col gap-1.5">
        {trace.map((t, i) => (
          <li key={i} className="rounded-xl bg-ink/5 px-3 py-2">
            <p className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-mono font-semibold">{t.tool}</span>
              <span className="tabular text-ink/55">{Math.round(t.ms)} ms</span>
            </p>
            {argText(t.args) && <p className="mt-0.5 break-all font-mono text-ink/60">{argText(t.args)}</p>}
            {t.preview && <p className="mt-1 break-words text-ink/70">{asText(t.preview)}</p>}
          </li>
        ))}
      </ul>
    </details>
  );
};

const Message = ({ m }) => {
  if (m.role === 'user') {
    return (
      <li className="flex items-start justify-end gap-2">
        <p className="max-w-[85%] rounded-2xl rounded-tr-md bg-accent px-3.5 py-2 text-sm text-on-accent">{m.content}</p>
        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-ink/8"><User size={14} /></span>
      </li>
    );
  }
  return (
    <li className="flex items-start gap-2">
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-ink text-white"><Bot size={14} /></span>
      <div className="min-w-0 max-w-[92%] rounded-2xl rounded-tl-md bg-ink/5 px-3.5 py-3">
        {m.error ? (
          <p role="alert" className="text-sm font-medium text-bad">{m.content}</p>
        ) : (
          <>
            <RichText text={m.content} />
            <div className="mt-3">
              <AiBadge grounded={m.grounded} unverified={m.unverified} provider={m.provider} model={m.model} seconds={m.seconds} />
            </div>
            {m.revised && <p className="mt-2 text-xs text-ink/55">The first draft broke a wording rule, so it was rewritten once before showing.</p>}
            <Trace trace={m.trace} />
            {m.sources?.length > 0 && (
              <details className="mt-2 text-xs text-ink/65">
                <summary className="cursor-pointer font-medium">Retrieved context ({m.sources.length})</summary>
                <ul className="mt-1 flex flex-col gap-1">
                  {m.sources.map((s) => {
                    // turns saved by the API (or asked on the phone) keep only the source ids, e.g. "S1"
                    const src = typeof s === 'string' ? { id: s, source: '', text: '' } : s;
                    const text = src.text ?? '';
                    return (
                      <li key={src.id}><span className="font-semibold">[{src.id}]{src.source ? ` ${src.source}:` : ''}</span> {text.length > 220 ? `${text.slice(0, 220)}...` : text}</li>
                    );
                  })}
                </ul>
              </details>
            )}
          </>
        )}
      </div>
    </li>
  );
};

// Also used by the floating assistant (components/AssistantDock.jsx); `pending` asks a question handed over by another screen.
export const Chat = ({ provider = 'auto', pending, compact = false, topic, onAnswer }) => {
  // each topic keeps its own conversation, saved in this browser, so the assistant remembers it
  const memoryKey = `rootlens.ai.chat.${topic?.id ?? 'line'}`;
  const [messages, setMessages] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(memoryKey) || '[]');
    } catch {
      return [];
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(memoryKey, JSON.stringify(messages.slice(-30)));
    } catch {
      // storage full or blocked: the conversation still works for this visit
    }
  }, [messages, memoryKey]);

  // The conversation is shared with the Android app: the API saves every turn, and both clients listen to
  // Firestore chats/{topic}/messages. Server turns win; a local answer keeps its extra detail (trace, badge).
  const topicId = topic && topic.kind !== 'line' ? topic.id : 'line';
  useEffect(() => {
    const merge = (server) => setMessages((cur) => {
      const local = new Map(cur.filter((m) => !m.error).map((m) => [`${m.role}|${m.content}`, m]));
      const errors = cur.filter((m) => m.error);
      return [...server.map((m) => ({ ...m, ...(local.get(`${m.role}|${m.content}`) ?? {}) })), ...errors];
    });
    let closed = false;
    let unsub = () => {};
    api(`/api/ai/chat?topic=${encodeURIComponent(topicId)}`).then((r) => !closed && r.messages?.length && merge(r.messages)).catch(() => {});
    if (FIREBASE) {
      firestore().then(({ db, fs }) => {
        if (closed) return;
        const q = fs.query(fs.collection(db, 'chats', topicId, 'messages'), fs.orderBy('at', 'asc'), fs.limitToLast(60));
        unsub = fs.onSnapshot(q, (snap) => snap.size && merge(snap.docs.map((d) => d.data())));
      });
    }
    return () => {
      closed = true;
      unsub();
    };
  }, [topicId]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const end = useRef(null);
  const runs = useApi('/api/runs?split=test&fails_only=true&limit=200');
  const lastFail = runs.data?.runs?.length ? runs.data.runs[runs.data.runs.length - 1].index : null;

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [messages, busy]);

  const model = topic && topic.kind !== 'line';
  const suggestions = model ? [
    `What is wrong with ${topic.label} and how do we fix it?`,
    'Which defect is the most severe, and which process step causes it?',
    'What should we check on the line first?',
  ] : [
    'What should we fix first and what is it worth?',
    'What is wrong with the latest inspected part and how do we fix it?',
    'How reliable is the model?',
    lastFail === null ? 'Why did a failed run fail?' : `Why did run ${lastFail} fail?`,
    'Which station looks worst on the Bosch line?',
  ];

  const ask = async (question) => {
    const q = question.trim();
    if (!q || busy) return;
    const history = messages.filter((m) => !m.error).slice(-8).map((m) => ({ role: m.role, content: m.content }));
    setMessages((cur) => [...cur, { role: 'user', content: q }]);
    setInput('');
    setBusy(true);
    try {
      const body = { question: q, history, ...(provider === 'auto' ? {} : { provider }), ...(model ? { topic: topic.id } : {}) };
      const r = await post('/api/ai/ask', body, { signal: AbortSignal.timeout(AI_TIMEOUT) });
      onAnswer?.(r);
      setMessages((cur) => [
        ...cur,
        { role: 'assistant', content: r.answer, grounded: r.grounded, unverified: r.unverified_numbers ?? [], trace: r.trace ?? [], sources: r.sources ?? [], provider: r.provider, model: r.model, seconds: r.seconds, revised: r.revised_once },
      ]);
    } catch (e) {
      setMessages((cur) => [...cur, { role: 'assistant', error: true, content: errorText(e) }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (pending?.question) ask(pending.question);
  }, [pending]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section className={compact ? 'flex min-h-0 flex-1 flex-col' : 'card flex flex-col'}>
      {!compact && <CardTitle sub="Answers come from RootLens tool calls. The badge says whether every number in the answer was found in the tool output.">Ask the analyst</CardTitle>}

      {messages.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-ink/15 p-4">
          <p className="text-sm text-ink/70">Start with a question:</p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <li key={s}>
                <button type="button" onClick={() => ask(s)} disabled={busy} className="rounded-full bg-ink/5 px-3.5 py-2 text-left text-sm font-medium text-ink/75 transition-colors hover:bg-ink/10 disabled:opacity-45">
                  {s}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <ul className={`flex flex-col gap-3 overflow-y-auto pr-1 ${compact ? 'min-h-0 flex-1' : 'max-h-[34rem]'}`} aria-live="polite">
          {messages.map((m, i) => <Message key={i} m={m} />)}
          {busy && (
            <li className="flex items-center gap-2 text-sm text-ink/60" role="status">
              <LoaderCircle size={16} className="animate-spin" /> Reading the analysis tools and writing an answer...
            </li>
          )}
          <li ref={end} aria-hidden="true" />
        </ul>
      )}

      {messages.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <li key={s}>
              <button type="button" onClick={() => ask(s)} disabled={busy} className="rounded-full bg-ink/5 px-2.5 py-1 text-xs font-medium text-ink/65 hover:bg-ink/10 disabled:opacity-45">{s}</button>
            </li>
          ))}
        </ul>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
        className="relative mt-4 flex gap-2"
      >
        <label className="min-w-0 flex-1">
          <span className="sr-only">Your question</span>
          <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about the ranking, a safe window, a run or the Bosch line" className="field" maxLength={600} />
        </label>
        <VoiceInput disabled={busy} onText={(t) => ask(t)} />
        <button type="submit" disabled={busy || !input.trim()} className="btn-primary shrink-0">
          {busy ? <LoaderCircle size={16} className="animate-spin" /> : <SendHorizontal size={16} />} Ask
        </button>
        {messages.length > 0 && (
          <button type="button" onClick={() => { setMessages([]); api(`/api/ai/chat?topic=${encodeURIComponent(topicId)}`, { method: 'DELETE' }).catch(() => {}); }} disabled={busy} className="btn-ghost shrink-0" title="Clears this conversation on the dashboard and the phone">Clear</button>
        )}
      </form>
    </section>
  );
};

// ---------------------------------------------------------------- investigation

const ListCard = ({ title, items, sub }) => (
  <section className="card">
    <CardTitle sub={sub}>{title}</CardTitle>
    {items.length ? (
      <ul className="flex flex-col gap-2 text-sm">
        {items.map((it, i) => (
          <li key={i} className="rounded-xl bg-ink/5 px-3 py-2">{it}</li>
        ))}
      </ul>
    ) : (
      <p className="text-sm text-ink/55">Nothing listed.</p>
    )}
  </section>
);

const Brief = ({ r }) => {
  const b = r.brief ?? {};
  const where = (b.where ?? []).map((w) => (typeof w === 'string' ? { item: w } : w));
  const change = (b.what_to_change ?? []).map((w) => (typeof w === 'string' ? { action: w } : w));
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <section className="card">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink/50">Investigation brief</p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight text-balance">{asText(b.headline)}</h2>
          </div>
          <AiBadge grounded={r.grounded} unverified={r.unverified_numbers ?? []} provider={r.provider} model={r.model} seconds={r.seconds} />
        </div>
        {!r.grounded && <p className="mt-3 rounded-xl bg-warn/15 px-3 py-2 text-sm font-medium">Some numbers in this brief were not found in the tool output. Check them against the Ranking and Safe windows pages before using them.</p>}
        <p className="mt-3 text-xs text-ink/60">Statistically suspected, stability-checked. Association in historical data, not proof of cause.</p>
      </section>

      <div className="grid gap-[var(--gap)] lg:grid-cols-2">
        <section className="card">
          <CardTitle sub="Ranked by stability across resamples.">Where it breaks</CardTitle>
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm">
            {where.map((w, i) => (
              <li key={i}>
                <span className="font-semibold">{asText(w.item)}</span>
                {w.evidence && <span className="block text-xs text-ink/65">{asText(w.evidence)}</span>}
              </li>
            ))}
          </ol>
          {!where.length && <p className="text-sm text-ink/55">Nothing listed.</p>}
        </section>

        <section className="card">
          <CardTitle sub="Values stay inside the range the line has run.">What to change</CardTitle>
          <ul className="flex flex-col gap-2 text-sm">
            {change.map((c, i) => (
              <li key={i} className="rounded-xl bg-ink/5 px-3 py-2">
                <p className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-mono font-semibold">{asText(c.parameter)}</span>
                  {c.status && <span className="rounded-full bg-ink/8 px-2 py-0.5 text-[11px] font-semibold text-ink/70">{asText(c.status)}</span>}
                </p>
                <p className="mt-0.5 text-ink/80">{asText(c.action)}</p>
              </li>
            ))}
          </ul>
          {!change.length && <p className="text-sm text-ink/55">Nothing listed.</p>}
        </section>

        <section className="card">
          <CardTitle action={<span className="rounded-full bg-warn/15 px-2 py-0.5 text-[11px] font-semibold text-warn">model estimate</span>}>How much it saves</CardTitle>
          <p className="text-sm leading-relaxed">{asText(b.how_much)}</p>
        </section>

        <ListCard title="How reliable is this" items={(b.reliability ?? []).map(asText)} />
      </div>

      <ListCard title="Next actions" sub="What to do before trusting any of this on the line." items={(b.next_actions ?? []).map(asText)} />

      <section className="card">
        <CardTitle sub="The tool calls the brief was written from, with how long each took.">Step trail</CardTitle>
        <ol className="flex flex-col gap-1.5 text-sm">
          {(r.steps ?? []).map((s, i) => (
            <li key={i} className="grid grid-cols-[1.25rem_1fr_auto] items-start gap-2 rounded-xl bg-ink/5 px-3 py-2">
              {s.ok ? <CircleCheck size={16} className="mt-0.5 text-good" /> : <CircleX size={16} className="mt-0.5 text-bad" />}
              <span className="min-w-0">
                <span className="font-mono font-semibold">{s.step}</span>
                {argText(s.args) && <span className="block break-all font-mono text-xs text-ink/55">{argText(s.args)}</span>}
              </span>
              <span className="tabular text-xs text-ink/60">{Math.round(s.ms)} ms</span>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
};

const Investigate = ({ provider }) => {
  const [volume, setVolume] = useState(1000);
  const [scrap, setScrap] = useState(500);
  const [state, setState] = useState({ busy: false, data: null, error: null });
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!state.busy) return undefined;
    const start = Date.now();
    setElapsed(0);
    const t = setInterval(() => setElapsed((Date.now() - start) / 1000), 250);
    return () => clearInterval(t);
  }, [state.busy]);

  const run = async () => {
    setState({ busy: true, data: null, error: null });
    try {
      const data = await post('/api/ai/investigate', { volume_per_day: volume, scrap_cost_per_part: scrap, ...(provider === 'auto' ? {} : { provider }) }, { signal: AbortSignal.timeout(AI_TIMEOUT * 2) });
      setState({ busy: false, data, error: null });
    } catch (e) {
      setState({ busy: false, data: null, error: errorText(e) });
    }
  };

  return (
    <>
      <section className="card" aria-busy={state.busy}>
        <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold"><Microscope size={20} className="text-accent-deep" /> Run full investigation</h2>
            <p className="mt-1 max-w-xl text-sm text-ink/65">
              The analyst calls the ranking, safe-window, savings and reliability tools in turn and writes one brief: where it breaks, what to change, how much it is worth. It takes 10 to 40 seconds.
            </p>
            <button type="button" onClick={run} disabled={state.busy} className="btn-primary mt-4 h-12 px-6 text-base">
              {state.busy ? <LoaderCircle size={18} className="animate-spin" /> : <Microscope size={18} />}
              {state.busy ? `Investigating... ${elapsed.toFixed(0)} s` : 'Run full investigation'}
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">Parts per day</span>
              <input type="number" min={1} step={100} value={volume} onChange={(e) => setVolume(Math.max(1, Number(e.target.value) || 1))} className="field tabular" disabled={state.busy} />
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">Scrap cost per part (Rs)</span>
              <input type="number" min={0} step={50} value={scrap} onChange={(e) => setScrap(Math.max(0, Number(e.target.value) || 0))} className="field tabular" disabled={state.busy} />
            </label>
            <p className="col-span-2 text-xs text-ink/55">Used for the savings range only. Provider: {PROVIDERS.find((p) => p.id === provider)?.label}.</p>
          </div>
        </div>
        {state.busy && (
          <p role="status" className="mt-4 flex items-center gap-2 rounded-xl bg-ink/5 px-3 py-2 text-sm text-ink/70">
            <LoaderCircle size={15} className="shrink-0 animate-spin" /> Calling the analysis tools, then writing and checking the brief. The step trail appears when it finishes.
          </p>
        )}
        {state.error && <p role="alert" className="mt-4 rounded-xl bg-bad/12 px-3 py-2 text-sm font-medium">The investigation failed: {state.error}</p>}
      </section>
      {state.data && <Brief r={state.data} />}
    </>
  );
};

const Analyst = () => {
  const [provider, setProvider] = useState('auto');
  const status = useApi('/api/ai/status');
  const st = status.data;
  const providerNote = st
    ? ['groq', 'gemini'].map((k) => `${k}: ${st.providers?.[k] ? st.models?.[k] ?? 'ready' : 'no key'}`).join(', ')
    : 'Auto tries one provider and falls back to the other.';
  return (
    <div className="flex flex-col gap-[var(--gap)]">
      <Banner tone="info">
        The analyst writes text from RootLens tool output; it does not read the anonymised features, so it never says what a feature physically measures. Savings are always a range and a model estimate.
      </Banner>
      {status.error && <Banner tone="warn">The AI service did not answer ({status.error.message}). Questions and the investigation will fail until it does.</Banner>}
      <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-black/25 px-4 py-3 ring-1 ring-white/10">
        <span className="text-sm font-medium text-white/80">Model provider</span>
        <div className="rounded-full bg-white/90 p-1 text-ink"><ChipToggle multiple={false} value={provider} onChange={setProvider} options={PROVIDERS} /></div>
        <span className="text-xs text-white/60">{providerNote}</span>
      </div>
      <Investigate provider={provider} />
      <Chat provider={provider} />
    </div>
  );
};

export default Analyst;

import { useEffect, useState } from 'react';
import ErrorBoundary from './ErrorBoundary';
import { AnimatePresence, motion } from 'framer-motion';
import { Activity, Bot, ChevronDown, Layers, LoaderCircle, Maximize2, X } from 'lucide-react';
import { Chat } from '../pages/Analyst';
import { navigate } from '../lib/router';
import { api, post } from '../lib/api';

// The AI assistant side panel, opened from the bottom bar. On top: "Context" (what Groq and Gemini are working
// with right now) and "Topic" (a saved model the conversation is about; each topic keeps its own chat history).
// Other screens open it with a question: askAssistant('question').
export const ASK_EVENT = 'rootlens:ask';
export const OPEN_EVENT = 'rootlens:open-assistant';
export const STATE_EVENT = 'rootlens:assistant-state';
export const askAssistant = (question) => dispatchEvent(new CustomEvent(ASK_EVENT, { detail: question }));
export const openAssistant = () => dispatchEvent(new Event(OPEN_EVENT));
const TOPIC_KEY = 'rootlens.ai.topic';
const LINE = { id: 'line', label: 'Line analysis (SECOM)', kind: 'line' };

const readTopic = () => {
  try {
    return JSON.parse(localStorage.getItem(TOPIC_KEY) || 'null') || LINE;
  } catch {
    return LINE;
  }
};

const Row = ({ k, v }) => (
  <div className="flex items-baseline justify-between gap-3 py-0.5">
    <dt className="shrink-0 text-white/55">{k}</dt>
    <dd className="tabular truncate text-right font-medium text-white/90">{v}</dd>
  </div>
);

// Live view of the model context: providers and models, then what the last answer used.
const ContextPanel = ({ status, last, topic, open, onToggle }) => (
  <section className="rounded-2xl bg-white/5 ring-1 ring-white/10">
    <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold">
      <Activity size={15} className="text-accent" /> Context
      <span className="ml-auto flex items-center gap-2 text-xs font-normal text-white/60">
        {['groq', 'gemini'].map((p) => (
          <span key={p} className="flex items-center gap-1">
            <span className={`size-1.5 rounded-full ${status?.providers?.[p] ? 'bg-good' : 'bg-white/30'}`} />{p === 'groq' ? 'Groq' : 'Gemini'}
          </span>
        ))}
        <ChevronDown size={14} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </span>
    </button>
    {open && (
      <dl className="border-t border-white/10 px-3 py-2 text-xs">
        {['groq', 'gemini'].map((p) => (
          <Row
            key={p}
            k={p === 'groq' ? 'Groq' : 'Gemini'}
            v={status?.providers?.[p] ? `${status.models?.[p] ?? 'ready'} · ${status.keys?.[p] ?? 0} key${status.keys?.[p] === 1 ? '' : 's'}` : status ? 'no key' : '...'}
          />
        ))}
        <Row k="Fallback order" v={(status?.chains?.text ?? []).map((s) => s.provider).join(' → ') || '...'} />
        <Row k="Topic in context" v={topic.label} />
        {last ? (
          <>
            <div className="my-1.5 border-t border-white/10" />
            <Row k="Last answer by" v={`${last.provider ?? '-'} · ${last.model ?? ''}`} />
            <Row k="Model calls" v={last.context?.calls ?? '-'} />
            <Row k="Tokens in / out" v={`${last.context?.input_tokens ?? 0} / ${last.context?.output_tokens ?? 0}`} />
            <Row k="Retrieved passages" v={`${last.context?.retrieved ?? 0} (${last.context?.retrieved_chars ?? 0} chars)`} />
            <Row k="Topic context" v={`${last.context?.topic_chars ?? 0} chars`} />
            <Row k="Earlier turns sent" v={last.context?.history_turns ?? 0} />
            <Row k="Tools called" v={(last.trace ?? []).map((t) => t.tool).join(', ') || 'none'} />
            <Row k="Time" v={`${last.seconds ?? '-'} s`} />
            {last.sources?.length > 0 && (
              <p className="mt-1 truncate text-white/55" title={last.sources.map((s) => s.source).join(', ')}>
                Sources: {last.sources.map((s) => `[${s.id}] ${s.source}`).join(', ')}
              </p>
            )}
          </>
        ) : (
          <p className="mt-1 text-white/50">Ask something to see what the model receives.</p>
        )}
      </dl>
    )}
  </section>
);

// Pick what the conversation is about. A sample that is not loaded yet is loaded first.
const TopicPicker = ({ topic, onPick }) => {
  const [open, setOpen] = useState(false);
  const [list, setList] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (open && !list) api('/api/ai/topics', { signal: AbortSignal.timeout(60000) }).then((r) => setList(r.topics)).catch(() => setList([]));
  }, [open, list]);
  const pick = async (t) => {
    let chosen = t;
    setError('');
    if (!t.id && t.sample) {
      setBusy(true);
      try {
        const m = await post('/api/assembly/samples/load', { name: t.sample }, { signal: AbortSignal.timeout(180000) });
        chosen = { id: m.id, label: m.label, kind: 'model', damaged: m.counts?.damaged_parts };
      } catch (e) {
        setError(`Could not load ${t.label}: ${e.message}`);
        setBusy(false);
        return;
      }
      setBusy(false);
    }
    onPick(chosen);
    setOpen(false);
    setList(null);
  };
  return (
    <section className="relative rounded-2xl bg-white/5 ring-1 ring-white/10">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="listbox" className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-semibold">
        <Layers size={15} className="text-accent" /> Topic
        <span className="ml-auto max-w-[60%] truncate text-xs font-normal text-white/75">{topic.label}</span>
        {busy ? <LoaderCircle size={14} className="animate-spin" /> : <ChevronDown size={14} className={`transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>
      {error && <p className="px-3 pb-2 text-xs text-bad">{error}</p>}
      {open && (
        <ul role="listbox" className="absolute inset-x-0 top-full z-10 mt-1 max-h-72 overflow-y-auto popover p-1.5 text-sm">
          {!list && <li className="px-3 py-2 text-white/60">Loading...</li>}
          {list?.map((t) => (
            <li key={t.id ?? t.sample}>
              <button
                type="button"
                role="option"
                aria-selected={t.id === topic.id}
                onClick={() => pick(t)}
                className={`flex w-full items-center justify-between gap-2 rounded-xl px-3 py-2 text-left hover:bg-white/10 ${t.id === topic.id ? 'bg-accent/20' : ''}`}
              >
                <span className="truncate">{t.label}</span>
                <span className="shrink-0 text-xs text-white/50">
                  {t.kind === 'line' ? 'analysis' : t.kind === 'sample' ? 'load sample' : `${t.damaged ?? 0} damaged`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};

const AssistantDock = () => {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(null);
  const [topic, setTopic] = useState(readTopic);
  const [status, setStatus] = useState(null);
  const [last, setLast] = useState(null);
  const [ctxOpen, setCtxOpen] = useState(true);

  useEffect(() => {
    const onAsk = (e) => {
      setOpen(true);
      setPending({ question: e.detail, at: Date.now() });
    };
    const onOpen = () => setOpen(true);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    addEventListener(ASK_EVENT, onAsk);
    addEventListener(OPEN_EVENT, onOpen);
    addEventListener('keydown', onKey);
    return () => {
      removeEventListener(ASK_EVENT, onAsk);
      removeEventListener(OPEN_EVENT, onOpen);
      removeEventListener('keydown', onKey);
    };
  }, []);
  useEffect(() => {
    dispatchEvent(new CustomEvent(STATE_EVENT, { detail: open }));
  }, [open]);
  // provider status refreshes while the panel is open
  useEffect(() => {
    if (!open) return undefined;
    const load = () => api('/api/ai/status', { signal: AbortSignal.timeout(60000) }).then(setStatus).catch(() => {});
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [open]);

  const pickTopic = (t) => {
    setTopic(t);
    setLast(null);
    try {
      localStorage.setItem(TOPIC_KEY, JSON.stringify(t));
    } catch {
      // storage blocked: the topic holds for this visit
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[70]" role="dialog" aria-modal="true" aria-label="AI assistant">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)} className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 360, damping: 38 }}
            className="absolute inset-y-0 right-0 flex w-[min(34rem,100vw)] flex-col p-3"
          >
            <div className="glass-panel flex min-h-0 flex-1 flex-col gap-2 rounded-3xl p-4">
              <div className="flex items-center gap-2">
                <span className="grid size-9 place-items-center rounded-xl bg-accent text-on-accent"><Bot size={18} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block font-semibold">AI assistant</span>
                  <span className="block text-xs text-white/60">Answers from the RootLens analysis, with what to do next. Every number is checked.</span>
                </span>
                <button type="button" onClick={() => { setOpen(false); navigate('analyst'); }} className="grid size-9 place-items-center rounded-xl text-white/70 hover:bg-white/10" aria-label="Open the full analyst with the investigation report" title="Full analyst and investigation">
                  <Maximize2 size={16} />
                </button>
                <button type="button" onClick={() => setOpen(false)} className="grid size-9 place-items-center rounded-xl text-white/70 hover:bg-white/10" aria-label="Close the assistant">
                  <X size={18} />
                </button>
              </div>
              <ContextPanel status={status} last={last} topic={topic} open={ctxOpen} onToggle={() => setCtxOpen((o) => !o)} />
              <TopicPicker topic={topic} onPick={pickTopic} />
              <div className="flex min-h-0 flex-1 flex-col rounded-2xl bg-white/90 p-3 text-ink">
                <ErrorBoundary what="The conversation">
                  <Chat key={topic.id} compact pending={pending} topic={topic} onAnswer={setLast} />
                </ErrorBoundary>
              </div>
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  );
};

export default AssistantDock;

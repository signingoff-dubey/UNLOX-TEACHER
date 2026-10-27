import { Fragment } from 'react';
import { ShieldCheck, TriangleAlert, Cpu, Timer } from 'lucide-react';

// Every AI-written block carries this badge: were its numbers found in the tool output, which model wrote it, how long it took.
// `seconds` is a number, or {tools, total} from the investigation endpoint.
export const AiBadge = ({ grounded, unverified = [], provider, model, seconds }) => {
  const total = typeof seconds === 'object' && seconds !== null ? seconds.total : seconds;
  const tools = typeof seconds === 'object' && seconds !== null ? seconds.tools : undefined;
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-semibold">
      {grounded ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-good/12 px-2 py-0.5 text-good">
          <ShieldCheck size={12} /> numbers verified
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 rounded-full bg-warn/15 px-2 py-0.5 text-warn">
          <TriangleAlert size={12} /> unverified numbers{unverified.length ? `: ${unverified.join(', ')}` : ''}
        </span>
      )}
      {(provider || model) && (
        <span className="inline-flex items-center gap-1 rounded-full bg-ink/8 px-2 py-0.5 text-ink/70">
          <Cpu size={12} /> {[provider, model].filter(Boolean).join(' / ')}
        </span>
      )}
      {typeof total === 'number' && (
        <span className="tabular inline-flex items-center gap-1 rounded-full bg-ink/8 px-2 py-0.5 text-ink/70">
          <Timer size={12} /> {total.toFixed(1)} s{typeof tools === 'number' ? ` (tools ${tools.toFixed(1)} s)` : ''}
        </span>
      )}
    </div>
  );
};

// Bold and inline code inside one line of model text. Everything else is plain text, so nothing from the model is ever injected as HTML.
const inline = (text) =>
  text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i} className="rounded bg-ink/8 px-1 font-mono text-[0.9em]">{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });

// The answer text is markdown-ish: paragraphs, "- " bullets, "1. " lists, "#" headings, **bold**.
export const RichText = ({ text }) => {
  const blocks = [];
  let list = null;
  for (const raw of String(text ?? '').split('\n')) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const kind = bullet ? 'ul' : 'ol';
      if (!list || list.kind !== kind) {
        list = { kind, items: [] };
        blocks.push(list);
      }
      list.items.push((bullet ?? numbered)[1]);
      continue;
    }
    list = null;
    if (!line.trim()) continue;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push(heading ? { kind: 'h', text: heading[1] } : { kind: 'p', text: line });
  }
  return (
    <div className="flex flex-col gap-2 text-sm leading-relaxed">
      {blocks.map((b, i) => {
        if (b.kind === 'h') return <h4 key={i} className="mt-1 font-semibold">{inline(b.text)}</h4>;
        if (b.kind === 'p') return <p key={i}>{inline(b.text)}</p>;
        const Tag = b.kind;
        return (
          <Tag key={i} className={`flex flex-col gap-1 pl-5 ${b.kind === 'ul' ? 'list-disc' : 'list-decimal'}`}>
            {b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}
          </Tag>
        );
      })}
    </div>
  );
};

// Text the model may return as a string, an object or a list; always renders something readable.
export const asText = (v) => {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number') return String(v);
  if (Array.isArray(v)) return v.map(asText).join('; ');
  return v.text ?? v.item ?? v.action ?? Object.values(v).map(asText).join(' ');
};

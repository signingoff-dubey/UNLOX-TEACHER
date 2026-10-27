import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion, useSpring } from 'framer-motion';
import { createPortal } from 'react-dom';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';

export const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

const LIVE_LEGEND = [['bg-white', 'Today'], ['bg-info', 'Activity'], ['bg-rose', 'Needs attention']];

// What happened on each date in this app (captures, scan inspections, model uploads).
// One model feeds the date colours, the legend and the day's event list, so they can never disagree.
const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

export const useLiveDayModel = (activity, today) =>
  useMemo(() => {
    const byDate = Object.fromEntries((activity?.days ?? []).map((d) => [d.date, d]));
    const todayIso = iso(today);
    const info = (d) => {
      const items = [];
      if (d === todayIso) items.push({ text: 'Today', tone: 'accent' });
      const row = byDate[d];
      if (!row) return items;
      if (row.runs) items.push({ text: `${plural(row.runs, 'run')}, ${row.fails} failed (replayed SECOM)`, tone: row.fails / row.runs >= 0.1 ? 'rose' : 'good' });
      if (row.capture) items.push({ text: plural(row.capture, 'capture'), tone: 'good' });
      if (row.inspection) items.push({ text: plural(row.inspection, 'scan inspection'), tone: 'info' });
      if (row.assembly) items.push({ text: plural(row.assembly, 'model upload'), tone: 'info' });
      if (row.alerts) items.push({ text: `${plural(row.alerts, 'item')} needing attention`, tone: 'rose' });
      for (const e of row.events.slice(0, 4)) items.push({ text: `${e.at.slice(11, 16)} ${e.title}`, tone: e.tone });
      return items;
    };
    const style = (d) => {
      const row = byDate[d];
      if (d === todayIso) return row ? 'bg-white text-ink font-semibold ring-2 ring-accent' : 'bg-white text-ink font-semibold';
      // red: something needs attention, or a production day failing at 10% or more (about 1.5x the usual rate)
      if (row?.alerts || (row?.runs && row.fails / row.runs >= 0.1)) return 'bg-rose text-white font-semibold';
      if (row) return 'bg-info/80 text-white font-semibold';
      return 'text-white/75 hover:bg-white/10';
    };
    return { info, style, legend: LIVE_LEGEND };
  }, [activity, today]);

// Dots on the dark panel: today is white here, as on the calendar itself.
const DOT = { accent: 'bg-white', good: 'bg-good', rose: 'bg-rose', info: 'bg-info' };

// Quick enough to keep up with the pointer, damped enough not to wobble.
const GLIDE = { stiffness: 700, damping: 42, mass: 0.5 };
const EASE = [0.4, 0, 0.2, 1];

// Pointing at a date moves the lens there. Each date's hit area is its whole cell, and only leaving the
// whole grid (or list) lets go, so the gaps between dates never count as leaving.
const useHover = () => {
  const [hover, setHover] = useState(null);
  const enter = (date) => ({ onMouseEnter: () => setHover(date), onFocus: () => setHover(date), onBlur: () => setHover(null) });
  const leave = { onMouseLeave: () => setHover(null) };
  return { hover, enter, leave };
};

// The lens sits on the date pointed at, and goes straight back to today once the pointer leaves the dates.
// No delay is needed: hover only clears on leaving the whole grid, never in the gaps between dates.
const lensDate = (hover) => hover ?? iso(new Date());

// Collapsed rail only: the rail has no room for the day's events, so pointing at a date shows them in a card
// beside it. Fixed-position in <body>, since the glass panel scrolls and has a backdrop filter that would clip it.
// It stays mounted while the pointer moves down the rail and glides to the next date instead of popping.
const CARD_W = 248;

const DayCard = ({ anchor, date, items }) => {
  const r = anchor.getBoundingClientRect();
  const left = Math.max(8, r.left - CARD_W - 10);
  const top = Math.min(Math.max(8, r.top - 12), window.innerHeight - 180);
  return (
    <motion.div
      role="tooltip"
      id="day-card"
      style={{ position: 'fixed', left: 0, top: 0, width: CARD_W, transformOrigin: 'right center' }}
      initial={{ opacity: 0, scale: 0.94, x: left + 8, y: top }}
      animate={{ opacity: 1, scale: 1, x: left, y: top }}
      exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.12 } }}
      transition={{ type: 'spring', ...GLIDE, opacity: { duration: 0.14 } }}
      className="popover pointer-events-none z-[70] p-3.5"
    >
      <p className="text-sm font-semibold">{longDate(date)}</p>
      {items.length === 0 ? (
        <p className="mt-1.5 text-sm text-white/55">No runs recorded.</p>
      ) : (
        <ul className="mt-1.5 flex flex-col gap-1.5">
          {items.map((it, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span className={`mt-1.5 size-2 shrink-0 rounded-full ${it.tone === 'accent' ? 'bg-white' : DOT[it.tone]}`} />
              {it.text}
            </li>
          ))}
        </ul>
      )}
    </motion.div>
  );
};

// The card lingers a moment after the pointer leaves, so it fades out instead of vanishing.
const useDayCard = (hover, container) => {
  const [card, setCard] = useState(null);
  useEffect(() => {
    if (hover) {
      const el = container.current?.querySelector(`[data-dot="${hover}"]`);
      if (el) setCard({ date: hover, el });
      return undefined;
    }
    const t = setTimeout(() => setCard(null), 120);
    return () => clearTimeout(t);
  }, [hover, container]);
  return card;
};

// Where `el` sits inside `parent`, scroll included. Measured from rects, so transforms on shared ancestors cancel out.
const offsetIn = (el, parent) => {
  const r = el.getBoundingClientRect();
  const p = parent.getBoundingClientRect();
  return [r.left - p.left - parent.clientLeft + parent.scrollLeft, r.top - p.top - parent.clientTop + parent.scrollTop];
};

// One glass lens per calendar that springs between dates. It is never remounted, so moving fast across the
// dates costs only a transform per frame. It sits above the date colours (z-1) and below the numbers (z-2).
const Lens = ({ at, watch }) => {
  const self = useRef(null);
  const x = useSpring(0, GLIDE);
  const y = useSpring(0, GLIDE);
  const placed = useRef(false);
  const [shown, setShown] = useState(false);
  useLayoutEffect(() => {
    // The parent, not a ref passed down: the parent's ref is not attached yet when this first runs.
    const parent = self.current?.parentElement;
    const el = parent?.querySelector(`[data-dot="${at}"]`);
    if (!el) {
      placed.current = false;
      setShown(false);
      return;
    }
    const [ox, oy] = offsetIn(el, parent);
    if (placed.current) {
      x.set(ox - 4);
      y.set(oy - 4);
    } else {
      x.jump(ox - 4);
      y.jump(oy - 4);
      placed.current = true;
    }
    setShown(true);
  }, [at, watch, x, y]);
  return (
    <motion.span
      ref={self}
      aria-hidden="true"
      className="liquid-lens pointer-events-none absolute left-0 top-0 z-[1] size-9 rounded-full"
      style={{ x, y }}
      initial={false}
      animate={{ opacity: shown ? 1 : 0, scale: shown ? 1 : 0.6 }}
      transition={{ duration: 0.16, ease: 'easeOut' }}
    />
  );
};

// A date: the button fills its whole cell (the hit area), the coloured dot inside carries the number,
// and the picked date gets an accent ring.
const Day = ({ date, model, picked, onPick, enter, label, className }) => {
  const d = iso(date);
  const isPicked = picked === d;
  return (
    <button
      type="button"
      data-today={d === iso(new Date())}
      onClick={() => onPick(isPicked ? null : d)}
      aria-pressed={isPicked}
      aria-label={label}
      {...enter(d)}
      className={`grid place-items-center rounded-lg ${className}`}
    >
      <span data-dot={d} className={`relative grid size-7 place-items-center rounded-full transition-colors ${model.style(d)}`}>
        <AnimatePresence>
          {isPicked && (
            <motion.span
              aria-hidden="true"
              initial={{ opacity: 0, scale: 1.5 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.7, transition: { duration: 0.12 } }}
              transition={{ type: 'spring', stiffness: 520, damping: 30 }}
              className="absolute -inset-[4px] z-[2] rounded-full border-2 border-accent"
            />
          )}
        </AnimatePresence>
        <span className="relative z-[2]">{date.getDate()}</span>
      </span>
    </button>
  );
};

const longDate = (d) => new Date(`${d}T00:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });

// What is on the picked date, under the calendar. Opens and closes by height; switching dates crossfades.
const DayDetails = ({ date, items, onClose }) => (
  <motion.section
    aria-live="polite"
    initial={{ opacity: 0, height: 0 }}
    animate={{ opacity: 1, height: 'auto' }}
    exit={{ opacity: 0, height: 0 }}
    transition={{ duration: 0.28, ease: EASE }}
    className="overflow-hidden"
  >
    <div className="mt-3 rounded-2xl bg-black/20 p-3.5">
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={date}
          initial={{ opacity: 0, y: 6, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -4, filter: 'blur(4px)' }}
          transition={{ duration: 0.16, ease: EASE }}
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-semibold">{longDate(date)}</p>
            <button type="button" onClick={onClose} aria-label="Close the day" className="-mr-1 -mt-1 grid size-7 shrink-0 place-items-center rounded-full text-white/55 transition-colors hover:bg-white/10 hover:text-white">
              <X size={14} />
            </button>
          </div>
          {items.length === 0 ? (
            <p className="mt-1.5 text-sm text-white/55">No runs recorded.</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-1.5">
              {items.map((it, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.04 * i, duration: 0.18, ease: EASE }}
                  className="flex items-start gap-2 text-sm text-white/85"
                >
                  <span className={`mt-1.5 size-2 shrink-0 rounded-full ${DOT[it.tone]}`} />
                  {it.text}
                </motion.li>
              ))}
            </ul>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  </motion.section>
);

export const Calendar = ({ model, picked = null, onPick = () => {}, start = new Date() }) => {
  const [month, setMonth] = useState(new Date(start.getFullYear(), start.getMonth(), 1));
  const [dir, setDir] = useState(0);
  const { hover, enter, leave } = useHover();
  const at = lensDate(hover);
  const firstWeekday = month.getDay();
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells = [...Array(firstWeekday).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1))];
  const shift = (delta) => {
    setDir(delta);
    setMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1));
  };
  return (
    <div>
      <div className="liquid-well rounded-2xl p-4">
        <div className="flex items-center justify-between">
          <p className="font-semibold">{month.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}</p>
          <div className="flex gap-1">
            <button type="button" onClick={() => shift(-1)} aria-label="Previous month" className="grid size-7 place-items-center rounded-full bg-white/10 text-white/70 hover:text-white"><ChevronLeft size={14} /></button>
            <button type="button" onClick={() => shift(1)} aria-label="Next month" className="grid size-7 place-items-center rounded-full bg-white/10 text-white/70 hover:text-white"><ChevronRight size={14} /></button>
          </div>
        </div>
        <div className="mt-3 grid grid-cols-7 text-center text-xs">
          {WEEKDAYS.map((d) => <span key={d} className="pb-1 text-white/40">{d}</span>)}
        </div>
        <motion.div
          key={iso(month)}
          {...leave}
          initial={dir ? { opacity: 0, x: dir * 28, filter: 'blur(6px)' } : false}
          animate={{ opacity: 1, x: 0, filter: 'blur(0px)', transitionEnd: { filter: 'none' } }}
          transition={{ type: 'spring', stiffness: 320, damping: 30 }}
          className="relative grid grid-cols-7 text-center text-xs"
        >
          <Lens at={at} watch={iso(month)} />
          {cells.map((date, i) =>
            date ? (
              <Day
                key={i}
                date={date}
                model={model}
                picked={picked}
                onPick={onPick}
                enter={enter}
                label={date.toLocaleDateString('en-IN', { day: 'numeric', month: 'long' })}
                className="h-8 w-full"
              />
            ) : (
              <span key={i} />
            )
          )}
        </motion.div>
        <ul className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-white/55">
          {(model.legend ?? LIVE_LEGEND).map(([cls, label]) => (
            <li key={label} className="flex items-center gap-1.5"><span className={`size-2 rounded-full ${cls}`} />{label}</li>
          ))}
        </ul>
      </div>
      <AnimatePresence initial={false}>
        {picked && <DayDetails key="details" date={picked} items={model.info(picked)} onClose={() => onPick(null)} />}
      </AnimatePresence>
    </div>
  );
};

// The collapsed form: one long bar with every day of the month, marked the same way as the full calendar.
// Pointing at a date shows its events in a card; clicking one opens the panel with that date picked.
export const DateRail = ({ model, picked = null, onPick = () => {}, start = new Date() }) => {
  const [month, setMonth] = useState(new Date(start.getFullYear(), start.getMonth(), 1));
  const { hover, enter, leave } = useHover();
  const at = lensDate(hover);
  const scroller = useRef(null);
  const card = useDayCard(hover, scroller);
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const days = Array.from({ length: daysInMonth }, (_, i) => new Date(month.getFullYear(), month.getMonth(), i + 1));
  const shift = (delta) => setMonth(new Date(month.getFullYear(), month.getMonth() + delta, 1));
  useEffect(() => {
    // Keep today (or the first day of another month) in view on short screens.
    const target = scroller.current?.querySelector('[data-today="true"]') ?? scroller.current?.querySelector('button');
    target?.scrollIntoView?.({ block: 'center' });
  }, [month]);
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center gap-1" aria-label={month.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })} role="group">
      <button type="button" onClick={() => shift(-1)} aria-label="Previous month" className="grid size-7 shrink-0 place-items-center rounded-full bg-white/10 text-white/70 hover:text-white"><ChevronLeft size={13} className="rotate-90" /></button>
      <p className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-white/50">{month.toLocaleDateString('en-IN', { month: 'short' })}</p>
      <div ref={scroller} {...leave} className="relative flex min-h-0 w-full flex-1 flex-col items-center overflow-y-auto p-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <Lens at={at} watch={iso(month)} />
        {days.map((date) => {
          const d = iso(date);
          const marked = model.info(d).length > 0;
          return (
            <Day
              key={d}
              date={date}
              model={model}
              picked={picked}
              onPick={(v) => onPick(v ?? d)}
              enter={enter}
              label={`${date.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}${marked ? ', has runs' : ''}`}
              className="h-[30px] w-full shrink-0 text-[11px]"
            />
          );
        })}
      </div>
      <button type="button" onClick={() => shift(1)} aria-label="Next month" className="grid size-7 shrink-0 place-items-center rounded-full bg-white/10 text-white/70 hover:text-white"><ChevronRight size={13} className="rotate-90" /></button>
      {createPortal(
        <AnimatePresence>{card && <DayCard key="day-card" anchor={card.el} date={card.date} items={model.info(card.date)} />}</AnimatePresence>,
        document.body
      )}
    </div>
  );
};

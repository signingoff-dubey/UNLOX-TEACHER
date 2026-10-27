import { useEffect, useState } from 'react';

// Opening or closing the panel changes the main column's width, so its text re-wraps and the page would slide
// under the reader. Pin whatever is at the top of the view to the same spot until the width animation ends.
const keepReadingPosition = (ms = 420) => {
  const main = document.querySelector('main');
  if (!main) return;
  const box = main.getBoundingClientRect();
  const probe = document.elementFromPoint(box.left + box.width / 2, box.top + 96);
  const anchor = probe && main.contains(probe) ? probe : null;
  if (!anchor) return;
  const top = anchor.getBoundingClientRect().top;
  const end = performance.now() + ms;
  const step = () => {
    if (!anchor.isConnected) return;
    const drift = anchor.getBoundingClientRect().top - top;
    if (Math.abs(drift) > 0.5) main.scrollTop += drift;
    if (performance.now() < end) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
};
import { motion, AnimatePresence } from 'framer-motion';
import { Box, Camera, PanelRightClose, PanelRightOpen, ScanSearch, X } from 'lucide-react';
import { Calendar, DateRail, useLiveDayModel } from './CalendarParts';
import { useApi } from '../../lib/useApi';
import { useActivity, useToday } from '../../lib/useActivity';
import { DATASET } from '../../lib/dataset';

const Profile = ({ overview }) => {
  const d = overview?.data;
  const stats = [
    { value: d ? d.rows.toLocaleString('en-IN') : '-', label: 'Runs' },
    { value: d ? d.fails : '-', label: 'Fails' },
    { value: d ? d.features : '-', label: 'Features' },
  ];
  return (
    <div>
      <div className="flex items-center gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-full bg-accent font-semibold text-on-accent">{DATASET.name.slice(0, 2)}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{DATASET.name}</p>
          <p className="truncate text-xs text-white/55">{DATASET.line}</p>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-3 divide-x divide-white/10 rounded-2xl bg-black/20 py-3 text-center">
        {stats.map((s) => (
          <div key={s.label}>
            <dd className="tabular text-lg font-semibold">{s.value}</dd>
            <dt className="text-xs text-white/55">{s.label}</dt>
          </div>
        ))}
      </dl>
    </div>
  );
};

// The latest captures, scan inspections and model uploads, pushed by the server as they happen.
const TONE = { rose: 'bg-bad/20 text-bad', good: 'bg-good/20 text-good', info: 'bg-info/20 text-info' };
const KIND_ICON = { capture: Camera, inspection: ScanSearch, assembly: Box };

const RecentActivity = ({ activity }) => {
  const recent = activity.data?.recent ?? [];
  return (
    <section>
      <h2 className="font-semibold">Recent activity</h2>
      {!activity.data && !activity.error && <p className="mt-3 text-xs text-white/55">Connecting...</p>}
      {activity.error && !activity.data && <p className="mt-3 text-xs text-white/55">Could not reach the API.</p>}
      {activity.data && recent.length === 0 && (
        <p className="mt-3 text-xs text-white/55">Nothing yet. Captures, scans and model uploads appear here as they happen.</p>
      )}
      <ul className="mt-3 flex flex-col gap-2">
        {recent.slice(0, 4).map((e) => (
          <li key={e.id}>
            <a href={e.link} className="flex w-full items-center gap-3 rounded-2xl bg-black/20 p-2.5 text-left transition-colors hover:bg-black/30">
              <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${TONE[e.tone] ?? TONE.info}`} aria-hidden="true">
                {(() => {
                  const Icon = KIND_ICON[e.kind] ?? Box;
                  return <Icon size={16} />;
                })()}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold">{e.title}</span>
                <span className="block truncate text-xs text-white/55">{e.at.replace('T', ' ').slice(0, 16)}</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
};

const KEY = 'right-expanded';
const RAIL = 64;
const WIDE = 320;

const readExpanded = () => {
  try {
    return localStorage.getItem(KEY) !== '0';
  } catch {
    return true;
  }
};

// Content keeps its full width while the panel grows or shrinks around it (the panel clips), so nothing reflows
// mid-animation. Width minus 11px padding and 1px border on each side.
const INNER_WIDE = WIDE - 24;
const INNER_RAIL = RAIL - 24;
const EASE = [0.4, 0, 0.2, 1];

// Opening: the sections follow the growing edge in, one after another. Closing: they fade out at once.
const list = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { delayChildren: 0.08, staggerChildren: 0.07 } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
};
const item = {
  hidden: { opacity: 0, x: 28, filter: 'blur(6px)' },
  show: { opacity: 1, x: 0, filter: 'blur(0px)', transition: { type: 'spring', stiffness: 260, damping: 26 } },
};

// Shows whether the calendar is receiving pushes from the server right now.
const LiveBadge = ({ live }) => (
  <p className="flex items-center gap-1.5 px-1 text-xs text-white/60">
    <span className={`size-1.5 rounded-full ${live ? 'animate-pulse bg-good' : 'bg-white/40'}`} aria-hidden="true" />
    {live ? 'Live, synced with the server' : 'Reconnecting, refreshing every 10 s'}
  </p>
);

const Summary = ({ overview, model, picked, onPick, start, activity }) => (
  <>
    <motion.div variants={item}><Profile overview={overview} /></motion.div>
    <motion.div variants={item} className="flex flex-col gap-2">
      <LiveBadge live={activity.live} />
      <Calendar key={`${start.getFullYear()}-${start.getMonth()}`} model={model} picked={picked} onPick={onPick} start={start} />
    </motion.div>
    <motion.div variants={item}><RecentActivity activity={activity} /></motion.div>
  </>
);

// Below xl the panel has no room beside the main panel, so it slides in from the right instead.
const Drawer = ({ onClose, children }) => {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[60] xl:hidden">
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <motion.aside
        aria-label="Dataset summary"
        initial={{ x: '100%' }}
        animate={{ x: 0 }}
        exit={{ x: '100%' }}
        transition={{ type: 'spring', stiffness: 360, damping: 38 }}
        className="absolute inset-y-0 right-0 w-[min(22rem,90vw)] p-3"
      >
        <div className="glass-panel flex h-full flex-col rounded-3xl p-3">
          <div className="flex items-center justify-between">
            <h2 className="pl-1 text-base font-semibold">Summary</h2>
            <button type="button" onClick={onClose} aria-label="Close the calendar panel" className="grid size-10 place-items-center rounded-xl text-white/70 hover:bg-white/10 hover:text-white">
              <X size={20} />
            </button>
          </div>
          <motion.div variants={list} initial="hidden" animate="show" className="mt-3 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-1 pb-1">
            {children}
          </motion.div>
        </div>
      </motion.aside>
    </div>
  );
};

const RightPanel = ({ drawerOpen = false, onCloseDrawer }) => {
  const [expanded, setExpanded] = useState(readExpanded);
  const [picked, setPicked] = useState(null); // the clicked date, shared by the calendar, the rail and the drawer

  useEffect(() => {
    try {
      localStorage.setItem(KEY, expanded ? '1' : '0');
    } catch {
      // Storage blocked: the panel just opens expanded next time.
    }
  }, [expanded]);

  const activity = useActivity();
  const today = useToday();

  // The calendar is live: it opens on today, rolls over at midnight and is pushed new captures,
  // scan inspections and model uploads by the server as they happen.
  const { data: overview } = useApi('/api/overview');
  const model = useLiveDayModel(activity.data, today);
  const start = today;

  return (
    <>
      <motion.aside
        aria-label="Dataset summary"
        initial={false}
        animate={{ width: expanded ? WIDE : RAIL }}
        transition={{ duration: 0.34, ease: EASE }}
        style={{ willChange: 'width' }}
        className="glass-panel hidden shrink-0 flex-col overflow-hidden rounded-[28px] p-[11px] xl:flex"
      >
        <button
          type="button"
          onClick={() => {
            keepReadingPosition();
            setExpanded((v) => !v);
          }}
          aria-label={expanded ? 'Collapse the calendar panel' : 'Expand the calendar panel'}
          aria-expanded={expanded}
          title={expanded ? 'Collapse' : 'Expand'}
          className="grid size-10 shrink-0 place-items-center self-start rounded-xl text-white/70 transition-colors hover:bg-white/10 hover:text-white"
        >
          <motion.span key={expanded ? 'close' : 'open'} initial={{ opacity: 0, rotate: expanded ? -90 : 90 }} animate={{ opacity: 1, rotate: 0 }} transition={{ duration: 0.25, ease: EASE }}>
            {expanded ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}
          </motion.span>
        </button>
        <div className="relative mt-2 min-h-0 flex-1">
          <AnimatePresence initial={false}>
            {expanded ? (
              <motion.div
                key="summary"
                variants={list}
                initial="hidden"
                animate="show"
                exit="exit"
                style={{ width: INNER_WIDE }}
                className="absolute inset-y-0 left-0 flex flex-col gap-4 overflow-y-auto px-1 pb-1"
              >
                <Summary overview={overview} model={model} picked={picked} onPick={setPicked} start={start} activity={activity} />
              </motion.div>
            ) : (
              <motion.div
                key="rail"
                initial={{ opacity: 0, y: 10, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)', transition: { delay: 0.18, duration: 0.25, ease: EASE } }}
                exit={{ opacity: 0, transition: { duration: 0.1 } }}
                style={{ width: INNER_RAIL }}
                className="absolute inset-y-0 left-0 flex flex-col"
              >
                <DateRail
                  key={`${start.getFullYear()}-${start.getMonth()}`}
                  start={start}
                  model={model}
                  picked={picked}
                  onPick={(d) => {
                    setPicked(d);
                    keepReadingPosition();
                    setExpanded(true);
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>
      <AnimatePresence>
        {drawerOpen && (
          <Drawer onClose={onCloseDrawer}>
            <Summary overview={overview} model={model} picked={picked} onPick={setPicked} start={start} activity={activity} />
          </Drawer>
        )}
      </AnimatePresence>
    </>
  );
};

export default RightPanel;

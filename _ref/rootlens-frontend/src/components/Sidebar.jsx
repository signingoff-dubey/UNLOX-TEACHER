import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PanelLeftClose, PanelLeftOpen, X } from 'lucide-react';
import Logo from './Logo';
import { homeItem, sections, sectionOf, settingsItem } from '../navigation';
import Liquid from './ui/Liquid';

// A scroll area that fades only the edge that has more to scroll to. At the very top nothing fades at the top, at the very bottom nothing
// fades at the bottom, so the first and last rows are never dimmed. The fade width eases in and out as you scroll off the ends.
const FadeScroll = ({ className = '', children }) => {
  const box = useRef(null);
  const [edge, setEdge] = useState({ top: false, bottom: false });
  const measure = useCallback(() => {
    const el = box.current;
    if (!el) return;
    const top = el.scrollTop > 2;
    const bottom = el.scrollHeight - el.clientHeight - el.scrollTop > 2;
    setEdge((e) => (e.top === top && e.bottom === bottom ? e : { top, bottom }));
  }, []);
  useEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    measure();
    const ro = new ResizeObserver(measure); // the list grows and shrinks as groups fold, and the rail changes width
    ro.observe(el);
    [...el.children].forEach((c) => ro.observe(c));
    return () => ro.disconnect();
  }, [measure]);
  return (
    <div ref={box} onScroll={measure} className={`fade-scroll ${className}`} style={{ '--fade-top': edge.top ? '44px' : '0px', '--fade-bottom': edge.bottom ? '52px' : '0px' }}>
      {children}
    </div>
  );
};

const RAIL = 64;
const EXPANDED = 236;

const Brand = ({ showName }) => (
  <div className="flex items-center gap-1">
    <span className="grid size-10 shrink-0 place-items-center" aria-hidden="true">
      <Logo size={28} className="rounded-lg" />
    </span>
    {showName && <span className="whitespace-nowrap text-base font-semibold">RootLens</span>}
  </div>
);

const Tooltip = ({ children }) => (
  <span
    role="tooltip"
    className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap popover !rounded-xl px-2.5 py-1 text-xs font-medium text-white opacity-0 shadow-lg ring-1 ring-white/10 transition-opacity group-hover:opacity-100 group-has-[:focus-visible]:opacity-100"
  >
    {children}
  </span>
);

// Labels fade instead of mounting, so only the width animates. Fade-in waits for the panel to open up a little.
const fade = (shown) => `transition-opacity ${shown ? 'opacity-100 duration-200 delay-100' : 'opacity-0 duration-100'}`;

const NavButton = ({ item, active, expanded, onSelect, badge, accent = false, pillId }) => {
  const Icon = item.icon;
  return (
    <div className="group relative">
      {/* Outside the button: the button clips its overflow, which would hide the pill while it travels. */}
      {active && pillId && <Liquid layoutId={pillId} className="inset-0 rounded-xl" />}
      <button
        type="button"
        onClick={() => onSelect(item.slug)}
        aria-label={expanded ? undefined : badge ? `${item.label}, ${badge} need you` : item.label}
        aria-current={active ? 'page' : undefined}
        className={`rail-row relative flex w-full px-[11px] items-center gap-3 overflow-hidden text-sm font-medium transition-colors ${
          accent
            ? 'rounded-full border border-accent text-accent hover:bg-accent/10'
            : active
              ? `rounded-xl text-on-accent ${pillId ? '' : 'bg-accent'}`
              : 'rounded-xl text-white/60 hover:bg-white/10 hover:text-white'
        }`}
      >
        <Icon size={18} className="shrink-0" />
        <span className={`min-w-0 flex-1 truncate text-left ${fade(expanded)}`}>{item.label}</span>
        {badge && (
          <span className={`shrink-0 rounded-md px-1.5 text-xs font-semibold ${active ? 'bg-white/20' : 'bg-accent/20 text-accent'} ${fade(expanded)}`}>{badge}</span>
        )}
        {badge && !active && <span className={`absolute right-1.5 top-1.5 size-2 rounded-full bg-accent ring-2 ring-panel ${fade(!expanded)}`} />}
      </button>
      {!expanded && <Tooltip>{item.label}</Tooltip>}
    </div>
  );
};

// Overview and four sections. A section opens on its first screen; the screens inside it are tabs on the page.
const NavList = ({ active, onSelect, expanded, badges, pillId }) => {
  const current = sectionOf(active)?.id;
  return (
    <nav aria-label="Main" className="flex flex-1 flex-col gap-1">
      <NavButton item={homeItem} active={active === homeItem.slug} expanded={expanded} onSelect={onSelect} badge={badges[homeItem.slug]} pillId={pillId} />
      {sections.map((sec) => (
        <NavButton
          key={sec.id}
          item={{ slug: sec.items[0].slug, label: sec.label, icon: sec.icon }}
          active={current === sec.id}
          expanded={expanded}
          onSelect={onSelect}
          badge={sec.items.map((i) => badges[i.slug]).find(Boolean)}
          pillId={pillId}
        />
      ))}
    </nav>
  );
};

const Footer = ({ expanded, onSelect, active }) => (
  <div className="flex flex-col gap-1">
    <NavButton item={settingsItem} active={active === 'settings'} expanded={expanded} onSelect={onSelect} />
  </div>
);

// Collapsed: hovering the logo reveals the expand button. Expanded: the collapse button sits beside the app name.
const RailHeader = ({ expanded, onToggle }) => (
  <div className="flex h-10 shrink-0 items-center">
    <div className="group relative grid size-10 shrink-0 place-items-center text-accent">
      <Logo size={28} className={`rounded-lg ${expanded ? '' : 'transition-opacity group-hover:opacity-0 group-has-[:focus-visible]:opacity-0'}`} />
      {!expanded && (
        <>
          <button
            type="button"
            onClick={onToggle}
            aria-label="Expand sidebar"
            aria-expanded={false}
            className="absolute inset-0 grid place-items-center rounded-xl text-white/70 opacity-0 transition-opacity hover:bg-white/10 hover:text-white focus-visible:opacity-100 group-hover:opacity-100"
          >
            <PanelLeftOpen size={18} />
          </button>
          <Tooltip>Expand sidebar</Tooltip>
        </>
      )}
    </div>
    <div inert={!expanded} className={`flex min-w-0 flex-1 items-center gap-2 overflow-hidden pl-1 ${fade(expanded)}`}>
      <span className="truncate whitespace-nowrap text-base font-semibold">RootLens</span>
      <button
        type="button"
        onClick={onToggle}
        aria-label="Collapse sidebar"
        aria-expanded
        title="Collapse sidebar"
        className="ml-auto grid size-8 shrink-0 place-items-center rounded-lg text-white/60 transition-colors hover:bg-white/10 hover:text-white"
      >
        <PanelLeftClose size={18} />
      </button>
    </div>
  </div>
);

const Rail = ({ active, onSelect, expanded, onToggle, badges }) => (
  // z-30 keeps tooltips above the main panel, which has its own stacking context from backdrop-filter.
  // Padding stays constant (64px rail - 2px border - 22px = 40px content), so the width is the only thing that animates.
  // The corner radius is fixed (28px is already a full pill at 64px): animating it made the shape change before the width did.
  <motion.aside
    initial={false}
    animate={{ width: expanded ? EXPANDED : RAIL }}
    transition={{ duration: 0.26, ease: [0.4, 0, 0.2, 1] }}
    style={{ willChange: 'width' }}
   
    className="relative z-30 hidden shrink-0 flex-col gap-3 lg:flex"
  >
    {/* Two cards: the pages (which scroll) above, the always-there actions below. */}
    <div className="glass-panel flex min-h-0 flex-1 flex-col rounded-[28px] px-[11px] py-3">
      <RailHeader expanded={expanded} onToggle={onToggle} />
      <FadeScroll className="-mx-1 mt-4 flex min-h-0 flex-1 flex-col overflow-y-auto px-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <NavList active={active} onSelect={onSelect} expanded={expanded} badges={badges} pillId="rail-pill" />
      </FadeScroll>
    </div>
    <div className="glass-panel shrink-0 rounded-[28px] px-[11px] py-3">
      <Footer expanded={expanded} onSelect={onSelect} active={active} />
    </div>
  </motion.aside>
);

const Drawer = ({ active, onSelect, onClose, badges }) => (
  <div className="fixed inset-0 z-[60] lg:hidden">
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
    <motion.aside
      initial={{ x: '-100%' }}
      animate={{ x: 0 }}
      exit={{ x: '-100%' }}
      transition={{ type: 'spring', stiffness: 360, damping: 38 }}
      className="absolute inset-y-0 left-0 w-[min(18rem,85vw)] p-3"
    >
      <div className="glass-panel flex h-full flex-col rounded-3xl p-3">
        <div className="flex items-center justify-between">
          <Brand showName />
          <button type="button" onClick={onClose} aria-label="Close menu" className="grid size-10 place-items-center rounded-xl text-white/70 hover:bg-white/10 hover:text-white">
            <X size={20} />
          </button>
        </div>
        <FadeScroll className="mt-3 flex-1 overflow-y-auto">
          <NavList active={active} onSelect={onSelect} expanded badges={badges} pillId="drawer-pill" />
        </FadeScroll>
        <div className="border-t border-white/10 pt-3">
          <Footer expanded onSelect={onSelect} active={active} />
        </div>
      </div>
    </motion.aside>
  </div>
);

const Sidebar = ({ active, onSelect, expanded, onToggle, mobileOpen, onCloseMobile, badges = {} }) => {
  const selectAndClose = (slug) => {
    onSelect(slug);
    onCloseMobile();
  };

  return (
    <>
      <Rail active={active} onSelect={onSelect} expanded={expanded} onToggle={onToggle} badges={badges} />
      <AnimatePresence>{mobileOpen && <Drawer active={active} onSelect={selectAndClose} onClose={onCloseMobile} badges={badges} />}</AnimatePresence>
    </>
  );
};

export default Sidebar;

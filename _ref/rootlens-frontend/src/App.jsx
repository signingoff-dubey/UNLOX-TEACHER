import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import Backdrop from './components/Backdrop.jsx';
import Opening from './components/Opening.jsx';
import AssistantDock from './components/AssistantDock.jsx';
import DataQuality from './pages/DataQuality';
import { Tabs } from './components/ui';
import { MotionConfig, motion } from 'framer-motion';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import BottomNav from './components/BottomNav';
import RightPanel from './components/dashboard/RightPanel';
import Overview from './pages/Overview';
import Ranking from './pages/Ranking';
import SafeWindows from './pages/SafeWindows';
import Savings from './pages/Savings';
import Captures from './pages/Captures';
import Settings from './pages/Settings';
import Timeline from './pages/Timeline';
import Stations from './pages/Stations';
import Pilot from './pages/Pilot';
import Validation from './pages/Validation';
import Compare from './pages/Compare';
import Analyst from './pages/Analyst';
import { StatusCard } from './components/ui/Gate';

// The 3D viewer pulls in the GLTF loader and orbit controls, so the Inspection screen loads on demand.
const Inspection = lazy(() => import('./pages/Inspection'));
import { findPage, pages, sectionOf } from './navigation';
import { useRoute, navigate } from './lib/router';
import ErrorBoundary from './components/ErrorBoundary';

const SCREENS = {
  home: Overview,
  ranking: Ranking,
  windows: SafeWindows,
  savings: Savings,
  timeline: Timeline,
  stations: Stations,
  pilot: Pilot,
  validation: Validation,
  compare: Compare,
  analyst: Analyst,
  captures: Captures,
  inspection: Inspection,
  data: DataQuality,
  settings: Settings,
};

const readExpanded = () => {
  try {
    return localStorage.getItem('sidebar-expanded') === '1';
  } catch {
    return false;
  }
};

// Pages that follow their URL parameter in place (#/windows/F33 -> #/windows/F59 only changes the selection),
// instead of being rebuilt and refetched for every parameter.
const FOLLOWS_PARAM = new Set(['windows']);

const App = () => {
  const { slug, param } = useRoute();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [expanded, setExpanded] = useState(readExpanded);

  useEffect(() => {
    try {
      localStorage.setItem('sidebar-expanded', expanded ? '1' : '0');
    } catch {
      // Storage blocked: the sidebar just starts collapsed next time.
    }
  }, [expanded]);

  // Links inside the summary drawer change the route; the drawer should not stay over the new page.
  useEffect(() => {
    setSummaryOpen(false);
  }, [slug, param]);

  const closeSummary = useCallback(() => setSummaryOpen(false), []);

  const page = findPage(slug) ?? pages.home;
  const Screen = SCREENS[page.slug];
  const section = sectionOf(page.slug);

  return (
    <MotionConfig reducedMotion="user">
      <Backdrop />
      <Opening />
      <div className="flex min-h-dvh gap-4 p-3 sm:p-4 lg:h-dvh">
        <Sidebar
          active={page.slug}
          onSelect={navigate}
          expanded={expanded}
          onToggle={() => setExpanded((v) => !v)}
          mobileOpen={mobileOpen}
          onCloseMobile={() => setMobileOpen(false)}
        />

        <div className="glass-panel relative flex min-w-0 flex-1 flex-col rounded-[28px]">
          <main className="flex-1 overflow-y-auto p-4 pb-24 sm:p-6 sm:pb-24">
            <Navbar page={page} onOpenMenu={() => setMobileOpen(true)} onOpenSummary={() => setSummaryOpen(true)} />
            <motion.div
              key={FOLLOWS_PARAM.has(page.slug) ? page.slug : `${page.slug}/${param ?? ''}`}
              className="mt-6"
              initial={{ opacity: 0, y: 14, scale: 0.985, filter: 'blur(10px)' }}
              animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)', transitionEnd: { filter: 'none', transform: 'none' } }}
              transition={{ type: 'spring', stiffness: 260, damping: 28, mass: 0.9 }}
            >
              {section && section.items.length > 1 && (
                <div className="mb-[var(--gap)]">
                  <Tabs dark tabs={section.items.map((i) => i.label)} active={page.label} onChange={(label) => navigate(section.items.find((i) => i.label === label).slug)} />
                </div>
              )}
              <Suspense fallback={<StatusCard q={{ loading: true }} what="This page" />}>
                <ErrorBoundary key={page.slug} what={page.label}>
                  <Screen key={FOLLOWS_PARAM.has(page.slug) ? page.slug : param} id={param} />
                </ErrorBoundary>
              </Suspense>
            </motion.div>
          </main>
          <BottomNav active={page.slug} onSelect={navigate} />
        </div>

        <RightPanel drawerOpen={summaryOpen} onCloseDrawer={closeSummary} />
        <ErrorBoundary what="The assistant">
          <AssistantDock />
        </ErrorBoundary>
      </div>
    </MotionConfig>
  );
};

export default App;

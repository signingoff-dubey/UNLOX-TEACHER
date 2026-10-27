import { House, ListOrdered, Crosshair, PiggyBank, Camera, Settings, Wrench, ShieldCheck, History, Factory, FlaskConical, Scale, Box, Bot, Search, Database } from 'lucide-react';

// Screens of the RootLens dashboard. `slug` is the URL hash (#/ranking).
// Every screen reads the RootLens API (src/lib/api.js); a 503 from it means the artifact has not been generated yet.
export const pages = {
  home: { slug: 'home', label: 'Overview', icon: House, description: 'How well failures can be predicted on a later time window, and where to look first.' },
  ranking: { slug: 'ranking', label: 'Ranking', icon: ListOrdered, description: 'Statistically suspected drivers of failure, ranked, with stability across 50 bootstrap resamples.' },
  windows: { slug: 'windows', label: 'Safe windows', icon: Crosshair, description: 'Where each stable driver had the lowest failure rate, inside the range the line has run. Association, not proof.' },
  savings: { slug: 'savings', label: 'Savings', icon: PiggyBank, description: 'Model-estimated monthly savings as a range, under the assumptions you set.' },
  timeline: { slug: 'timeline', label: 'Timeline', icon: History, description: 'How the suspected drivers shifted from one time window to the next. Association, not proven cause.' },
  stations: { slug: 'stations', label: 'Stations (Bosch)', icon: Factory, description: 'Bosch production line: part flow, fail rate per station and which stations are statistically suspected, stability-checked.' },
  pilot: { slug: 'pilot', label: 'Pilot planner', icon: FlaskConical, description: 'How many parts, how many days and what it costs to test a suggested window on the line.' },
  validation: { slug: 'validation', label: 'Validation', icon: ShieldCheck, description: 'Does the method work? Planted-fault benchmark against plain SHAP ranking, and a check on a dataset with known failure rules.' },
  compare: { slug: 'compare', label: 'How we compare', icon: Scale, description: 'What RootLens covers, set against the public projects we checked.' },
  analyst: { slug: 'analyst', label: 'AI Analyst', icon: Bot, description: 'Ask questions in plain language, or run a full investigation. Every number in an answer is checked against the analysis tools.' },
  captures: { slug: 'captures', label: 'Captures', icon: Camera, description: 'Photograph or upload a process sheet, check what was read, and see the run scored against the safe windows. Run history is one tab over.' },
  data: { slug: 'data', label: 'Data quality', icon: Database, description: 'Missing values and outliers: what was filled or clipped, fitted on the training window only, and the check that the data kept its shape.' },
  inspection: { slug: 'inspection', label: 'Inspection', icon: Box, description: 'Separate capability, not part of root-cause analysis: surface checks on a 3D scan, analyzed after upload.' },
  settings: { slug: 'settings', label: 'Settings', icon: Settings, description: 'Theme, accent, surfaces, density, the API address and analysis defaults.' },
};

// The sidebar holds five sections. A section with several screens shows them as tabs at the top of the page,
// so every old link (#/windows, #/pilot ...) still opens, inside its section.
export const homeItem = pages.home;
export const sections = [
  { id: 'rootcause', label: 'Root cause', icon: Search, items: [pages.ranking, pages.timeline, pages.stations] },
  { id: 'fix', label: 'Fix & savings', icon: Wrench, items: [pages.windows, pages.savings, pages.pilot] },
  { id: 'inspect', label: 'Inspection', icon: Box, items: [pages.inspection, pages.captures] },
  { id: 'trust', label: 'Trust', icon: ShieldCheck, items: [pages.data, pages.validation, pages.compare] },
];

export const sectionOf = (slug) => sections.find((s) => s.items.some((i) => i.slug === slug));

export const settingsItem = pages.settings;

// The floating pill: the three answers RootLens gives, in order (where, what to change, how much).
export const flowSteps = [pages.ranking, pages.windows, pages.savings];

export const findPage = (slug) => pages[slug];

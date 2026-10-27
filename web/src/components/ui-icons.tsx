import React from "react";

// Small stroke icons for the app UI (the video templates have their own set in remotion/icons.tsx).
const base = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2,
  strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;

const P: Record<string, React.ReactNode> = {
  play: <path d="M7 4.5v15l12-7.5z" fill="currentColor" stroke="none" />,
  pause: <><rect x="6" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" /><rect x="14" y="4.5" width="4" height="15" rx="1" fill="currentColor" stroke="none" /></>,
  back5: <><path d="M4 12a8 8 0 1 0 2.5-5.8" /><path d="M4 4v4h4" /><text x="12" y="16" fontSize="8" fontWeight="700" textAnchor="middle" fill="currentColor" stroke="none">5</text></>,
  fwd5: <><path d="M20 12a8 8 0 1 1-2.5-5.8" /><path d="M20 4v4h-4" /><text x="12" y="16" fontSize="8" fontWeight="700" textAnchor="middle" fill="currentColor" stroke="none">5</text></>,
  prev: <><path d="M6 5v14" /><path d="M19 5.5v13L9 12z" fill="currentColor" stroke="none" /></>,
  next: <><path d="M18 5v14" /><path d="M5 5.5v13L15 12z" fill="currentColor" stroke="none" /></>,
  volume: <><path d="M4 9.5v5h4l5 4v-13l-5 4z" fill="currentColor" stroke="none" /><path d="M16.5 8.5a5 5 0 0 1 0 7" /><path d="M19 6a8.5 8.5 0 0 1 0 12" /></>,
  mute: <><path d="M4 9.5v5h4l5 4v-13l-5 4z" fill="currentColor" stroke="none" /><path d="M17 9.5l5 5M22 9.5l-5 5" /></>,
  flashcards: <><rect x="3" y="6" width="14" height="11" rx="2" /><path d="M7 3h12a2 2 0 0 1 2 2v9" /></>,
  quiz: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01" /></>,
  mindmap: <><circle cx="5" cy="12" r="2.5" /><circle cx="19" cy="5.5" r="2" /><circle cx="19" cy="12" r="2" /><circle cx="19" cy="18.5" r="2" /><path d="M7.5 11l9.5-5M7.5 12h9.5M7.5 13l9.5 5" /></>,
  studyguide: <><path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z" /><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3M9 8h6M9 12h6" /></>,
  faq: <><path d="M4 5h16v11H9l-5 4z" /><path d="M9 9h6M9 12h4" /></>,
  glossary: <><path d="M8 6h12M8 12h12M8 18h12" /><circle cx="4" cy="6" r="1" fill="currentColor" /><circle cx="4" cy="12" r="1" fill="currentColor" /><circle cx="4" cy="18" r="1" fill="currentColor" /></>,
  timeline: <><path d="M12 3v18" /><circle cx="12" cy="7" r="2" fill="currentColor" /><circle cx="12" cy="17" r="2" fill="currentColor" /><path d="M14.5 7H20M4 17h5.5" /></>,
  cube: <><path d="M12 2.5l8.5 4.7v9.6L12 21.5l-8.5-4.7V7.2z" /><path d="M3.5 7.2L12 12l8.5-4.8M12 12v9.5" /></>,
  mic: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3" /></>,
  cc: <><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M10 10.2a2.5 2.5 0 1 0 0 3.6M17 10.2a2.5 2.5 0 1 0 0 3.6" /></>,
  gear: <><circle cx="12" cy="12" r="3" /><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1" /></>,
  full: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
  unfull: <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />,
  upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></>,
  file: <><path d="M6 3h8l5 5v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" /><path d="M14 3v5h5" /></>,
  x: <path d="M6 6l12 12M18 6L6 18" />,
  arrowLeft: <path d="M19 12H5M11 6l-6 6 6 6" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  download: <><path d="M12 4v12M7 11l5 5 5-5" /><path d="M4 19h16" /></>,
  sparkle: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" fill="currentColor" stroke="none" />,
};

export const Ui: React.FC<{ name: keyof typeof P; size?: number }> = ({ name, size = 22 }) => (
  <svg {...base} width={size} height={size}>{P[name]}</svg>
);

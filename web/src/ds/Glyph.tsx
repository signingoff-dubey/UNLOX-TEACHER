import React from "react";

// Thin line icons for the UI chrome, drawn on a 24x24 grid. The first block is Priya's set; the rest were added for the new screens.
const PATHS: Record<string, string> = {
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z",
  book: "M4 5a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0-2 2zM4 20a2 2 0 0 0 2 2h13v-4",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM9 13h6",
  x: "M6 6l12 12M18 6L6 18",
  trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
  cube: "M12 2l9 5v10l-9 5-9-5V7zM12 22V12M21 7l-9 5-9-5",
  leaf: "M5 19C5 10 11 4 20 4c0 9-6 15-15 15zM5 19l8-8",
  drop: "M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z",
  rainbow: "M3 18a9 9 0 0 1 18 0M7 18a5 5 0 0 1 10 0",
  pie: "M12 3v9h9a9 9 0 1 1-9-9zM15 3.5A9 9 0 0 1 20.5 9H15z",
  download: "M12 3v12M7 10l5 5 5-5M4 21h16",
  captions: "M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM7 11h4M7 15h7M14 11h3",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  // added for Chanakya
  home: "M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z",
  plus: "M12 5v14M5 12h14",
  library: "M5 4h4v16H5zM11 4h4v16h-4zM17.5 5.5l3 .8-3.6 13.4-3-.8z",
  trophy: "M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a3 3 0 0 0 3 3h1M16 6h4v1a3 3 0 0 1-3 3h-1M12 13v4M8 21h8M10 17h4",
  flame: "M12 3c1 3 4 4.5 4 8.5A4 4 0 0 1 12 16a4 4 0 0 1-4-4c0-1.5.6-2.6 1.5-3.5C9.5 10 11 10 11 8c0-2 .5-3.5 1-5zM12 21a6 6 0 0 1-6-6c0-1.8.8-3.2 2-4.4M12 21a6 6 0 0 0 6-6c0-1.2-.3-2.2-.8-3",
  check: "M5 12.5l4.5 4.5L19 7.5",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
  play: "M8 5.5v13l11-6.5z",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 16.5a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9zM12 12h.01",
  chevron: "M9 6l6 6-6 6",
  shield: "M12 3l7 3v5c0 5-3 8.5-7 10-4-1.5-7-5-7-10V6z",
  star: "M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z",
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12l2-1-1-3-2.3.2-1.6-1.6L16.4 4l-3-1-1 2h-2.8l-1-2-3 1 .7 2.3L4.7 8.2 2.4 8l-1 3 2 1v1.5l-2 1 1 3 2.3-.2 1.6 1.6L7.6 20l3 1 1-2h2.8l1 2 3-1-.7-2.3 1.6-1.6L21 16l1-3z",
};

export const Glyph: React.FC<{ name: string; size?: number; className?: string }> = ({ name, size = 18, className }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
    strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d={PATHS[name] ?? PATHS.sparkle} />
  </svg>
);

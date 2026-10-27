import React from "react";
import { C } from "./theme";

// Simple original line icons, drawn on a 100x100 grid. The LLM picks one by name.
// Fill defaults to "none" on the <svg>; shapes that need colour set their own fill.
const S = { stroke: C.ink, strokeWidth: 5, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const ICONS: Record<string, React.ReactNode> = {
  lightbulb: (
    <>
      <path d="M50 12a26 26 0 0 0-15 47c4 3 6 7 6 11h18c0-4 2-8 6-11a26 26 0 0 0-15-47z" fill="#FFE28A" {...S} />
      <path d="M41 80h18M43 89h14" {...S} />
    </>
  ),
  sun: (
    <>
      <circle cx="50" cy="50" r="18" fill="#FFC94A" {...S} />
      {Array.from({ length: 8 }, (_, i) => {
        const a = (i * Math.PI) / 4;
        return <line key={i} x1={50 + 28 * Math.cos(a)} y1={50 + 28 * Math.sin(a)}
          x2={50 + 40 * Math.cos(a)} y2={50 + 40 * Math.sin(a)} {...S} />;
      })}
    </>
  ),
  leaf: (
    <>
      <path d="M18 82C18 40 45 16 84 16c0 40-24 66-66 66z" fill="#8FD18A" {...S} />
      <path d="M18 82L62 38M40 60h16M32 52V38" {...S} />
    </>
  ),
  water: <path d="M50 12C38 32 24 46 24 62a26 26 0 0 0 52 0c0-16-14-30-26-50z" fill="#8CC8F2" {...S} />,
  atom: (
    <>
      <ellipse cx="50" cy="50" rx="40" ry="15" {...S} />
      <ellipse cx="50" cy="50" rx="40" ry="15" transform="rotate(60 50 50)" {...S} />
      <ellipse cx="50" cy="50" rx="40" ry="15" transform="rotate(-60 50 50)" {...S} />
      <circle cx="50" cy="50" r="7" fill={C.pink} {...S} />
    </>
  ),
  cell: (
    <>
      <ellipse cx="50" cy="50" rx="40" ry="32" fill="#CDEBC6" {...S} />
      <circle cx="56" cy="46" r="12" fill="#9C84DB" {...S} />
      <circle cx="30" cy="58" r="3" fill={C.ink} />
      <circle cx="40" cy="68" r="3" fill={C.ink} />
      <circle cx="72" cy="64" r="3" fill={C.ink} />
    </>
  ),
  heart: <path d="M50 84S14 62 14 36a18 18 0 0 1 36-4 18 18 0 0 1 36 4c0 26-36 48-36 48z" fill="#F29AAE" {...S} />,
  brain: (
    <>
      <path d="M48 18c-10-6-26 0-26 14-10 6-10 22 0 28 0 14 14 22 26 16zM52 18c10-6 26 0 26 14 10 6 10 22 0 28 0 14-14 22-26 16z" fill="#F6B8C8" {...S} />
      <path d="M34 40c6 0 8 6 8 10M66 40c-6 0-8 6-8 10" {...S} />
    </>
  ),
  earth: (
    <>
      <circle cx="50" cy="50" r="38" fill="#8CC8F2" {...S} />
      <path d="M28 30c8 2 10 10 18 10s6 12-2 16-10 12-14 18M64 20c-2 8 6 12 12 12M62 62c6-4 14 0 16 6" fill="#8FD18A" {...S} />
    </>
  ),
  bolt: <path d="M56 8L22 56h24l-6 36 36-50H52z" fill="#FFD84A" {...S} />,
  gear: (
    <>
      {Array.from({ length: 8 }, (_, i) => (
        <rect key={i} x="44" y="8" width="12" height="18" rx="2" fill="#C9D3E6" {...S}
          transform={`rotate(${i * 45} 50 50)`} />
      ))}
      <circle cx="50" cy="50" r="27" fill="#C9D3E6" {...S} />
      <circle cx="50" cy="50" r="10" fill={C.card} {...S} />
    </>
  ),
  book: (
    <>
      <path d="M50 26C40 18 24 18 12 22v56c12-4 28-4 38 4 10-8 26-8 38-4V22c-12-4-28-4-38 4z" fill="#FFE7C2" {...S} />
      <path d="M50 26v56" {...S} />
    </>
  ),
  flask: (
    <>
      <path d="M40 12h20M43 12v26L20 80a6 6 0 0 0 5 8h50a6 6 0 0 0 5-8L57 38V12" fill="#FFFFFF" {...S} />
      <path d="M30 62h40l10 18a6 6 0 0 1-5 8H25a6 6 0 0 1-5-8z" fill="#9FE0C9" {...S} />
    </>
  ),
  cloud: <path d="M28 76a18 18 0 0 1-2-36 24 24 0 0 1 46-6 20 20 0 0 1 4 42z" fill="#E6EEF9" {...S} />,
  magnet: (
    <>
      <path d="M22 18v34a28 28 0 0 0 56 0V18H60v34a10 10 0 0 1-20 0V18z" fill="#F08A8A" {...S} />
      <path d="M22 18h18v14H22zM60 18h18v14H60z" fill="#E3E8F0" {...S} />
    </>
  ),
  rocket: (
    <>
      <path d="M50 8c18 14 22 40 14 62H36C28 48 32 22 50 8z" fill="#E6EEF9" {...S} />
      <circle cx="50" cy="38" r="8" fill="#8CC8F2" {...S} />
      <path d="M36 58L22 74v10l16-10M64 58l14 16v10L62 74M42 76l8 16 8-16" fill="#F7A65A" {...S} />
    </>
  ),
};

export const Icon: React.FC<{ name: string; size: number }> = ({ name, size }) => (
  <svg width={size} height={size} viewBox="0 0 100 100" fill="none">
    {ICONS[name] ?? ICONS.lightbulb}
  </svg>
);

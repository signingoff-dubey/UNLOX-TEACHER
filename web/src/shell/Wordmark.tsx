import React from "react";
import { WORD } from "./logoPaths";

const LIGHT = new Set(["#E3E3E3", "#F2F2F2", "#F6F6F6"]);        // the gaps inside the letters: they take the page colour

/** The site name, drawn in the lettering of the intro animation (the same paths, not a font). `short` is only the first letter. */
export const Wordmark: React.FC<{ height?: number; short?: boolean; className?: string }> = ({ height = 26, short, className }) => {
  const box = short ? [528, 624, 80, 150] : [528, 624, 632, 150];
  return (
    <svg className={className} viewBox={box.join(" ")} height={height} width={(height * box[2]) / box[3]} role="img" aria-label="Chanakya" focusable="false">
      {WORD.map(([d, fill], i) => <path key={i} d={d} fill={LIGHT.has(fill) ? "var(--bg)" : "currentColor"} />)}
    </svg>
  );
};

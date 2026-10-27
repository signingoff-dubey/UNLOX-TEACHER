import { spring, interpolate, Easing } from "remotion";

export const W = 1920;
export const H = 1080;
export const FPS = 30;

export const C = {
  paper: "#FBF7EF",
  grid: "#EEE6D6",
  ink: "#1F2A44",
  muted: "#5B6478",
  card: "#FFFFFF",
  line: "#E3DACA",
  saffron: "#E98A2E",
  teal: "#178F7E",
  blue: "#3366CC",
  rose: "#CF4A68",
  violet: "#7457C2",
  green: "#2E9E57",
};

export const PALETTE = [C.saffron, C.teal, C.blue, C.rose, C.violet, C.green];

// Browser shapes each script with the first family that has its glyphs.
// Nirmala UI ships with Windows and covers every Indic script, as a last resort.
export const FONT_STACK =
  "'Noto Sans', 'Noto Sans Devanagari', 'Noto Sans Telugu', 'Noto Sans Kannada', 'Noto Sans Tamil', " +
  "'Noto Sans Malayalam', 'Noto Sans Bengali', 'Noto Sans Gujarati', 'Nirmala UI', sans-serif";

/** Content area between the header and the caption bar. */
export const STAGE = { top: 140, bottom: 860, left: 110, right: W - 110 };

/** 0 -> 1 spring that starts at `delay` frames. */
export const pop = (frame: number, fps: number, delay = 0) =>
  spring({ frame: frame - delay, fps, config: { damping: 15, mass: 0.7 } });

/** Linear 0 -> 1 progress between two frames, eased. */
export const ease = (frame: number, from: number, to: number) =>
  interpolate(frame, [from, Math.max(to, from + 1)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

/** Frame at which item `i` of `n` appears, spread over the spoken part of the scene
 *  so the visuals follow the narration (which names items in the same order). */
export const revealFrame = (i: number, n: number, speechFrames: number, lead = 10) =>
  Math.round(lead + (i * speechFrames * 0.78) / Math.max(n, 1));

/** Shrink text as it gets longer. Indic scripts render taller, so long labels need room. */
export const fit = (text: string, base: number, comfortableChars: number, min = 0.55) =>
  Math.round(base * Math.max(min, Math.min(1, comfortableChars / Math.max(text.length, 1))));

/** One size for a group of labels (sized by the longest), so sibling boxes match. */
export const fitAll = (texts: string[], base: number, comfortableChars: number, min = 0.55) =>
  fit(texts.reduce((a, b) => (b.length > a.length ? b : a), ""), base, comfortableChars, min);

import { spring, interpolate, Easing } from "remotion";

export const W = 1920;
export const H = 1080;
export const FPS = 30;

// Soft grey glass theme: neutral surfaces, one lime accent, aura gradients.
export const C = {
  bg: "#E2E2E2",
  ink: "#1C1C1C",
  muted: "#6B6B6B",
  card: "#F6F6F6",
  line: "#E9E9E9",
  lime: "#C7D43D",
  green: "#2F8335",
  orange: "#E06A1B",
  blue: "#4A86C5",
  pink: "#E0457A",
  violet: "#7A62C9",
  teal: "#2E9AA0",
};

/** Blurred colour fields behind cards, as in the score / age / tracker cards. */
export const AURA = {
  green: "radial-gradient(120% 90% at 50% 100%, #2F8335 0%, #41A642 35%, #A3C26A 60%, #E3C498 85%, #F1E6D8 100%)",
  orange: "radial-gradient(90% 90% at 55% 60%, #F37811 0%, #ED8441 25%, #E29F68 50%, #DAB093 70%, #BBC5C6 100%)",
  pink: "radial-gradient(80% 80% at 50% 50%, #E18951 0%, #F15F8A 18%, #F589A3 45%, #F2ABB8 70%, #F0C2C7 100%)",
};

export const PALETTE = [C.orange, C.green, C.blue, C.pink, C.violet, C.teal];

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

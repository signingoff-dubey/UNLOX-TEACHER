import { useState } from 'react';

// How the app looks on this device: theme, accent colour, surface style, background, density and text size.
// Kept in localStorage, because it is a per-device preference and not analysis data.
const KEY = 'rootlens-appearance';

// A theme sets the backdrop palette, the panel tint and a default accent. The accent can still be changed on its own.
// Colours are read by index.css (CSS variables) and by ShaderBackdrop.jsx (--sh-* hex values).
export const THEMES = [
  {
    id: 'ember',
    label: 'Ember',
    hint: 'Warm graphite with an orange accent. The default.',
    accent: '#f26b1d',
    vars: { '--bg-0': '#141110', '--bg-1': '#221c18', '--bg-2': '#4a2c18', '--bg-3': '#6b3a17', '--panel-rgb': '28 24 21', '--sh-ink': '#16120f', '--sh-mid': '#7a3d12', '--sh-cool': '#1d2a3a', '--sh-hot': '#f2833a' },
  },
  {
    id: 'marigold',
    label: 'Marigold',
    hint: 'The original PS2 look: warm ink and ochre.',
    accent: '#f0b429',
    vars: { '--bg-0': '#1f1a14', '--bg-1': '#2e261d', '--bg-2': '#5a4220', '--bg-3': '#7a5a1e', '--panel-rgb': '30 26 21', '--sh-ink': '#1b1612', '--sh-mid': '#9e6614', '--sh-cool': '#124d80', '--sh-hot': '#f2852e' },
  },
  {
    id: 'graphite',
    label: 'Graphite',
    hint: 'Cool slate and a green status accent. Calm for long sessions.',
    accent: '#22c55e',
    vars: { '--bg-0': '#0b0f17', '--bg-1': '#111827', '--bg-2': '#1e293b', '--bg-3': '#334155', '--panel-rgb': '17 22 32', '--sh-ink': '#0b0f17', '--sh-mid': '#26344a', '--sh-cool': '#0f3b3a', '--sh-hot': '#3b82f6' },
  },
  {
    id: 'ocean',
    label: 'Deep ocean',
    hint: 'Navy and teal. High contrast for projectors.',
    accent: '#38bdf8',
    vars: { '--bg-0': '#020814', '--bg-1': '#071a2e', '--bg-2': '#0b3354', '--bg-3': '#0f4c6e', '--panel-rgb': '8 20 36', '--sh-ink': '#030a16', '--sh-mid': '#0b3a5e', '--sh-cool': '#0d5c5a', '--sh-hot': '#38bdf8' },
  },
  {
    id: 'aurora',
    label: 'Aurora',
    hint: 'Violet night with a magenta glow.',
    accent: '#a78bfa',
    vars: { '--bg-0': '#0d0a18', '--bg-1': '#1a1230', '--bg-2': '#33204f', '--bg-3': '#4c2463', '--panel-rgb': '24 18 40', '--sh-ink': '#0d0a18', '--sh-mid': '#4a2378', '--sh-cool': '#0f4f5c', '--sh-hot': '#e0457b' },
  },
];

export const ACCENTS = [
  { id: 'ember', label: 'Ember', hex: '#f26b1d' },
  { id: 'marigold', label: 'Marigold', hex: '#f0b429' },
  { id: 'rose', label: 'Rose', hex: '#e0457b' },
  { id: 'violet', label: 'Violet', hex: '#a78bfa' },
  { id: 'ocean', label: 'Ocean', hex: '#38bdf8' },
  { id: 'teal', label: 'Teal', hex: '#14a89a' },
  { id: 'leaf', label: 'Leaf', hex: '#22c55e' },
];

export const SURFACES = [
  { id: 'glass', label: 'Glass', hint: 'Frosted panels and cards. You see the background through them, and text stays easy to read.' },
  { id: 'clear', label: 'Clear glass', hint: 'More see-through and more blur.' },
  { id: 'solid', label: 'Solid', hint: 'No see-through. Best on slow machines and projectors.' },
];

export const BACKDROPS = [
  { id: 'animated', label: 'Moving gradient', hint: 'A slow flowing shader. Falls back to CSS without WebGL.' },
  { id: 'still', label: 'Still gradient', hint: 'Same colours, no movement.' },
  { id: 'plain', label: 'Plain', hint: 'One soft gradient, no blobs.' },
];

export const DENSITIES = [
  { id: 'comfortable', label: 'Comfortable' },
  { id: 'compact', label: 'Compact' },
];

export const TEXT_SIZES = [
  { id: 'sm', label: 'Small', px: 15 },
  { id: 'md', label: 'Default', px: 16 },
  { id: 'lg', label: 'Large', px: 18 },
];

export const DEFAULTS = { theme: 'ember', accent: '#f26b1d', surface: 'glass', backdrop: 'animated', reactive: true, density: 'comfortable', text: 'md', motion: true };

const isHex = (v) => typeof v === 'string' && /^#[0-9a-f]{6}$/i.test(v);
const oneOf = (list, v, fallback) => (list.some((x) => x.id === v) ? v : fallback);

export const readAppearance = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
    return {
      theme: oneOf(THEMES, saved.theme, DEFAULTS.theme),
      accent: isHex(saved.accent) ? saved.accent : DEFAULTS.accent,
      surface: oneOf(SURFACES, saved.surface, DEFAULTS.surface),
      backdrop: oneOf(BACKDROPS, saved.backdrop, DEFAULTS.backdrop),
      reactive: typeof saved.reactive === 'boolean' ? saved.reactive : DEFAULTS.reactive,
      density: oneOf(DENSITIES, saved.density, DEFAULTS.density),
      text: oneOf(TEXT_SIZES, saved.text, DEFAULTS.text),
      motion: typeof saved.motion === 'boolean' ? saved.motion : DEFAULTS.motion,
    };
  } catch {
    return { ...DEFAULTS };
  }
};

const luminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const INK = '#1f1a14';

// Text on the accent: ink or white, whichever reads better on that colour.
export const onAccent = (hex) => {
  const l = luminance(hex);
  const withInk = (l + 0.05) / (luminance(INK) + 0.05);
  const withWhite = 1.05 / (l + 0.05);
  return withInk >= withWhite ? INK : '#ffffff';
};

// Hover, deep and soft accent shades are derived in index.css from --color-accent, so only two accent values are set here.
export const applyAppearance = ({ theme, accent, surface, backdrop, reactive, density, text, motion }) => {
  const root = document.documentElement;
  const t = THEMES.find((x) => x.id === theme) ?? THEMES[0];
  for (const [k, v] of Object.entries(t.vars)) root.style.setProperty(k, v);
  root.style.setProperty('--color-accent', accent);
  root.style.setProperty('--color-on-accent', onAccent(accent));
  root.style.fontSize = `${(TEXT_SIZES.find((s) => s.id === text) ?? TEXT_SIZES[1]).px}px`;
  root.dataset.theme = t.id;
  root.dataset.surface = surface;
  root.dataset.backdrop = backdrop;
  root.dataset.reactive = reactive ? 'on' : 'off';
  root.dataset.density = density;
  root.dataset.motion = motion ? 'on' : 'off';
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t.vars['--bg-0']);
};

export const useAppearance = () => {
  const [value, setValue] = useState(readAppearance);
  const update = (patch) => {
    // Picking a theme also picks its accent; the accent can then be changed on its own.
    const themed = patch.theme ? { accent: THEMES.find((t) => t.id === patch.theme)?.accent ?? value.accent } : {};
    const next = { ...value, ...themed, ...patch };
    setValue(next);
    applyAppearance(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Storage blocked: the change holds until the page reloads.
    }
  };
  const reset = () => update({ ...DEFAULTS });
  return [value, update, reset];
};

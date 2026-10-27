import { useCallback, useEffect, useRef, useState } from 'react';
import { Pipette } from 'lucide-react';

// A colour picker drawn in the app's own style, in place of the browser's stock one: a saturation/brightness square, a hue
// strip, a hex field, optional eyedropper (Chromium) and the preset swatches. Everything works from the keyboard.

const clamp = (n, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, n));

export const hexToHsv = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
  let h = 0;
  if (d) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h = (h * 60 + 360) % 360;
  }
  return { h, s: max ? d / max : 0, v: max };
};

export const hsvToHex = ({ h, s, v }) => {
  const f = (n) => {
    const k = (n + h / 60) % 6;
    return v - v * s * Math.max(0, Math.min(k, 4 - k, 1));
  };
  return `#${[f(5), f(3), f(1)].map((x) => Math.round(x * 255).toString(16).padStart(2, '0')).join('')}`;
};

const normaliseHex = (text) => {
  const t = text.trim().replace(/^#/, '');
  if (/^[0-9a-f]{3}$/i.test(t)) return `#${t.split('').map((c) => c + c).join('')}`.toLowerCase();
  if (/^[0-9a-f]{6}$/i.test(t)) return `#${t}`.toLowerCase();
  return null;
};

// One drag surface used by both the square and the strip. onMove gets x and y as 0..1 inside the element.
function useDrag(onMove) {
  const ref = useRef(null);
  const at = (e) => {
    const r = ref.current.getBoundingClientRect();
    onMove(clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height));
  };
  return {
    ref,
    onPointerDown: (e) => { e.currentTarget.setPointerCapture(e.pointerId); at(e); },
    onPointerMove: (e) => { if (e.currentTarget.hasPointerCapture(e.pointerId)) at(e); },
  };
}

export default function ColorPicker({ value, onChange, presets = [], label = 'Custom', active = false }) {
  const [open, setOpen] = useState(false);
  const [hsv, setHsv] = useState(() => hexToHsv(value));
  const [text, setText] = useState(value);
  const root = useRef(null);
  const button = useRef(null);

  // Follow outside changes (a preset was clicked) without fighting a drag in progress.
  useEffect(() => {
    if (hsvToHex(hsv) !== value) { setHsv(hexToHsv(value)); }
    setText(value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const commit = useCallback((next) => {
    setHsv(next);
    const hex = hsvToHex(next);
    setText(hex);
    onChange(hex);
  }, [onChange]);

  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (!root.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') { setOpen(false); button.current?.focus(); } };
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('pointerdown', away); document.removeEventListener('keydown', esc); };
  }, [open]);

  const square = useDrag((x, y) => commit({ ...hsv, s: x, v: 1 - y }));
  const strip = useDrag((x) => commit({ ...hsv, h: x * 360 }));

  const nudge = (e, fn) => {
    const step = e.shiftKey ? 0.1 : 0.02;
    const map = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (map[e.key]) { e.preventDefault(); fn(...map[e.key]); }
  };

  const eyedrop = async () => {
    try {
      const { sRGBHex } = await new window.EyeDropper().open();
      const hex = normaliseHex(sRGBHex);
      if (hex) commit(hexToHsv(hex));
    } catch { /* cancelled */ }
  };

  const hueColor = hsvToHex({ h: hsv.h, s: 1, v: 1 });
  const current = hsvToHex(hsv);

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3.5 text-sm font-medium transition-colors ${active ? 'border-ink bg-ink/5' : 'border-ink/10 hover:bg-ink/5'}`}
      >
        <span className="size-7 rounded-full ring-1 ring-ink/15" style={{ background: value }} />
        {label} <span className="font-mono text-xs text-ink/50">{value}</span>
      </button>

      {open && (
        <div role="dialog" aria-label="Choose a colour" className="cp-pop absolute right-0 top-full z-50 mt-2 w-[18.5rem] max-w-[calc(100vw-2rem)] rounded-2xl p-3.5 text-white">
          <div
            {...square}
            role="slider"
            tabIndex={0}
            aria-label="Shade: left to right is more colour, top to bottom is darker"
            aria-valuetext={`${Math.round(hsv.s * 100)}% colour, ${Math.round(hsv.v * 100)}% brightness`}
            onKeyDown={(e) => nudge(e, (dx, dy) => commit({ ...hsv, s: clamp(hsv.s + dx), v: clamp(hsv.v - dy) }))}
            className="cp-square relative h-40 w-full cursor-crosshair touch-none rounded-xl"
            style={{ backgroundColor: hueColor }}
          >
            <span className="cp-knob" style={{ left: `${hsv.s * 100}%`, top: `${(1 - hsv.v) * 100}%`, background: current }} />
          </div>

          <div
            {...strip}
            role="slider"
            tabIndex={0}
            aria-label="Hue"
            aria-valuemin={0}
            aria-valuemax={360}
            aria-valuenow={Math.round(hsv.h)}
            onKeyDown={(e) => nudge(e, (dx) => commit({ ...hsv, h: (hsv.h + dx * 360 + 360) % 360 }))}
            className="cp-hue relative mt-3 h-3.5 w-full cursor-pointer touch-none rounded-full"
          >
            <span className="cp-knob" style={{ left: `${(hsv.h / 360) * 100}%`, top: '50%', background: hueColor }} />
          </div>

          <div className="mt-3 flex items-center gap-2">
            <span className="size-9 shrink-0 rounded-lg ring-1 ring-white/20" style={{ background: current }} aria-hidden="true" />
            <input
              aria-label="Hex colour"
              value={text}
              spellCheck={false}
              maxLength={7}
              onChange={(e) => {
                setText(e.target.value);
                const hex = normaliseHex(e.target.value);
                if (hex) { setHsv(hexToHsv(hex)); onChange(hex); }
              }}
              onBlur={() => setText(current)}
              className="h-9 min-w-0 flex-1 rounded-lg bg-white/10 px-3 font-mono text-sm uppercase text-white outline-none ring-1 ring-white/15 focus:ring-2 focus:ring-accent"
            />
            {typeof window !== 'undefined' && 'EyeDropper' in window && (
              <button type="button" onClick={eyedrop} aria-label="Pick a colour from the screen" className="grid size-9 shrink-0 place-items-center rounded-lg bg-white/10 ring-1 ring-white/15 hover:bg-white/20">
                <Pipette size={16} />
              </button>
            )}
          </div>

          {presets.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Preset colours">
              {presets.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  aria-label={p.label}
                  title={p.label}
                  onClick={() => { setHsv(hexToHsv(p.hex)); setText(p.hex); onChange(p.hex); }}
                  className={`size-6 rounded-full ring-1 ring-white/25 transition-transform hover:scale-110 ${value.toLowerCase() === p.hex.toLowerCase() ? 'outline outline-2 outline-offset-2 outline-white' : ''}`}
                  style={{ background: p.hex }}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

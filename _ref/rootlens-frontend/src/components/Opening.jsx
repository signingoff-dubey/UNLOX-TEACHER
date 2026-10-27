import { useEffect, useRef, useState } from 'react';
import logoSvg from '../assets/rootlens-logo.svg?raw';

// RootLens opening (from the brand team's animation/): the logo builds, the lens sweeps the line and finds the one
// orange node, a square locks onto it, the fault is traced back up its root, then the hexagon turns into a window
// that zooms past the screen edges onto the live dashboard underneath. Plays on every page load; Settings can
// replay it or switch it off.

const SPEED = 1.3; // the whole opening runs this much faster than the timings written in the CSS
const CX = 1079.5;
const CY = 927.5; // hexagon centre, the zoom origin
const HEX = '1079.5,440 1511,689 1511,1166 1079.5,1415 648,1166 648,689';
const TRACE = 'M1268.1 1133.65 V928.9 L1162.2 823 L1079.5 739 V440';
export const OPENING_OFF_KEY = 'rootlens.opening.off';
export const REPLAY_EVENT = 'rootlens:replay-opening';

const grab = (re) => logoSvg.match(re)?.[0] ?? '';
const group = (cls) => grab(new RegExp(`<g class="${cls}"[\\s\\S]*?</g>`));
const WORD = grab(/<path class="word"[\s\S]*?\/>/);

const CSS = `
.rl-op { --cyan:#22cede; --orange:#fe6a0c; --ease-out:cubic-bezier(0.16,1,0.3,1); --unit:0.32s; position:fixed; inset:0; z-index:100; }
.rl-op svg { position:absolute; inset:0; width:100%; height:100%; }
.rl-op .draw { stroke-dasharray:1 1; stroke-dashoffset:1; }
.rl-op.play .draw { animation: rl-draw calc(var(--unit)*2.2) var(--ease-out) calc(var(--d)*var(--unit)) forwards; }
.rl-op.play .hex .draw { animation-duration:1.1s; }
.rl-op.play .trunk { animation-duration:0.7s; animation-timing-function:cubic-bezier(0.5,0,0.2,1); }
@keyframes rl-draw { to { stroke-dashoffset:0; } }
.rl-op .node { transform-box:fill-box; transform-origin:center; opacity:0; transform:scale(0.2); }
.rl-op.play .node { animation: rl-pop 0.55s cubic-bezier(0.34,1.56,0.64,1) calc(var(--d)*var(--unit) + 0.25s) forwards; }
@keyframes rl-pop { to { opacity:1; transform:scale(1); } }
.rl-op .scan { opacity:0; }
.rl-op.play .scan { animation: rl-scan 0.9s cubic-bezier(0.45,0,0.25,1) 2.55s forwards; }
@keyframes rl-scan { 0% { opacity:0; transform:translateX(-560px); } 20% { opacity:1; } 80% { opacity:1; } 100% { opacity:0; transform:translateX(560px); } }
.rl-op.play .node:not(.root) { animation: rl-pop 0.55s cubic-bezier(0.34,1.56,0.64,1) calc(var(--d)*var(--unit) + 0.25s) forwards, rl-blink 0.5s ease calc(2.55s + var(--sx)*0.9s) 1; }
@keyframes rl-blink { 40% { stroke:#fff; } }
.rl-op .node.root { stroke:var(--cyan); }
.rl-op.play .node.root { animation: rl-pop 0.55s cubic-bezier(0.34,1.56,0.64,1) calc(var(--d)*var(--unit) + 0.25s) forwards, rl-ignite 0.5s ease 3.25s forwards; }
@keyframes rl-ignite { to { stroke:var(--orange); } }
.rl-op .word { clip-path:inset(0 100% 0 0); transform:translateY(26px); opacity:0; }
.rl-op.play .word { animation: rl-word 0.9s var(--ease-out) 3.35s forwards; }
@keyframes rl-word { to { clip-path:inset(0 0 0 0); transform:none; opacity:1; } }
.rl-op .tag { font:500 38px/1 ui-monospace,'JetBrains Mono',Consolas,monospace; letter-spacing:0.18em; fill:#e8eef0; opacity:0; }
.rl-op.play .tag { animation: rl-tag 0.8s ease 4s forwards; }
@keyframes rl-tag { to { opacity:0.6; } }
.rl-op .lock { fill:none; stroke:var(--orange); stroke-width:5; opacity:0; transform-box:fill-box; transform-origin:center; }
.rl-op.play .lock { animation: rl-lock 0.7s var(--ease-out) 5.1s forwards; }
@keyframes rl-lock { 0% { opacity:0; transform:scale(2.6) rotate(45deg); } 100% { opacity:1; transform:scale(1) rotate(0deg); } }
.rl-op .trace, .rl-op .trace-glow { fill:none; stroke:var(--orange); stroke-linejoin:miter; stroke-dasharray:1 1; stroke-dashoffset:1; }
.rl-op .trace { stroke-width:21; }
.rl-op .trace-glow { stroke-width:44; opacity:0.45; filter:url(#rl-blur); }
.rl-op.play .trace, .rl-op.play .trace-glow { animation: rl-draw 1.5s cubic-bezier(0.65,0,0.35,1) 5.5s forwards; }
.rl-op .top { fill:none; stroke:var(--orange); stroke-width:8; opacity:0; transform-box:fill-box; transform-origin:center; }
.rl-op.play .top { animation: rl-pulse 1s var(--ease-out) 6.95s 2; }
@keyframes rl-pulse { 0% { opacity:1; transform:scale(0.6); } 100% { opacity:0; transform:scale(3.6); } }
.rl-op .pulse { fill:none; stroke:var(--orange); stroke-width:6; opacity:0; transform-box:fill-box; transform-origin:center; }
.rl-op.play .pulse { animation: rl-pulse 1.2s var(--ease-out) 3.3s 1; }
.rl-op .glow { opacity:0; transition:opacity 1.6s ease; }
.rl-op.play .glow { opacity:1; }
.rl-op .skip { position:absolute; right:24px; bottom:24px; font:500 0.75rem system-ui,sans-serif; color:#e8eef0b3; background:#171c20b3; border:1px solid #ffffff26; border-radius:999px; padding:0.6rem 1.1rem; min-height:44px; cursor:pointer; backdrop-filter:blur(8px); transition:color .2s,border-color .2s; }
.rl-op .skip:hover, .rl-op .skip:focus-visible { color:#fff; border-color:#ffffff66; }
@media (prefers-reduced-motion: reduce) {
  .rl-op .draw, .rl-op .trace, .rl-op .trace-glow { stroke-dashoffset:0; }
  .rl-op .node, .rl-op .word { opacity:1; transform:none; clip-path:none; }
  .rl-op .node.root { stroke:var(--orange); }
  .rl-op .tag { opacity:0.6; }
  .rl-op .lock { opacity:1; }
  .rl-op.play * { animation:none !important; }
}`;

const SCENE = `
<defs>
  <filter id="rl-blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>
  <radialGradient id="rl-halo"><stop offset="0" stop-color="#22cede" stop-opacity="0.18"/><stop offset="1" stop-color="#22cede" stop-opacity="0"/></radialGradient>
  <clipPath id="rl-lens"><polygon points="${HEX}"/></clipPath>
  <linearGradient id="rl-beam" x1="0" x2="1"><stop offset="0" stop-color="#22cede" stop-opacity="0"/><stop offset="0.5" stop-color="#bff6fb" stop-opacity="0.28"/><stop offset="1" stop-color="#22cede" stop-opacity="0"/></linearGradient>
  <mask id="rl-window" maskUnits="userSpaceOnUse" x="-40000" y="-40000" width="80000" height="80000">
    <rect x="-40000" y="-40000" width="80000" height="80000" fill="#fff"/>
    <g class="zoomer"><polygon data-hole points="${HEX}" fill="#000" fill-opacity="0"/></g>
  </mask>
</defs>
<rect x="-40000" y="-40000" width="80000" height="80000" fill="#171c20" mask="url(#rl-window)"/>
<g class="zoomer">
  <circle class="glow" cx="1079.5" cy="927.5" r="760" fill="url(#rl-halo)"/>
  <g data-lines>
    ${group('roots')}
    <g clip-path="url(#rl-lens)"><rect class="scan" x="989.5" y="430" width="180" height="1000" fill="url(#rl-beam)"/></g>
    <path class="trace-glow" pathLength="1" d="${TRACE}"/>
    <path class="trace" pathLength="1" d="${TRACE}"/>
    ${group('nodes')}
    <circle class="pulse" cx="1268.1" cy="1156.4" r="22.75"/>
    <rect class="lock" x="1218.1" y="1106.4" width="100" height="100" rx="6"/>
    <circle class="top" cx="1079.5" cy="440" r="26"/>
  </g>
  <g data-brand>
    ${WORD}
    <text class="tag" x="1079.5" y="1808" text-anchor="middle">ROOT-CAUSE ANALYSIS · DIGITAL MANUFACTURING</text>
  </g>
  ${group('hex')}
</g>`;

const read = (store, key) => {
  try {
    return store.getItem(key);
  } catch {
    return null;
  }
};

const Opening = () => {
  const [show, setShow] = useState(() => read(localStorage, OPENING_OFF_KEY) !== '1');   // every page load
  const [run, setRun] = useState(0);
  const root = useRef(null);
  const svg = useRef(null);

  useEffect(() => {
    const replay = () => {
      setShow(true);
      setRun((n) => n + 1);
    };
    addEventListener(REPLAY_EVENT, replay);
    return () => removeEventListener(REPLAY_EVENT, replay);
  }, []);

  useEffect(() => {
    if (!show) return undefined;
    const el = root.current;
    const scene = svg.current;
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hole = scene.querySelector('[data-hole]');
    const lines = scene.querySelector('[data-lines]');
    const brand = scene.querySelector('[data-brand]');
    const zoomers = scene.querySelectorAll('.zoomer');
    const vb = scene.viewBox.baseVal;
    scene.querySelectorAll('.node').forEach((n) => n.style.setProperty('--sx', ((+n.getAttribute('cx') - vb.x) / vb.width).toFixed(3)));
    const setZoom = (s) => zoomers.forEach((g) => g.setAttribute('transform', `translate(${CX} ${CY}) scale(${s}) translate(${-CX} ${-CY})`));
    const clamp01 = (v) => Math.max(0, Math.min(1, v));
    let raf = 0;
    let zooming = false;

    const finish = () => setShow(false);
    // The hexagon turns into a window and grows until its edges are past every corner of the screen.
    const zoom = (ms) => {
      if (zooming) return;
      zooming = true;
      clearTimeout(timer);
      const t0 = performance.now();
      const frame = (now) => {
        const p = clamp01((now - t0) / ms);
        hole.setAttribute('fill-opacity', clamp01(p * 5).toFixed(3));
        brand.style.opacity = String(1 - clamp01(p * 4));
        lines.style.opacity = String(1 - clamp01(p * 2.2));
        setZoom(reduced ? 1 : 1 + 25 * p ** 4);
        if (reduced) el.style.opacity = String(1 - p);
        if (p < 1) raf = requestAnimationFrame(frame);
        else finish();
      };
      raf = requestAnimationFrame(frame);
    };

    setZoom(1);
    el.classList.remove('play');
    void el.getBoundingClientRect(); // restart the CSS animations
    el.classList.add('play');
    el.getAnimations({ subtree: true }).forEach((a) => {
      a.playbackRate = SPEED;
    });
    const timer = setTimeout(() => zoom(reduced ? 500 : 1500 / SPEED), reduced ? 1200 : 7400 / SPEED);
    const onKey = (e) => {
      if (['Escape', 'Enter', ' '].includes(e.key)) {
        e.preventDefault();
        zoom(700);
      }
    };
    const skip = el.querySelector('.skip');
    const onSkip = () => zoom(700);
    skip.addEventListener('click', onSkip);
    addEventListener('keydown', onKey);
    skip.focus({ preventScroll: true });
    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(raf);
      removeEventListener('keydown', onKey);
      skip.removeEventListener('click', onSkip);
    };
  }, [show, run]);

  if (!show) return null;
  return (
    <div ref={root} className="rl-op" key={run}>
      <style>{CSS}</style>
      <svg ref={svg} viewBox="360 352 1440 1500" preserveAspectRatio="xMidYMid meet" role="img" aria-label="RootLens" dangerouslySetInnerHTML={{ __html: SCENE }} />
      <button type="button" className="skip">Skip intro</button>
    </div>
  );
};

export default Opening;

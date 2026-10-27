import { useEffect, useRef } from 'react';
import { Mesh, OrthographicCamera, PlaneGeometry, Scene, ShaderMaterial, Vector2, Vector3, WebGLRenderer } from 'three';

// A flowing, warped gradient drawn by a small fragment shader on one full-screen triangle pair.
// It draws at full resolution with dithering (dark gradients band badly in 8 bits otherwise), pauses while the tab is hidden, stands still for people who ask
// for reduced motion, and removes itself if WebGL is missing so the CSS gradient underneath shows instead.
// The pointer stirs it: a trail of points chases the cursor, swirls the gradient around them, and leaves a soft glow and ripple.
const SPEED = 0.3;
const TRAIL = 8; // points in the cursor's wake; keep in step with the shader's TRAIL
const MAX_DPR = 1.5; // full resolution up to this pixel ratio: a stretched low-res canvas looks soft and blocky

const VERT = `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

const FRAG = `
precision highp float;
varying vec2 vUv;
uniform float uTime;
uniform vec2 uRes;
uniform vec3 uAccent;
uniform vec3 uInk;
uniform vec3 uMid;
uniform vec3 uCool;
uniform vec3 uHot;
#define TRAIL 8
uniform vec2 uTrail[TRAIL]; // cursor wake in 0..1 screen space, newest first
uniform float uEnergy;      // 0 at rest, up to 1 while the cursor moves fast
uniform float uPresence;    // 0 when the cursor is away, 1 when it is over the page
uniform float uClock;       // real seconds, for the ripple

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 3; i++) { v += a * noise(p); p = p * 2.02 + 17.0; a *= 0.5; }
  return v;
}

void main() {
  vec2 uv = vUv;
  float aspect = uRes.x / uRes.y;
  uv.x *= aspect;

  // Swirl the field around each trail point; older points pull less.
  vec2 warp = vec2(0.0);
  float wake = 0.0;
  for (int i = 0; i < TRAIL; i++) {
    vec2 d = uv - vec2(uTrail[i].x * aspect, uTrail[i].y);
    float fall = exp(-dot(d, d) * 26.0) * (1.0 - float(i) / float(TRAIL));
    warp += vec2(-d.y, d.x) * fall;
    wake += fall;
  }
  uv += warp * uPresence * (0.5 + 1.6 * uEnergy);

  float t = uTime;
  vec2 q = vec2(fbm(uv * 0.85 + vec2(0.0, t * 0.55)), fbm(uv * 0.85 + vec2(5.2, -t * 0.45)));
  vec2 r = vec2(fbm(uv * 1.0 + 2.2 * q + vec2(1.7, 9.2) + t * 0.35), fbm(uv * 1.0 + 2.2 * q + vec2(8.3, 2.8) - t * 0.30));
  float f = fbm(uv * 0.8 + 2.4 * r);

  vec3 ink = uInk;
  vec3 ochre = uMid;
  vec3 ember = uHot;
  vec3 sea = uCool;
  vec3 col = mix(ink, ochre, smoothstep(0.25, 0.7, f));
  col = mix(col, sea, smoothstep(0.35, 1.0, length(q)) * 0.55);
  col = mix(col, uAccent, smoothstep(0.45, 0.95, r.x) * 0.55);
  col += ember * smoothstep(0.6, 1.0, f * r.y * 1.6) * 0.35;
  col *= 0.8 + 0.35 * smoothstep(0.0, 1.0, vUv.y);
  // Glow under the cursor, a ripple spreading from it, and a faint light along the wake.
  vec2 hd = vUv - uTrail[0];
  hd.x *= aspect;
  float dist = length(hd);
  float ring = (0.5 + 0.5 * sin(dist * 70.0 - uClock * 5.0)) * exp(-dist * 10.0) * smoothstep(0.0, 0.04, dist);
  col += mix(uAccent, ember, 0.35) * exp(-dist * dist * 70.0) * 0.16 * uPresence;
  col += uAccent * ring * (0.05 + 0.10 * uEnergy) * uPresence;
  col += uAccent * min(wake, 1.5) * uEnergy * 0.07 * uPresence;
  // soft vignette, then ±0.5/255 triangular noise so the 8-bit output has no visible steps
  col *= 1.0 - 0.28 * smoothstep(0.55, 1.25, length(vUv - 0.5) * 1.6);
  float d = hash(gl_FragCoord.xy + fract(uTime) * 61.0) + hash(gl_FragCoord.xy * 1.37 + 7.0) - 1.0;
  col += d / 255.0;
  gl_FragColor = vec4(col, 1.0);
}`;

// Theme colours come from CSS variables set by lib/appearance.js, so the shader follows Settings > Appearance.
const cssColor = (name, fallback) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const m = /^#?([0-9a-f]{6})$/i.exec(v);
  if (!m) return fallback;
  const n = parseInt(m[1], 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};
const cssAccent = () => cssColor('--color-accent', [0.95, 0.42, 0.11]);

export default function ShaderBackdrop() {
  const host = useRef(null);

  useEffect(() => {
    const el = host.current;
    if (!el) return undefined;
    let renderer;
    try {
      renderer = new WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'default' });
    } catch {
      return undefined; // no WebGL: the CSS gradient stays
    }
    const canvas = renderer.domElement;
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';
    el.appendChild(canvas);

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const trail = Array.from({ length: TRAIL }, () => new Vector2(0.5, 0.5));
    const uniforms = {
      uTime: { value: 0 }, uRes: { value: new Vector2(1, 1) }, uAccent: { value: new Vector3(...cssAccent()) },
      uInk: { value: new Vector3(...cssColor('--sh-ink', [0.08, 0.07, 0.06])) }, uMid: { value: new Vector3(...cssColor('--sh-mid', [0.48, 0.24, 0.07])) },
      uCool: { value: new Vector3(...cssColor('--sh-cool', [0.11, 0.16, 0.23])) }, uHot: { value: new Vector3(...cssColor('--sh-hot', [0.95, 0.51, 0.23])) },
      uTrail: { value: trail }, uEnergy: { value: 0 }, uPresence: { value: 0 }, uClock: { value: 0 },
    };
    const scene = new Scene();
    const camera = new OrthographicCamera(-1, 1, 1, -1, 0, 1);
    scene.add(new Mesh(new PlaneGeometry(2, 2), new ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms })));

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      const w = Math.max(2, Math.floor(window.innerWidth * dpr));
      const h = Math.max(2, Math.floor(window.innerHeight * dpr));
      renderer.setPixelRatio(1);
      renderer.setSize(w, h, false);
      uniforms.uRes.value.set(w, h);
    };
    resize();
    window.addEventListener('resize', resize);

    // The accent can change in Settings while this is on screen.
    const watch = new MutationObserver(() => {
      uniforms.uAccent.value.set(...cssAccent());
      uniforms.uInk.value.set(...cssColor('--sh-ink', [0.08, 0.07, 0.06]));
      uniforms.uMid.value.set(...cssColor('--sh-mid', [0.48, 0.24, 0.07]));
      uniforms.uCool.value.set(...cssColor('--sh-cool', [0.11, 0.16, 0.23]));
      uniforms.uHot.value.set(...cssColor('--sh-hot', [0.95, 0.51, 0.23]));
      if (document.documentElement.dataset.reactive === 'off') present = 0;
    });
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['style', 'data-theme', 'data-reactive'] });

    // Pointer in the shader's 0..1 space (y up). The canvas sits behind the UI, so listen on the window.
    const target = new Vector2(0.5, 0.5);
    let seen = false;
    let present = 0;
    // Settings > Appearance can switch the cursor reaction off; the glow then fades out like the cursor left.
    const reactive = () => document.documentElement.dataset.reactive !== 'off';
    const onMove = (e) => {
      if (!reactive()) return;
      target.set(e.clientX / window.innerWidth, 1 - e.clientY / window.innerHeight);
      if (!seen) { trail.forEach((p) => p.copy(target)); seen = true; } // no sweep in from the centre
      present = 1;
    };
    const onLeave = (e) => { if (!e.relatedTarget) present = 0; };
    const onUp = (e) => { if (e.pointerType !== 'mouse') present = 0; }; // a lifted finger has no cursor
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onMove, { passive: true });
    window.addEventListener('pointerup', onUp, { passive: true });
    document.addEventListener('pointerout', onLeave);
    const onBlur = () => { present = 0; };
    window.addEventListener('blur', onBlur);

    let raf = 0;
    let last = performance.now();
    const frame = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      uniforms.uTime.value += dt * SPEED;
      uniforms.uClock.value += dt;
      last = now;
      // The head eases toward the cursor and each point follows the one ahead, so a quick flick leaves a tail.
      const prevX = trail[0].x, prevY = trail[0].y;
      trail[0].lerp(target, 1 - Math.exp(-dt * 14));
      for (let i = 1; i < TRAIL; i++) trail[i].lerp(trail[i - 1], 1 - Math.exp(-dt * 11));
      const speed = dt > 0 ? Math.hypot(trail[0].x - prevX, trail[0].y - prevY) / dt : 0;
      uniforms.uEnergy.value += (Math.min(1, speed * 0.9) - uniforms.uEnergy.value) * (1 - Math.exp(-dt * 6));
      uniforms.uPresence.value += (present - uniforms.uPresence.value) * (1 - Math.exp(-dt * 4));
      renderer.render(scene, camera);
      raf = reduced.matches || document.hidden ? 0 : requestAnimationFrame(frame);
    };
    const start = () => {
      cancelAnimationFrame(raf);
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };
    start();
    document.addEventListener('visibilitychange', start);
    reduced.addEventListener?.('change', start);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', start);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onMove);
      window.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointerout', onLeave);
      window.removeEventListener('blur', onBlur);
      reduced.removeEventListener?.('change', start);
      watch.disconnect();
      scene.traverse((o) => { o.geometry?.dispose?.(); o.material?.dispose?.(); });
      renderer.dispose();
      canvas.remove();
    };
  }, []);

  return <div ref={host} className="shader-backdrop" aria-hidden="true" />;
}

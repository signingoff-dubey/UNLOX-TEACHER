import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { Eye, Flame, LoaderCircle, Pause, Play, RotateCcw, ScanEye, TriangleAlert, Undo2 } from 'lucide-react';
import { apiUrl } from '../lib/api';

// Multi-part model viewer for the "View damage" demo. Plays the model's own disassembly animation (exported from
// Blender as a glTF clip) live in the browser, or explodes the parts outward when the file has no animation.
// "View damage" runs the whole sequence: take it apart, isolate the damaged part, fly the camera to it, switch on the
// simulated thermal layer (COLOR_0). Clicking a part selects it. Every GPU resource is released on unmount.

const EXPLODE = 1.6; // computed explode: parts move this many times their distance from the centre

const partOf = (obj, names) => {
  for (let o = obj; o; o = o.parent) if (names.has(o.name)) return o.name;
  return null;
};

// Same palette as the scale: used to tint whole parts when a model has temperatures but no COLOR_0 layer.
const IRONBOW = ['#0d0d59', '#73148c', '#d94019', '#ffa60d', '#fff7cc'].map((c) => new THREE.Color(c));
const ironbow = (t, min = 25, max = 85) => {
  const x = Math.min(1, Math.max(0, (t - min) / (max - min || 1))) * (IRONBOW.length - 1);
  const i = Math.min(IRONBOW.length - 2, Math.floor(x));
  return IRONBOW[i].clone().lerp(IRONBOW[i + 1], x - i);
};

const ThermalScale = ({ min, max }) => (
  <div className="pointer-events-none absolute bottom-20 right-3 w-40 rounded-xl bg-black/55 p-2 text-[11px] text-white/80 backdrop-blur">
    <p className="font-medium">Thermal (simulated)</p>
    <div className="mt-1 h-2 rounded-full" style={{ background: 'linear-gradient(90deg,#0d0d59,#73148c,#d94019,#ffa60d,#fff7cc)' }} />
    <div className="mt-0.5 flex justify-between tabular"><span>{min ?? 25} °C</span><span>{max ?? 85} °C</span></div>
  </div>
);

const Btn = ({ onClick, active, disabled, children, title, primary, label }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    title={title}
    aria-pressed={active}
    aria-label={label}
    className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 ${
      primary ? 'bg-accent text-on-accent hover:brightness-110' : active ? 'bg-white/20 text-white' : 'bg-white/8 text-white/80 hover:bg-white/15 hover:text-white'
    }`}
  >
    {children}
  </button>
);

const AssemblyViewer = ({ manifest, height = 520, onSelect, onViewDamage }) => {
  const host = useRef(null);
  const api = useRef({});
  const [status, setStatus] = useState({ loading: true, error: '' });
  const [ui, setUi] = useState({ t: 0, duration: 0, playing: false, thermal: false, isolate: false, explode: 0, phase: '' });
  const [selected, setSelected] = useState(null);
  const plan = manifest?.view_damage;
  const hasAnim = Boolean(plan?.animation || manifest?.animations?.length);

  useEffect(() => {
    const el = host.current;
    if (!el || !manifest?.model_url) return undefined;
    let disposed = false;
    let raf = 0;
    setStatus({ loading: true, error: '' });
    setSelected(null);

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setStatus({ loading: false, error: 'This browser could not start WebGL, so the 3D view is unavailable.' });
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;
    el.appendChild(renderer.domElement);
    renderer.domElement.style.display = 'block';

    const scene = new THREE.Scene();
    // Studio-style image lighting gives plastics and metals real highlights instead of flat shading.
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envTex;
    const camera = new THREE.PerspectiveCamera(38, 1, 0.001, 100);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7a6a, 1.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.6);
    key.position.set(2, 4, 3);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xdfe8ff, 1.0);
    fill.position.set(-3, 2, 2);
    scene.add(fill);
    const rim = new THREE.DirectionalLight(0xffd2b0, 1.2);
    rim.position.set(-2, 1, -4);
    scene.add(rim);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    const resize = () => {
      const w = el.clientWidth || 1;
      const h = el.clientHeight || 1;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = '100%';
      renderer.domElement.style.height = '100%';
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const s = { root: null, mixer: null, actions: {}, parts: new Map(), meshes: [], extent: 1, fly: null, clock: new THREE.Clock(), lastUi: 0, explode: 0, pulse: [] };
    const names = new Set((manifest.parts ?? []).map((p) => p.name));

    // ----- material state: every mesh owns a cloned material so isolate / thermal never leak between parts
    const applyLook = () => {
      const iso = api.current.isolate ? new Set(plan?.isolate ?? []) : null;
      for (const m of s.meshes) {
        const mat = m.material;
        const o = m.userData.look;
        const thermal = api.current.thermal && m.geometry.attributes.color;
        const partHeat = api.current.thermal && !thermal && m.userData.temp != null;
        mat.vertexColors = Boolean(thermal);
        mat.color.copy(thermal ? new THREE.Color(1, 1, 1) : partHeat ? ironbow(m.userData.temp, manifest?.thermal?.min_c, manifest?.thermal?.max_c) : o.color);
        mat.map = thermal || partHeat ? null : o.map;
        if (mat.emissive) mat.emissive.copy(o.emissive);
        const hidden = iso && !iso.has(m.userData.part);
        mat.transparent = hidden || o.transparent;
        mat.opacity = hidden ? 0.08 : o.opacity;
        mat.depthWrite = !hidden;
        if (m.userData.part && m.userData.part === api.current.selected && mat.emissive) mat.emissive.setRGB(0.25, 0.18, 0.02);
        mat.needsUpdate = true;
      }
    };

    // ----- camera flight to a box over ~0.9 s
    const flyTo = (box, scale = 2.2) => {
      const centre = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3()).length() || s.extent;
      const dist = (size / (2 * Math.tan((camera.fov * Math.PI) / 360))) * scale;
      const dir = camera.position.clone().sub(controls.target).normalize();
      s.fly = { t: 0, fromPos: camera.position.clone(), fromTarget: controls.target.clone(), toPos: centre.clone().add(dir.multiplyScalar(dist)), toTarget: centre };
    };

    const partBox = (name) => {
      const box = new THREE.Box3();
      s.root.traverse((o) => o.isMesh && o.userData.part === name && box.expandByObject(o));
      return box;
    };

    const setExplode = (k) => {
      s.explode = k;
      for (const p of s.parts.values()) p.obj.position.copy(p.home).addScaledVector(p.dir, k * EXPLODE);
    };

    const report = (force) => {
      const now = performance.now();
      if (!force && now - s.lastUi < 90) return;
      s.lastUi = now;
      const a = s.actions.main;
      setUi((u) => ({ ...u, t: a ? a.time : 0, playing: Boolean(a && a.isRunning() && !a.paused), explode: s.explode }));
    };

    const loop = () => {
      raf = requestAnimationFrame(loop);
      const dt = s.clock.getDelta();
      s.mixer?.update(dt);
      if (s.fly) {
        s.fly.t = Math.min(1, s.fly.t + dt / 0.9);
        const e = 1 - (1 - s.fly.t) ** 3;
        camera.position.lerpVectors(s.fly.fromPos, s.fly.toPos, e);
        controls.target.lerpVectors(s.fly.fromTarget, s.fly.toTarget, e);
        if (s.fly.t >= 1) s.fly = null;
      }
      const pulse = 0.6 + 0.4 * Math.sin(performance.now() / 220);
      for (const m of s.pulse) if (m.material.emissive) m.material.emissiveIntensity = pulse * 2.2;
      controls.update();
      renderer.render(scene, camera);
      if (s.mixer) report(false);
    };
    loop();

    // ----- picking
    const ray = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    let down = null;
    const onDown = (e) => (down = [e.clientX, e.clientY]);
    const onUp = (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5 || !s.root) return;
      const r = renderer.domElement.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects(s.meshes.filter((m) => m.material.opacity > 0.5), false)[0];
      const name = hit ? hit.object.userData.part : null;
      api.current.selected = name;
      setSelected(name);
      onSelect?.(name);
      applyLook();
    };
    renderer.domElement.addEventListener('pointerdown', onDown);
    renderer.domElement.addEventListener('pointerup', onUp);

    const ctl = new AbortController();
    fetch(apiUrl(manifest.model_url), { signal: ctl.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.arrayBuffer();
      })
      .then((buf) => new Promise((resolve, reject) => new GLTFLoader().parse(buf, '', resolve, reject)))
      .then((gltf) => {
        if (disposed) return;
        s.root = gltf.scene;
        scene.add(s.root);

        // Centre and size the assembled model.
        const box = new THREE.Box3().setFromObject(s.root);
        const centre = box.getCenter(new THREE.Vector3());
        s.root.position.sub(centre);
        s.root.updateMatrixWorld(true);
        const size = box.getSize(new THREE.Vector3());
        s.extent = Math.max(size.x, size.y, size.z) || 1;

        s.root.traverse((o) => {
          if (names.has(o.name) && !s.parts.has(o.name)) {
            const wc = new THREE.Box3().setFromObject(o).getCenter(new THREE.Vector3());
            const dir = wc.clone();
            if (dir.lengthSq() < (s.extent * 0.05) ** 2) dir.set(0, 1, 0).multiplyScalar(s.extent * 0.3);
            // explode direction in the parent's space, so nested parts move with their parent
            const local = o.parent.worldToLocal(wc.clone().add(dir)).sub(o.parent.worldToLocal(wc.clone()));
            s.parts.set(o.name, { obj: o, home: o.position.clone(), dir: local });
          }
          if (!o.isMesh) return;
          o.material = Array.isArray(o.material) ? o.material.map((m) => m.clone()) : o.material.clone();
          if (Array.isArray(o.material)) o.material = o.material[0];
          const m = o.material;
          m.side = THREE.DoubleSide;
          m.vertexColors = false;
          o.userData.part = partOf(o, names);
          o.userData.look = { color: m.color.clone(), emissive: m.emissive ? m.emissive.clone() : new THREE.Color(), map: m.map ?? null, opacity: m.opacity, transparent: m.transparent };
          s.meshes.push(o);
          const p = (manifest.parts ?? []).find((x) => x.name === o.userData.part);
          o.userData.temp = p?.temp_c ?? null;
          if (p?.role === 'damage_marker') s.pulse.push(o);
        });
        applyLook();

        // Animation: prefer the plan's clip, else any clip named like a disassembly.
        if (gltf.animations.length) {
          s.mixer = new THREE.AnimationMixer(s.root);
          for (const clip of gltf.animations) {
            const a = s.mixer.clipAction(clip);
            a.setLoop(THREE.LoopOnce, 1);
            a.clampWhenFinished = true;
            s.actions[clip.name] = a;
          }
          const mainName = plan?.animation && s.actions[plan.animation] ? plan.animation
            : Object.keys(s.actions).find((n) => /disassembl|explod/i.test(n)) ?? Object.keys(s.actions)[0];
          s.actions.main = s.actions[mainName];
          s.mixer.addEventListener('finished', (e) => {
            report(true);
            api.current.onFinished?.(e.action);
          });
          setUi((u) => ({ ...u, duration: s.actions.main.getClip().duration }));
        }

        const dist = (s.extent / (2 * Math.tan((camera.fov * Math.PI) / 360))) * 2.4;
        camera.near = s.extent / 500;
        camera.far = s.extent * 200;
        camera.position.set(dist * 0.55, dist * 0.5, dist * 0.85);
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.minDistance = s.extent * 0.05;
        controls.maxDistance = s.extent * 15;
        controls.update();
        setStatus({ loading: false, error: '' });
      })
      .catch((e) => {
        if (disposed || e?.name === 'AbortError') return;
        setStatus({ loading: false, error: `The model could not be loaded: ${e?.message || e}` });
      });

    // ----- commands for the toolbar
    const main = () => s.actions.main;
    api.current = {
      thermal: false,
      isolate: false,
      selected: null,
      play() {
        const a = main();
        if (!a) return setExplode(1) || report(true);
        a.paused = false;
        a.timeScale = 1;
        if (a.time >= a.getClip().duration - 1e-3) a.time = 0;
        a.play();
      },
      reverse() {
        const a = main();
        if (!a) return setExplode(0) || report(true);
        a.paused = false;
        a.timeScale = -1;
        if (a.time <= 1e-3) a.time = a.getClip().duration;
        a.play();
      },
      pause() {
        const a = main();
        if (a) a.paused = true;
        report(true);
      },
      scrub(t) {
        const a = main();
        if (!a) return;
        a.play();
        a.paused = true;
        a.time = t;
        s.mixer.update(0);
        report(true);
      },
      explode(k) {
        setExplode(k);
        report(true);
      },
      setThermal(on) {
        api.current.thermal = on;
        applyLook();
        setUi((u) => ({ ...u, thermal: on }));
      },
      setIsolate(on) {
        api.current.isolate = on;
        applyLook();
        setUi((u) => ({ ...u, isolate: on }));
        if (on && plan?.focus_part) flyTo(partBox(plan.focus_part));
      },
      reset() {
        api.current.setThermal(false);
        api.current.setIsolate(false);
        const a = main();
        if (a) api.current.scrub(0);
        else setExplode(0);
        flyTo(new THREE.Box3().setFromObject(s.root), 1.25);
        setUi((u) => ({ ...u, phase: '' }));
      },
      viewDamage() {
        const finish = () => {
          setUi((u) => ({ ...u, phase: 'Isolating the damaged part' }));
          api.current.setIsolate(true);
          setTimeout(() => {
            api.current.setThermal(true);
            const reveal = s.actions.damage_reveal;
            if (reveal) reveal.reset().play();
            api.current.selected = plan?.focus_part ?? null;
            setSelected(api.current.selected);
            applyLook();
            setUi((u) => ({ ...u, phase: 'Thermal view (simulated)' }));
          }, 900);
        };
        setUi((u) => ({ ...u, phase: 'Taking it apart' }));
        const a = main();
        if (!a) {
          let k = s.explode;
          const step = () => {
            k = Math.min(1, k + 0.04);
            setExplode(k);
            report(true);
            if (k < 1) requestAnimationFrame(step);
            else finish();
          };
          step();
          return;
        }
        api.current.onFinished = (action) => {
          if (action === a && a.timeScale > 0) {
            api.current.onFinished = null;
            finish();
          }
        };
        a.reset();
        a.timeScale = 1.4;
        a.play();
      },
    };

    return () => {
      disposed = true;
      ctl.abort();
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener('pointerdown', onDown);
      renderer.domElement.removeEventListener('pointerup', onUp);
      s.mixer?.stopAllAction();
      s.root?.traverse((o) => {
        if (!o.isMesh) return;
        o.geometry.dispose();
        for (const v of Object.values(o.material)) if (v && v.isTexture) v.dispose();
        o.material.dispose();
      });
      envTex.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      api.current = {};
    };
  }, [manifest?.model_url]); // eslint-disable-line react-hooks/exhaustive-deps

  const part = (manifest?.parts ?? []).find((p) => p.name === selected);
  const ready = !status.loading && !status.error;

  return (
    <div className="flex flex-col gap-3">
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-slate-500 to-slate-800 ring-1 ring-ink/10" style={{ height: `min(${height}px, 64vh)`, minHeight: 360 }}>
        <div ref={host} className="absolute inset-0 touch-none" role="img" aria-label="3D model. Drag to rotate, scroll to zoom, click a part to select it." />
        {status.loading && (
          <div role="status" className="absolute inset-0 grid place-items-center text-sm text-white/75">
            <span className="flex items-center gap-2"><LoaderCircle size={16} className="animate-spin" /> Loading the model...</span>
          </div>
        )}
        {status.error && (
          <div role="alert" className="absolute inset-0 grid place-items-center px-6 text-center text-sm text-white/80">
            <span className="flex items-center gap-2"><TriangleAlert size={16} className="shrink-0" /> {status.error}</span>
          </div>
        )}
        {ui.phase && <p role="status" className="absolute left-3 top-3 rounded-full bg-black/55 px-3 py-1 text-xs font-medium text-white backdrop-blur">{ui.phase}</p>}
        {ui.thermal && <ThermalScale min={manifest?.thermal?.min_c} max={manifest?.thermal?.max_c} />}
        {part && (
          <div className="absolute right-3 top-3 w-60 rounded-2xl bg-white/95 p-3 text-ink shadow-xl">
            <p className="text-sm font-semibold">{part.display_name}</p>
            <p className="text-xs text-ink/55">{part.name} · {part.role}</p>
            {part.temp_c != null && <p className="mt-1.5 text-xs">Temperature: <span className="tabular font-semibold">{part.temp_c} °C</span> (simulated)</p>}
            {part.damage && (
              <div className="mt-2 rounded-xl bg-bad/10 p-2 text-xs text-ink">
                <p className="font-semibold text-bad first-letter:uppercase">{part.damage.type}{part.damage.internal ? ', internal' : ''}{part.damage.severity != null ? `, severity ${part.damage.severity}` : ''}</p>
                {part.damage.description && <p className="mt-0.5">{part.damage.description}</p>}
              </div>
            )}
            {part.station && <p className="mt-1.5 text-[11px] text-ink/55">Station {part.station} (illustrative mapping)</p>}
          </div>
        )}


      <div className="absolute inset-x-3 bottom-3 z-10 flex items-center gap-1.5 overflow-x-auto rounded-2xl bg-black/60 p-2 text-white backdrop-blur">
        <Btn primary onClick={() => { api.current.viewDamage?.(); onViewDamage?.(); }} disabled={!ready || !plan} title={plan ? 'Take it apart, isolate the damaged part, switch to thermal' : 'No damage annotations in this model'}>
          <ScanEye size={15} /> View damage
        </Btn>
        {hasAnim ? (
          <>
            <Btn onClick={() => (ui.playing ? api.current.pause() : api.current.play())} disabled={!ready} title="Play the disassembly">
              {ui.playing ? <Pause size={15} /> : <Play size={15} />} {ui.playing ? 'Pause' : 'Disassemble'}
            </Btn>
            <Btn onClick={() => api.current.reverse()} disabled={!ready} title="Reassemble" label="Reassemble"><Undo2 size={15} /></Btn>
            <input
              type="range"
              min={0}
              max={ui.duration || 1}
              step={0.01}
              value={ui.t}
              disabled={!ready}
              onChange={(e) => api.current.scrub(Number(e.target.value))}
              aria-label="Animation time"
              className="min-w-16 flex-1 accent-accent"
            />
            <span className="tabular w-16 shrink-0 text-right text-xs text-white/70">{ui.t.toFixed(1)} / {(ui.duration || 0).toFixed(1)} s</span>
            <label className="flex min-w-28 items-center gap-1.5 border-l border-white/15 pl-2 text-xs text-white/75">
              Explode
              <input type="range" min={0} max={1} step={0.01} value={ui.explode} disabled={!ready} onChange={(e) => api.current.explode(Number(e.target.value))} className="w-20 accent-accent" aria-label="Explode parts" />
            </label>
          </>
        ) : (
          <label className="flex min-w-40 flex-1 items-center gap-2 text-xs text-white/75">
            Explode
            <input type="range" min={0} max={1} step={0.01} value={ui.explode} disabled={!ready} onChange={(e) => api.current.explode(Number(e.target.value))} className="flex-1 accent-accent" aria-label="Explode parts" />
          </label>
        )}
        <Btn onClick={() => api.current.setThermal(!ui.thermal)} active={ui.thermal} disabled={!ready || !manifest?.thermal?.available} title="Thermal view (simulated)" label="Thermal view"><Flame size={15} /></Btn>
        <Btn onClick={() => api.current.setIsolate(!ui.isolate)} active={ui.isolate} disabled={!ready || !plan} title="Isolate the damaged part" label="Isolate the damaged part"><Eye size={15} /></Btn>
        <Btn onClick={() => api.current.reset()} disabled={!ready} title="Reset the view" label="Reset the view"><RotateCcw size={15} /></Btn>
      </div>
      </div>
    </div>
  );
};

export default AssemblyViewer;

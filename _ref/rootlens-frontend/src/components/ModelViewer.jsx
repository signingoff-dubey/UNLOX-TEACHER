import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { LoaderCircle, TriangleAlert } from 'lucide-react';
import { apiUrl } from '../lib/api';

const disposeMaterial = (m) => {
  for (const v of Object.values(m)) if (v && v.isTexture) v.dispose();
  m.dispose();
};

// Orbit viewer for a GLB the API produced. The camera is fitted to the model's bounding box, and every GPU resource
// (geometries, materials, textures, the renderer itself) is released when the model changes or the screen goes away.
const ModelViewer = ({ url, height = 420 }) => {
  const host = useRef(null);
  const [state, setState] = useState({ loading: true, error: '' });

  useEffect(() => {
    const el = host.current;
    if (!el || !url) return undefined;
    let disposed = false;
    let raf = 0;
    setState({ loading: true, error: '' });

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch {
      setState({ loading: false, error: 'This browser could not start WebGL, so the 3D view is unavailable.' });
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);
    renderer.domElement.style.display = 'block';

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x554433, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(2, 3, 4);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.6);
    fill.position.set(-3, -1, -2);
    scene.add(fill);

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

    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();

    let root = null;
    const ctl = new AbortController();
    fetch(apiUrl(url), { signal: ctl.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return res.arrayBuffer();
      })
      .then(
        (buf) =>
          new Promise((resolve, reject) => {
            new GLTFLoader().parse(buf, '', resolve, reject);
          }),
      )
      .then((gltf) => {
        if (disposed) return;
        root = gltf.scene;
        root.traverse((o) => {
          if (!o.isMesh) return;
          const mats = Array.isArray(o.material) ? o.material : [o.material];
          for (const m of mats) {
            m.side = THREE.DoubleSide;
            if (o.geometry.attributes.color) m.vertexColors = true;
            m.needsUpdate = true;
          }
        });
        scene.add(root);

        // Centre the model at the origin and back the camera off until it fills the view.
        const box = new THREE.Box3().setFromObject(root);
        const centre = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        root.position.sub(centre);
        const extent = Math.max(size.x, size.y, size.z) || 1;
        const dist = (extent / (2 * Math.tan((camera.fov * Math.PI) / 360))) * 1.5;
        camera.near = extent / 200;
        camera.far = extent * 200;
        camera.position.set(dist * 0.6, dist * 0.45, dist * 0.9);
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.minDistance = extent * 0.2;
        controls.maxDistance = extent * 12;
        controls.update();
        setState({ loading: false, error: '' });
      })
      .catch((e) => {
        if (disposed || e?.name === 'AbortError') return;
        setState({ loading: false, error: `The model could not be loaded: ${e?.message || e}` });
      });

    return () => {
      disposed = true;
      ctl.abort();
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      root?.traverse((o) => {
        if (!o.isMesh) return;
        o.geometry.dispose();
        (Array.isArray(o.material) ? o.material : [o.material]).forEach(disposeMaterial);
      });
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [url]);

  return (
    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-ink/85 to-ink/70 ring-1 ring-ink/10" style={{ height }}>
      <div ref={host} className="absolute inset-0 touch-none" role="img" aria-label="3D model of the scan. Drag to rotate, scroll to zoom." />
      {state.loading && (
        <div role="status" className="absolute inset-0 grid place-items-center text-sm text-white/75">
          <span className="flex items-center gap-2"><LoaderCircle size={16} className="animate-spin" /> Loading the model...</span>
        </div>
      )}
      {state.error && (
        <div role="alert" className="absolute inset-0 grid place-items-center px-6 text-center text-sm text-white/80">
          <span className="flex items-center gap-2"><TriangleAlert size={16} className="shrink-0" /> {state.error}</span>
        </div>
      )}
    </div>
  );
};

export default ModelViewer;

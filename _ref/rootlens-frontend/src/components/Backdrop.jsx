import { lazy, Suspense, useEffect, useState } from 'react';

// three.js is only fetched when the animated background is chosen, and the CSS gradient shows until it is ready.
const ShaderBackdrop = lazy(() => import('./ShaderBackdrop.jsx'));

const current = () => document.documentElement.dataset.backdrop || 'animated';

export default function Backdrop() {
  const [mode, setMode] = useState(current);
  useEffect(() => {
    const watch = new MutationObserver(() => setMode(current()));
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-backdrop'] });
    return () => watch.disconnect();
  }, []);
  const shader = mode === 'animated';
  return (
    <div className={`app-backdrop${shader ? ' has-shader' : ''}`} aria-hidden="true">
      {shader ? <Suspense fallback={null}><ShaderBackdrop /></Suspense> : null}
    </div>
  );
}

import React, { Suspense, lazy, memo, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { World } from "metaverse";
import type { Lesson } from "../types";
import { MetaverseStart } from "./MetaverseStart";
import { TunnelTransition } from "./TunnelTransition";

// The 3D world is a separate chunk. It is fetched when the button is hovered (or when the browser is idle), so by the
// time the tunnel ends it is already in memory and only its start-up work is left.
const load = () => import("metaverse");
const Metaverse = lazy(load);
export const preloadMetaverse = () => { void load(); };

type Props = {
  /** Increase to play the entrance and open the world. */
  trigger: number;
  lesson: Lesson | null;
  lang: string;
  /** A world already built from study-tool data (the Meta quiz). Wins over the lesson. */
  world?: World | null;
};

/** Reports "mounted and painted" after the world next to it has finished its (heavy) first render. */
const Ready: React.FC<{ onReady: () => void }> = ({ onReady }) => {
  useEffect(() => {
    // Effects run in order, so the world's own start-up has already finished. Two frames later it has been painted.
    const id = requestAnimationFrame(() => requestAnimationFrame(onReady));
    return () => cancelAnimationFrame(id);
  }, [onReady]);
  return null;
};

/**
 * tunnel  -> blocks assemble, you rush down them into a light
 * start   -> the world is behind a Start page
 * open    -> Start was pressed: the topic screen of the world
 *
 * All of this state lives here, not in App, so nothing else on the page re-renders while the animation plays.
 */
export const MetaverseLayer = memo(function MetaverseLayer({ trigger, lesson, lang, world }: Props) {
  const [phase, setPhase] = useState<"off" | "tunnel" | "start" | "open">("off");
  const [tunnel, setTunnel] = useState(false);
  const [ready, setReady] = useState(false);
  const last = useRef(0);

  useEffect(() => {
    if (trigger === last.current) return;
    last.current = trigger;
    preloadMetaverse();
    setReady(false);
    setPhase("tunnel");
    setTunnel(true);
  }, [trigger]);

  const leave = useCallback(() => { setPhase("off"); setTunnel(false); setReady(false); }, []);
  const covered = useCallback(() => setPhase("start"), []);
  const done = useCallback(() => setTunnel(false), []);
  const onReady = useCallback(() => setReady(true), []);
  const start = useCallback(() => setPhase("open"), []);

  if (phase === "off") return null;
  return createPortal(
    <>
      {(phase === "start" || phase === "open") && (
        <div className="mv-overlay" role="dialog" aria-label="Metaverse quiz world">
          <Suspense fallback={null}>
            <Metaverse lesson={lesson} lang={lang} world={world} onExit={leave} />
            <Ready onReady={onReady} />
          </Suspense>
        </div>
      )}
      {phase === "start" && ready && <MetaverseStart onStart={start} onBack={leave} />}
      {tunnel && <TunnelTransition onCovered={covered} release={ready} onDone={done} />}
    </>,
    document.body,
  );
});

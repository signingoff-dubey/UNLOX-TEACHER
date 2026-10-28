import { useEffect, useMemo, useRef } from "react";
import "@fontsource/chakra-petch/500.css";
import "@fontsource/chakra-petch/600.css";
import "@fontsource/chakra-petch/700.css";
import "@fontsource/figtree/400.css";
import "@fontsource/figtree/600.css";
import "@fontsource/figtree/700.css";
import { CSS, MARKUP } from "./ui";
import { startMetaverse, type StartOptions } from "./engine";
import { lessonToWorld, type LessonLike } from "./lessonToWorld";
import type { World } from "./types";

export type MetaverseProps = {
  /** A world that was already built (for example by the Meta quiz from every study tool). Wins over `lesson`. */
  world?: World | null;
  /** A generated lesson to walk through. Without one, the built-in Java, photosynthesis and water-cycle worlds are offered. */
  lesson?: LessonLike | null;
  /** Language track of the lesson to use. */
  lang?: string;
  /** Shows an Exit button and calls this when it is pressed. */
  onExit?: () => void;
  /** Builds a world for a topic typed in the world (the AI). Without it, only the ready-made worlds are offered. */
  onBuild?: StartOptions["onBuild"];
  /** Keeps points and purchases outside the browser as well. */
  store?: StartOptions["store"];
  /** Only the 3D scene is shown (the camera circles the world): the host has its own page on top, e.g. a Start page. */
  intro?: boolean;
};

/**
 * Mounts the 3D world inside a shadow root, so its styles never leak into the host page
 * and the host page's styles never leak into it.
 */
export default function Metaverse({ lesson, lang = "en", world: given, onExit, onBuild, store, intro = false }: MetaverseProps) {
  const host = useRef<HTMLDivElement>(null);
  const introRef = useRef(intro);
  introRef.current = intro;
  const exit = useRef(onExit);
  exit.current = onExit;
  const build = useRef(onBuild);
  build.current = onBuild;
  const world = useMemo(() => given ?? (lesson ? lessonToWorld(lesson, lang) : null), [given, lesson, lang]);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const root = el.shadowRoot ?? el.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${CSS}</style>${MARKUP}`;
    root.getElementById("app")?.classList.toggle("intro", introRef.current);
    const stop = startMetaverse(root, {
      extraWorlds: world ? { lesson: world } : {},
      onExit: exit.current ? () => exit.current?.() : undefined,
      onBuild: build.current ? (topic, progress) => build.current!(topic, progress) : undefined,
      store,
    });
    return () => {
      stop();
      root.innerHTML = "";
    };
  }, [world, store]);

  useEffect(() => {
    host.current?.shadowRoot?.getElementById("app")?.classList.toggle("intro", intro);       // the topic card fades in when the intro ends
  }, [intro]);

  return <div ref={host} style={{ width: "100%", height: "100%" }} />;
}

import { useEffect, useMemo, useRef } from "react";
import "@fontsource/chakra-petch/500.css";
import "@fontsource/chakra-petch/600.css";
import "@fontsource/chakra-petch/700.css";
import "@fontsource/figtree/400.css";
import "@fontsource/figtree/600.css";
import "@fontsource/figtree/700.css";
import { CSS, MARKUP } from "./ui";
import { startMetaverse } from "./engine";
import { lessonToWorld, type LessonLike } from "./lessonToWorld";

export type MetaverseProps = {
  /** A generated lesson to walk through. Without one, the built-in Java, photosynthesis and water-cycle worlds are offered. */
  lesson?: LessonLike | null;
  /** Language track of the lesson to use. */
  lang?: string;
  /** Shows an Exit button and calls this when it is pressed. */
  onExit?: () => void;
};

/**
 * Mounts the 3D world inside a shadow root, so its styles never leak into the host page
 * and the host page's styles never leak into it.
 */
export default function Metaverse({ lesson, lang = "en", onExit }: MetaverseProps) {
  const host = useRef<HTMLDivElement>(null);
  const exit = useRef(onExit);
  exit.current = onExit;
  const world = useMemo(() => (lesson ? lessonToWorld(lesson, lang) : null), [lesson, lang]);

  useEffect(() => {
    const el = host.current;
    if (!el) return;
    const root = el.shadowRoot ?? el.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${CSS}</style>${MARKUP}`;
    const stop = startMetaverse(root, {
      extraWorlds: world ? { lesson: world } : {},
      onExit: exit.current ? () => exit.current?.() : undefined,
    });
    return () => {
      stop();
      root.innerHTML = "";
    };
  }, [world]);

  return <div ref={host} style={{ width: "100%", height: "100%" }} />;
}

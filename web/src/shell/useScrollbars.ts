import { useEffect } from "react";

const HIDE_AFTER_MS = 900;

/** Scrollbars are hidden until something scrolls: the scrolling element (or the page) gets the class `is-scrolling` for a moment.
 *  The look is in styles/scroll.css. `scroll` does not bubble, so one capturing listener on the document sees them all. */
export function useScrollbars() {
  useEffect(() => {
    const timers = new WeakMap<Element, number>();
    const onScroll = (e: Event) => {
      const t = e.target;
      const el = t instanceof Element ? t : document.documentElement;
      el.classList.add("is-scrolling");
      window.clearTimeout(timers.get(el));
      timers.set(el, window.setTimeout(() => el.classList.remove("is-scrolling"), HIDE_AFTER_MS));
    };
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    return () => document.removeEventListener("scroll", onScroll, { capture: true });
  }, []);
}

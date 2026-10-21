import { useEffect } from "react";

const clamp = (v) => Math.min(1, Math.max(0, v));

// Writes a 0..1 scroll progress into the element's `--p` custom property (no re-renders).
//   "pass": 0 as the element enters the viewport, 1 as it leaves
//   "line": how far the element's top edge has travelled past 55% of the viewport
//   "pin":  progress through a tall section whose child is `position: sticky`
export default function useScrollProgress(ref, mode = "pass") {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { top, height } = el.getBoundingClientRect();
        const vh = globalThis.innerHeight;
        let p;
        if (mode === "pin") p = height > vh ? -top / (height - vh) : 1;
        else if (mode === "line") p = (vh * 0.55 - top) / height;
        else p = (vh - top) / (vh + height);
        el.style.setProperty("--p", clamp(p).toFixed(4));
      });
    };
    update();
    globalThis.addEventListener("scroll", update, { passive: true });
    globalThis.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      globalThis.removeEventListener("scroll", update);
      globalThis.removeEventListener("resize", update);
    };
  }, [ref, mode]);
}

import { useEffect, useState } from "react";

// Index of the child (matching `selector`) closest to the viewport centre, or -1 if none is near.
export default function useFocusedChild(containerRef, selector) {
  const [index, setIndex] = useState(-1);

  useEffect(() => {
    const update = () => {
      const items = [
        ...(containerRef.current?.querySelectorAll(selector) ?? []),
      ];
      const mid = innerHeight / 2;
      let best = -1,
        bestDist = Infinity;
      items.forEach((el, i) => {
        const b = el.getBoundingClientRect();
        const d = Math.abs((b.top + b.bottom) / 2 - mid);
        if (d < bestDist) {
          bestDist = d;
          best = i;
        }
      });
      setIndex(bestDist < innerHeight * 0.6 ? best : -1);
    };
    update();
    addEventListener("scroll", update, { passive: true });
    addEventListener("resize", update);
    return () => {
      removeEventListener("scroll", update);
      removeEventListener("resize", update);
    };
  }, [containerRef, selector]);

  return index;
}

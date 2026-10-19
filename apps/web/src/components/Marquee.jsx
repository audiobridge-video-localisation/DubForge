import { useEffect, useRef, useState } from "react";
import { marqueeWords } from "../data/content.js";

const REPEATS = 6;
const words = Array.from({ length: REPEATS }, () => marqueeWords).flat();

// Slides left forever; the word nearest the viewport centre is highlighted.
export default function Marquee() {
  const track = useRef(null);
  const [active, setActive] = useState(-1);

  useEffect(() => {
    let x = 0,
      last = performance.now(),
      raf,
      current = -1;
    const tick = (now) => {
      x -= (now - last) * 0.04; // ~40px/s
      last = now;
      const loop = track.current.scrollWidth / REPEATS;
      if (-x > loop) x += loop;
      track.current.style.transform = `translateX(${x}px)`;

      let best = -1,
        bestDist = Infinity;
      [...track.current.children].forEach((s, i) => {
        const b = s.getBoundingClientRect();
        const d = Math.abs((b.left + b.right) / 2 - innerWidth / 2);
        if (d < bestDist) {
          bestDist = d;
          best = i;
        }
      });
      if (best !== current) {
        current = best;
        setActive(best);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="marquee">
      <div className="mtrack" ref={track}>
        {words.map((w, i) => (
          <span key={i} className={i === active ? "on" : ""}>
            {w}
          </span>
        ))}
      </div>
    </div>
  );
}

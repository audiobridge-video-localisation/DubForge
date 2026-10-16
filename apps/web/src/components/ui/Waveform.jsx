import { useEffect, useRef } from "react";
import "./Waveform.css";

// Bars ease toward random targets every frame while `live`, otherwise rest as dots.
// Heights are written to CSS variables directly so animation never re-renders React.
export default function Waveform({ live, bars = 12 }) {
  const wrap = useRef(null);
  const liveRef = useRef(live);
  liveRef.current = live;

  useEffect(() => {
    const els = [...wrap.current.children];
    const val = Array(bars).fill(0.15);
    const tgt = Array(bars).fill(0.15);
    let nextPick = 0,
      raf;

    const frame = (t) => {
      if (t > nextPick) {
        nextPick = t + 90;
        let a = Math.random(); // neighbours share a trend so it reads as speech
        for (let k = 0; k < bars; k++) {
          a = a * 0.55 + Math.random() * 0.45;
          const centre = 1 - (Math.abs(k - (bars - 1) / 2) / (bars / 2)) * 0.5;
          tgt[k] = liveRef.current
            ? Math.max(0.15, Math.min(1, a * centre * 1.5))
            : 0.15;
        }
      }
      els.forEach((el, k) => {
        val[k] += (tgt[k] - val[k]) * 0.28;
        el.style.setProperty("--h", val[k].toFixed(3));
      });
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [bars]);

  return (
    <div ref={wrap} className={`wbars ${live ? "live" : ""}`}>
      {Array.from({ length: bars }, (_, i) => (
        <i key={i} />
      ))}
    </div>
  );
}

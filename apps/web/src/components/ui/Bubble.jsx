import { useEffect, useId, useRef, useState } from "react";
import useTypewriter from "../../hooks/useTypewriter.js";
import "./Bubble.css";

// Speech-bubble outline: rounded box with a small tail at the bottom-right.
function bubblePath(w, h) {
  const r = Math.min(26, h / 2);
  const tx = w - r;
  return [
    `M${r},0 H${w - r} A${r},${r} 0 0 1 ${w},${r}`,
    `V${h - r} A${r},${r} 0 0 1 ${w - r},${h}`,
    `Q${tx + 3},${h + 5} ${tx + 11},${h + 10}`,
    `Q${tx - 8},${h + 9} ${tx - 22},${h}`,
    `H${r} A${r},${r} 0 0 1 0,${h - r}`,
    `V${r} A${r},${r} 0 0 1 ${r},0 Z`,
  ].join(" ");
}

// The outline is recomputed whenever the box resizes, so it always hugs the typed text.
export default function Bubble({ phrases }) {
  const el = useRef(null);
  const id = useId().replace(/:/g, "");
  const [size, setSize] = useState({ w: 0, h: 0 });
  const text = useTypewriter(phrases);

  useEffect(() => {
    const ro = new ResizeObserver(() => {
      const { width, height } = el.current.getBoundingClientRect();
      setSize({ w: width, h: height });
    });
    ro.observe(el.current);
    return () => ro.disconnect();
  }, []);

  const { w, h } = size;
  return (
    <div className="bubble" ref={el}>
      <svg
        className="shape"
        width={w}
        height={h + 12}
        viewBox={`0 0 ${w} ${h + 12}`}
      >
        <defs>
          <linearGradient id={`f${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#d6e6ff" />
            <stop offset=".42" stopColor="#9ec5ff" />
            <stop offset="1" stopColor="#d2f1f7" />
          </linearGradient>
          <linearGradient id={`s${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#221898" />
            <stop offset="1" stopColor="#626262" />
          </linearGradient>
          <filter id={`d${id}`} x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow
              dx="0"
              dy="8"
              stdDeviation="5"
              floodColor="#000"
              floodOpacity=".11"
            />
          </filter>
        </defs>
        <path
          d={bubblePath(w, h)}
          filter={`url(#d${id})`}
          fill={`url(#f${id})`}
          stroke={`url(#s${id})`}
          strokeWidth="1"
          strokeLinejoin="round"
        />
      </svg>
      <span className="text">
        {text}
        <span className="caret" />
      </span>
      <div className="gloss" />
    </div>
  );
}

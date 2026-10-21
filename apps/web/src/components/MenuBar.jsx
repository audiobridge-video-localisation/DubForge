import { useEffect, useRef, useState } from "react";
import useClock from "../hooks/useClock.js";
import { brand, navLinks } from "../data/content.js";
import { Bluetooth, Headphones, Wifi } from "./ui/Icons.jsx";
import SmartLink from "./ui/SmartLink.jsx";
import "./MenuBar.css";

const clamp = (v, min = -1, max = 1) => Math.max(min, Math.min(max, v));
const between = (a, b) => a + Math.random() * (b - a);

// The lower lid of the logo's eye is a tiny waveform. `bump` (0..1) is where along it
// the cursor is pointing and `energy` how strongly it reacts; `t` keeps it breathing.
const WAVE_POINTS = 9;
function wave(energy, bump, t) {
  let d = "M6 16";
  for (let i = 1; i < WAVE_POINTS - 1; i++) {
    const at = i / (WAVE_POINTS - 1);
    const lift = Math.exp(-((at - bump) ** 2) / 0.05);
    const amp =
      1 + 1.2 * (0.5 + 0.5 * Math.sin(t * 2.2 + i)) + 4 * energy * lift;
    const x = 6 + at * 52;
    const y = 21 + (i % 2 ? amp : -amp * 0.45);
    d += ` L${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return `${d} L58 16`;
}

// A one-eyed monoline mark. While the cursor moves, it turns toward it and the pupil
// looks right at it; the lower lid ripples where you point. When the cursor goes
// still the eye gets bored and glances around on its own.
function Logo() {
  const link = useRef(null);
  const glyph = useRef(null);
  const pupil = useRef(null);
  const lower = useRef(null);

  useEffect(() => {
    if (globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches)
      return;
    // `aim` is where the cursor says the mark should be; `now` eases toward it
    const aim = { x: 0, y: 0, bump: 0.5, energy: 0.25 };
    const now = { x: 0, y: 0, bump: 0.5, energy: 0.25 };
    const eye = { x: 0, y: 0, gx: 0, gy: 0 };
    let lastMove = -1e9;
    let nextGlance = 0;
    let frame = 0;

    const onMove = (e) => {
      const box = link.current.getBoundingClientRect();
      const dx = e.clientX - (box.left + box.width / 2);
      const dy = e.clientY - (box.top + box.height / 2);
      aim.x = clamp(dx / 260);
      aim.y = clamp(dy / 160);
      aim.bump = 0.5 + clamp(dx / 220) * 0.45;
      aim.energy = 0.3 + 0.7 * clamp(1 - Math.hypot(dx, dy) / 560, 0, 1);
      lastMove = globalThis.performance.now();
    };
    const onLeave = () => {
      aim.x = aim.y = 0;
      aim.bump = 0.5;
      aim.energy = 0.25;
      lastMove = -1e9;
    };
    const onOut = (e) => {
      if (!e.relatedTarget) onLeave();
    };

    const tick = (ms) => {
      const t = ms / 1000;
      now.x += (aim.x - now.x) * 0.14;
      now.y += (aim.y - now.y) * 0.14;
      now.bump += (aim.bump - now.bump) * 0.16;
      now.energy += (aim.energy - now.energy) * 0.12;
      glyph.current.style.transform = `translate(${now.x * 4}px, ${now.y * 3}px) rotateX(${-now.y * 18}deg) rotateY(${now.x * 22}deg)`;

      // gaze: look at the cursor while it moves, otherwise dart around
      if (ms - lastMove < 2200) {
        eye.gx = aim.x;
        eye.gy = aim.y;
      } else if (ms > nextGlance) {
        eye.gx = between(-1, 1);
        eye.gy = between(-0.8, 0.8);
        nextGlance = ms + between(600, 2000);
      }
      eye.x += (eye.gx - eye.x) * 0.3;
      eye.y += (eye.gy - eye.y) * 0.3;
      pupil.current.style.transform = `translate(${eye.x * 11}px, ${eye.y * 2.6}px)`;

      lower.current.setAttribute("d", wave(now.energy, now.bump, t));
      frame = requestAnimationFrame(tick);
    };

    globalThis.addEventListener("pointermove", onMove, { passive: true });
    globalThis.addEventListener("pointerup", onLeave);
    globalThis.document.addEventListener("mouseout", onOut);
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
      globalThis.removeEventListener("pointermove", onMove);
      globalThis.removeEventListener("pointerup", onLeave);
      globalThis.document.removeEventListener("mouseout", onOut);
    };
  }, []);

  return (
    <a className="logo-link" href="#" ref={link} aria-label={`${brand} home`}>
      <svg
        className="logo-glyph"
        viewBox="0 0 64 32"
        ref={glyph}
        aria-hidden="true"
      >
        <defs>
          <clipPath id="logo-eye-clip">
            <ellipse cx="32" cy="13" rx="24" ry="11" />
          </clipPath>
        </defs>
        <g className="logo-lid">
          <path className="logo-line" d="M6 16C12 -4 52 -4 58 16" />
          <path className="logo-line" ref={lower} d={wave(0.25, 0.5, 0)} />
        </g>
        <g clipPath="url(#logo-eye-clip)">
          <circle
            className="logo-pupil"
            ref={pupil}
            cx="32"
            cy="12.5"
            r="5.2"
          />
        </g>
      </svg>
    </a>
  );
}

export default function MenuBar() {
  const time = useClock();
  const [scrolled, setScrolled] = useState(false);
  const [hover, setHover] = useState({ left: 0, width: 0, on: false });

  useEffect(() => {
    const onScroll = () => setScrolled(globalThis.scrollY > 8);
    onScroll();
    globalThis.addEventListener("scroll", onScroll, { passive: true });
    return () => globalThis.removeEventListener("scroll", onScroll);
  }, []);

  // one highlight that glides to whichever link the cursor is on
  const glideTo = (e) =>
    setHover({
      left: e.currentTarget.offsetLeft,
      width: e.currentTarget.offsetWidth,
      on: true,
    });

  return (
    <header className={`menubar ${scrolled ? "scrolled" : ""}`}>
      <div className="left">
        <nav
          className="menu-items"
          onMouseLeave={() => setHover((h) => ({ ...h, on: false }))}
        >
          <i
            className={`hover-glider ${hover.on ? "on" : ""}`}
            style={{ left: hover.left, width: hover.width }}
            aria-hidden="true"
          />
          <a className="brand" href="#">
            {brand}
          </a>
          {navLinks.map((l) => (
            <a
              key={l.label}
              href={l.href}
              onMouseEnter={glideTo}
              onFocus={glideTo}
            >
              {l.label}
            </a>
          ))}
        </nav>
      </div>

      <Logo />

      <div className="right">
        <div className="status">
          <Wifi />
          <Headphones />
          <Bluetooth />
          <span className="time">{time}</span>
        </div>
        <SmartLink className="getbtn" href="/app">
          open workspace <span aria-hidden="true">↗</span>
        </SmartLink>
      </div>
    </header>
  );
}

import { useEffect, useRef, useState } from "react";
import DeskWindow from "./ui/DeskWindow.jsx";
import Button from "./ui/Button.jsx";
import Draggable from "./ui/Draggable.jsx";
import { langs } from "../data/langs.js";
import {
  onDubRequest,
  setDeskLang,
  useDeskLang,
} from "../hooks/useDeskLang.js";
import "./Hero.css";

// Drop scene-04.mov on a folder and the whole desk re-localizes.
const rows = [
  [
    "Sophia",
    "It still feels like yesterday.",
    {
      es: "Todavía se siente como ayer.",
      fr: "On dirait que c'était hier.",
      de: "Es fühlt sich an wie gestern.",
      ja: "まるで昨日のことのようだ。",
    },
  ],
  [
    "Sophia",
    "A city that changes in quiet ways.",
    {
      es: "Una ciudad que cambia de formas silenciosas.",
      fr: "Une ville qui change en silence.",
      de: "Eine Stadt, die sich leise verändert.",
      ja: "静かに変わっていく街。",
    },
  ],
  [
    "Marcus",
    "You notice it more when you leave.",
    {
      es: "Lo notas más cuando te vas.",
      fr: "On le remarque plus en partant.",
      de: "Man merkt es erst, wenn man geht.",
      ja: "離れて初めて気づく。",
    },
  ],
  [
    "Sophia",
    "But it always feels like home to me.",
    {
      es: "Pero siempre se siente como casa para mí.",
      fr: "Mais pour moi, c'est toujours comme à la maison.",
      de: "Aber für mich fühlt es sich immer nach Zuhause an.",
      ja: "それでも、ここはいつも我が家のよう。",
    },
  ],
];

// Everything is placed on a fixed 1440px canvas.
const folderSpots = {
  es: { x: 378, y: 255 },
  fr: { x: 405, y: 385 },
  de: { x: 1130, y: 262 },
  ja: { x: 1110, y: 478 },
};
const trinkets = [
  { type: "hello", x: 395, y: 28, rot: 4 },
  { type: "speaker", x: 1245, y: 150, rot: -7 },
  { type: "translate", x: 845, y: 150, rot: -4 },
  { type: "bars", x: 1215, y: 640, rot: 5 },
  { type: "kao", text: "\\(^o^)/", x: 385, y: 135, rot: -8, size: 26 },
  { type: "kao", text: "♪ ~(˘▾˘~)", x: 790, y: 95, rot: 6, size: 20 },
  { type: "kao", text: "{ ^‿^ }", x: 1110, y: 395, rot: 7, size: 24 },
  { type: "kao", text: "(¬‿¬)", x: 190, y: 365, rot: -7, size: 20 },
  {
    type: "note",
    text: "drag scene-04.mov onto a folder",
    x: 60,
    y: 610,
    rot: -4,
  },
];

function Wave({ purple = false, draw = false }) {
  return (
    <div
      className={`desk-wave ${purple ? "purple" : ""} ${draw ? "wave-draw" : ""}`}
      aria-hidden="true"
    >
      {Array.from({ length: 72 }, (_, i) => (
        <i
          key={i}
          style={{
            height: `${12 + ((i * 23 + i * i) % 80)}%`,
            animationDelay: `${i * -0.07}s`,
          }}
        />
      ))}
    </div>
  );
}

function Trinket({ item, lang }) {
  const l = langs[lang];
  return (
    <>
      {item.type === "hello" && (
        <div className="sticker sticker-hello" key={lang}>
          {l.hello}
        </div>
      )}
      {item.type === "speaker" && (
        <div className="sticker sticker-speaker">
          <span className="avatar" key={lang}>
            S
          </span>
          <div>
            <b>Sophia</b>
            <small>voice kept · {l.code}</small>
          </div>
        </div>
      )}
      {item.type === "translate" && (
        <div className="sticker sticker-translate">
          <b>文</b>
          <i>A</i>
        </div>
      )}
      {item.type === "bars" && (
        <div className="sticker sticker-bars" aria-hidden="true">
          {[40, 75, 55, 95, 60, 85, 45, 70, 35].map((h, i) => (
            <i key={i} style={{ height: `${h}%` }} />
          ))}
        </div>
      )}
      {item.type === "kao" && (
        <div className="kao" style={{ fontSize: item.size }}>
          {item.text}
        </div>
      )}
      {item.type === "note" && <div className="note-sticky">{item.text}</div>}
    </>
  );
}

const steps = ["Upload", "Review", "Translate", "Dub", "Export"];
const navItems = [
  ["▤", "Transcript"],
  ["♧", "Speakers"],
  ["文", "Translation"],
  ["♩", "Voice & Dub"],
  ["↗", "Export"],
];
// which sidebar section the demo is "in" at each phase
const navAt = [0, 2, 3, 0, 4];
const captions = [
  "Review source",
  "Translate",
  "Match voice & timing",
  "Review approved",
  "Demo complete",
];

function Workspace({ phase, lang, running, onReplay, onPause, onStep }) {
  const l = langs[lang];
  const nav = navAt[phase];
  return (
    <div
      className={`studio-preview phase-${phase}`}
      style={{ "--p": phase / 4 }}
    >
      <aside className="studio-sidebar">
        <small>PROJECT</small>
        <strong>A brighter tomorrow</strong>
        <span>Video · 00:28 · Scene 04</span>
        <div className="studio-nav">
          <i className="nav-glider" style={{ "--n": nav }} aria-hidden="true" />
          {navItems.map(([icon, label], i) => (
            <div className={i === nav ? "on" : ""} key={label}>
              <span>{icon}</span>
              {label}
            </div>
          ))}
        </div>
        <span className="studio-demo">Demo project</span>
      </aside>
      <div className="studio-editor">
        <div className="studio-steps">
          {steps.map((step, i) => (
            <button
              type="button"
              className={i === Math.min(phase + 1, 4) ? "active" : ""}
              key={step}
              onClick={() => onStep(i)}
            >
              <b>{i < Math.min(phase + 1, 4) ? "✓" : i + 1}</b>
              {step}
            </button>
          ))}
          <a href="/app">Open editor ↗</a>
        </div>
        <div className="studio-table">
          <div className="studio-row studio-head">
            <span>#</span>
            <span>Speaker</span>
            <span>English (source)</span>
            <span>{l.name} (localized)</span>
            <span>Status</span>
          </div>
          {rows.map(([speaker, source, target], i) => (
            <div
              className={`studio-row demo-row ${i === 0 ? "lead" : ""}`}
              style={{ "--r": i }}
              key={source}
            >
              <span className="row-number">00{i + 1}</span>
              <span>
                <b
                  className={`speaker-tag ${speaker === "Marcus" ? "blue" : ""}`}
                >
                  {speaker}
                </b>
              </span>
              <span className="demo-source">{source}</span>
              <span className="demo-target">
                <span className="swap" key={lang} lang={lang}>
                  {target[lang]}
                </span>
              </span>
              <span
                className="approved"
                role="img"
                aria-label={phase < 3 ? "Awaiting review" : "Approved"}
              >
                ✓
              </span>
            </div>
          ))}
        </div>
        <div className="studio-timeline">
          <div className="timeline-ticks">
            <span>00:00</span>
            <span>00:05</span>
            <span>00:10</span>
            <span>00:15</span>
            <span>00:20</span>
          </div>
          <div className="timeline-track">
            <span>SOPHIA (EN)</span>
            <div className="wave-lane">
              <Wave purple />
            </div>
          </div>
          <div className="timeline-track">
            <span>SOPHIA ({l.code})</span>
            <div className="wave-lane">
              <Wave draw key={lang} />
            </div>
          </div>
          <div className="timeline-cursor" />
        </div>
        <div className="studio-transport">
          <button
            type="button"
            className="demo-control"
            onClick={phase === 4 ? onReplay : onPause}
            aria-label={
              phase === 4
                ? "Replay localization demo"
                : running
                  ? "Pause localization demo"
                  : "Resume localization demo"
            }
          >
            {phase === 4 ? "↻" : running ? "Ⅱ" : "▶"}
          </button>
          <span className="demo-caption" aria-live="polite" key={phase}>
            {phase === 1 ? `Translate to ${l.name}` : captions[phase]}
          </span>
          <div className="transport-rail">
            <i />
          </div>
          {["MP4", "SRT", "VTT"].map((format) => (
            <span className={`fmt ${phase === 4 ? "ready" : ""}`} key={format}>
              {format}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Hero() {
  const section = useRef(null);
  const dubTimer = useRef(0);
  const [phase, setPhase] = useState(0);
  const [visible, setVisible] = useState(false);
  const [playing, setPlaying] = useState(true);
  const lang = useDeskLang();
  const [busy, setBusy] = useState(null);
  const [over, setOver] = useState(null);
  const [reduced, setReduced] = useState(
    () => globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const running = visible && playing && phase < 4 && !reduced;
  const shown = reduced ? 4 : phase;
  const l = langs[lang];
  useEffect(() => {
    const media = globalThis.matchMedia("(prefers-reduced-motion: reduce)");
    const change = () => setReduced(media.matches);
    media.addEventListener("change", change);
    const observer = new IntersectionObserver(
      ([entry]) => setVisible(entry.isIntersecting),
      { threshold: 0.15 },
    );
    observer.observe(section.current);
    return () => {
      media.removeEventListener("change", change);
      observer.disconnect();
      globalThis.clearTimeout(dubTimer.current);
    };
  }, []);
  useEffect(() => {
    if (!running) return;
    const timer = globalThis.setTimeout(
      () => setPhase((value) => Math.min(value + 1, 4)),
      1700,
    );
    return () => globalThis.clearTimeout(timer);
  }, [running, phase]);
  const replay = () => {
    setPhase(0);
    setPlaying(true);
  };
  const jump = (step) => {
    setPhase(Math.max(step - 1, 0));
    setPlaying(true);
  };

  // The language folder whose centre sits inside the dragged window, if any.
  const folderUnder = (el) => {
    const box = el.getBoundingClientRect();
    for (const folder of section.current.querySelectorAll("[data-drop]")) {
      const f = folder.getBoundingClientRect();
      const cx = f.left + f.width / 2;
      const cy = f.top + f.height / 2;
      if (cx > box.left && cx < box.right && cy > box.top && cy < box.bottom)
        return folder.dataset.drop;
    }
    return null;
  };
  const dub = (next) => {
    if (next === lang || next === busy) return;
    globalThis.clearTimeout(dubTimer.current);
    setBusy(next);
    dubTimer.current = globalThis.setTimeout(
      () => {
        setDeskLang(next);
        setBusy(null);
        setPhase(1);
        setPlaying(true);
      },
      reduced ? 0 : 900,
    );
  };
  const dubRef = useRef(dub);
  useEffect(() => {
    dubRef.current = dub;
  });
  useEffect(() => onDubRequest((next) => dubRef.current(next)), []);
  const fileAway = (el, x, y) => {
    el.style.transition = reduced
      ? "none"
      : "left 450ms cubic-bezier(0.2, 1.3, 0.4, 1), top 450ms cubic-bezier(0.2, 1.3, 0.4, 1)";
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    globalThis.setTimeout(() => (el.style.transition = ""), 500);
  };

  // Small windows, each a little DubForge file with its name underneath.
  const clips = [
    {
      file: "scene-04.mov",
      ext: "MOV",
      x: 60,
      y: 80,
      w: 270,
      dragProps: {
        onPositionChange: (_, el) => setOver(folderUnder(el)),
        onDrop: (el) => {
          const target = folderUnder(el);
          setOver(null);
          if (!target) return;
          dub(target);
          fileAway(el, 60, 80);
        },
      },
      body: (
        <div className="mini-video">
          <img
            src="/assets/scene-04-landscape.jpg"
            alt="An alpine lake beneath misty mountains, a sample scene for localization"
            width="800"
            height="533"
            draggable="false"
          />
          <span className="mini-chip">EN → {langs[busy ?? lang].code}</span>
          <span className="dub-stamp" key={lang}>
            dubbed ✓
          </span>
          <span className="mini-sub" key={`sub-${lang}`} lang={lang}>
            {rows[0][2][lang]}
          </span>
          {busy && (
            <span className="dub-bar">
              <i />
              dubbing to {langs[busy].name}…
            </span>
          )}
        </div>
      ),
    },
    {
      file: "transcript.txt",
      ext: "TXT",
      x: 520,
      y: 8,
      w: 250,
      body: (
        <div className="mini-text">
          <p>
            <time>00:00</time> <b>SOPHIA</b>
            <br />
            {rows[0][1]}
          </p>
          <p className="tr" key={lang} lang={lang}>
            <time>→ {l.code}</time>
            <br />
            {rows[0][2][lang]}
          </p>
          <p>
            <time>00:04</time> <b>MARCUS</b>
            <br />
            {rows[1][1]}
          </p>
        </div>
      ),
    },
    {
      file: `sophia-${lang}.wav`,
      ext: "WAV",
      x: 1000,
      y: 70,
      w: 255,
      body: (
        <div className="mini-wave">
          <Wave />
          <span>
            <b>{l.code}</b> voice matched · 00:28
          </span>
        </div>
      ),
    },
    {
      file: "approve-all.app",
      ext: "APP",
      x: 70,
      y: 395,
      w: 270,
      body: (
        <div className="mini-dialog">
          <span className="dialog-icon" aria-hidden="true">
            ✓
          </span>
          <div>
            <strong>
              {shown >= 3 ? "All 4 lines approved" : "Approve 4 lines?"}
            </strong>
            <small>Export unlocks once every line is approved.</small>
            <div className="dialog-actions">
              <span>Review</span>
              <span className="go">{shown >= 3 ? "Approved" : "Approve"}</span>
            </div>
          </div>
        </div>
      ),
    },
    {
      file: `${l.folder} / export`,
      ext: "ZIP",
      x: 1195,
      y: 355,
      w: 215,
      body: (
        <div className="mini-files">
          {[
            ["MP4", `dubbed.${lang}.mp4`],
            ["MP3", `dubbed.${lang}.mp3`],
            ["SRT", `subtitles.${lang}.srt`],
            ["VTT", `captions.${lang}.vtt`],
          ].map(([ext, name]) => (
            <div key={ext}>
              <span className={`format-icon format-${ext.toLowerCase()}`}>
                {ext}
              </span>
              {name}
            </div>
          ))}
        </div>
      ),
    },
  ];

  return (
    <section
      ref={section}
      style={{ "--lang": l.color, "--lang-deep": l.deep }}
      className={`hero ${visible ? "in-view" : ""} ${running ? "demo-running" : ""} ${running && phase === 2 ? "audio-playing" : ""}`}
    >
      <div className="canvas">
        {clips.map((clip, i) => (
          <Draggable
            key={clip.ext}
            x={clip.x}
            y={clip.y}
            className="mini"
            style={{ width: clip.w, "--i": i }}
            {...clip.dragProps}
          >
            <DeskWindow ext={clip.ext}>{clip.body}</DeskWindow>
            <div className="cap">{clip.file}</div>
          </Draggable>
        ))}
        {trinkets.map((item, i) => (
          <Draggable
            key={i}
            x={item.x}
            y={item.y}
            rot={item.rot}
            className="trinket"
            style={{ "--i": i + clips.length }}
          >
            <Trinket item={item} lang={lang} />
          </Draggable>
        ))}
        {Object.entries(langs).map(([key, entry], i) => (
          <Draggable
            key={key}
            x={folderSpots[key].x}
            y={folderSpots[key].y}
            className="trinket folder-spot"
            style={{ "--i": i + clips.length + trinkets.length }}
          >
            <div
              className={`folder-wrap ${over === key ? "over" : ""} ${lang === key ? "active" : ""}`}
              data-drop={key}
            >
              <div className="folder" />
              <span>{entry.folder}</span>
            </div>
          </Draggable>
        ))}

        <div className="hero-heading">
          <h1>DubForge</h1>
          <p>
            localize every voice, without losing the <em>feeling</em>
          </p>
          <div className="ctas">
            <Button variant="primary" href="/app">
              open workspace
            </Button>
            <Button variant="secondary" href="#feat">
              see the workflow
            </Button>
          </div>
          <small>upload · review · translate · dub · export</small>
        </div>

        <DeskWindow
          ext="DF"
          className="studio-window"
          title="DubForge / localization desk"
        >
          <Workspace
            phase={shown}
            lang={lang}
            running={running}
            onReplay={replay}
            onStep={jump}
            onPause={() => setPlaying((value) => !value)}
          />
        </DeskWindow>
      </div>
    </section>
  );
}

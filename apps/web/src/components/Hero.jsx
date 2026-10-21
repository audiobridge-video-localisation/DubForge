import { useEffect, useRef, useState } from "react";
import MacWindow from "./ui/MacWindow.jsx";
import Button from "./ui/Button.jsx";
import Draggable from "./ui/Draggable.jsx";
import "./Hero.css";

const rows = [
  ["Sophia", "It still feels like yesterday.", "Todavía se siente como ayer."],
  [
    "Sophia",
    "A city that changes in quiet ways.",
    "Una ciudad que cambia de formas silenciosas.",
  ],
  [
    "Marcus",
    "You notice it more when you leave.",
    "Lo notas más cuando te vas.",
  ],
  [
    "Sophia",
    "But it always feels like home to me.",
    "Pero siempre se siente como casa para mí.",
  ],
];

// Everything is placed on a fixed 1440px canvas.
const trinkets = [
  {
    type: "tag",
    tone: "blue",
    hello: ["HOLA", "me llamo"],
    name: "Sophia",
    x: 395,
    y: 28,
    rot: 4,
  },
  {
    type: "tag",
    tone: "red",
    hello: ["BONJOUR", "je m'appelle"],
    name: "Marcus",
    x: 1245,
    y: 150,
    rot: -7,
  },
  { type: "kao", text: "\\(^o^)/", x: 385, y: 135, rot: -8, size: 26 },
  { type: "kao", text: "♪ ~(˘▾˘~)", x: 790, y: 95, rot: 6, size: 20 },
  { type: "kao", text: "{ ^‿^ }", x: 1110, y: 395, rot: 7, size: 24 },
  { type: "kao", text: "(¬‿¬)", x: 365, y: 455, rot: -7, size: 20 },
  { type: "folder", label: "es-ES", x: 378, y: 255 },
  { type: "folder", label: "de-DE", x: 1130, y: 262 },
  { type: "folder", label: "ja-JP", x: 1110, y: 478 },
  { type: "tile", kind: "translate", x: 845, y: 150, rot: -4 },
  { type: "tile", kind: "mic", x: 120, y: 640, rot: -6 },
  { type: "note", text: "keep the timing natural", x: 1205, y: 625, rot: 5 },
];

function Wave({ purple = false }) {
  return (
    <div className={`desk-wave ${purple ? "purple" : ""}`} aria-hidden="true">
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

function Trinket({ item }) {
  return (
    <>
      {item.type === "tag" && (
        <div className={`tag ${item.tone}`}>
          <div className="hd">
            {item.hello[0]}
            <br />
            {item.hello[1]}
          </div>
          <div className="nm">{item.name}</div>
        </div>
      )}
      {item.type === "kao" && (
        <div className="kao" style={{ fontSize: item.size }}>
          {item.text}
        </div>
      )}
      {item.type === "folder" && (
        <div className="folder-wrap">
          <div className="folder" />
          <span>{item.label}</span>
        </div>
      )}
      {item.type === "tile" && (
        <div className={`tile tile-${item.kind}`}>
          {item.kind === "translate" ? (
            <>
              <b>文</b>
              <i>A</i>
            </>
          ) : (
            <span>♪</span>
          )}
        </div>
      )}
      {item.type === "note" && <div className="note-sticky">{item.text}</div>}
    </>
  );
}

function Workspace({ phase, running, onReplay, onPause }) {
  return (
    <div className={`studio-preview phase-${phase}`}>
      <aside className="studio-sidebar">
        <small>PROJECT</small>
        <strong>A brighter tomorrow</strong>
        <span>Video · 00:28 · Scene 04</span>
        <div className="studio-nav">
          {[
            "Transcript",
            "Speakers",
            "Translation",
            "Voice & Dub",
            "Export",
          ].map((label, i) => (
            <div className={i === 0 ? "selected" : ""} key={label}>
              <span>{["▤", "♧", "文", "♩", "↗"][i]}</span>
              {label}
            </div>
          ))}
        </div>
        <span className="studio-demo">Demo project</span>
      </aside>
      <div className="studio-editor">
        <div className="studio-steps">
          {["Upload", "Review", "Translate", "Dub", "Export"].map((step, i) => (
            <span
              className={i === Math.min(phase + 1, 4) ? "active" : ""}
              key={step}
            >
              <b>{i < 2 ? "✓" : i + 1}</b>
              {step}
            </span>
          ))}
          <a href="/app">Open editor ↗</a>
        </div>
        <div className="studio-table">
          <div className="studio-row studio-head">
            <span>#</span>
            <span>Speaker</span>
            <span>English (source)</span>
            <span>Spanish (localized)</span>
            <span>Status</span>
          </div>
          {rows.map(([speaker, source, target], i) => (
            <div
              className={`studio-row ${i === 0 ? "demo-row" : ""}`}
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
              <span className="demo-target">{target}</span>
              <span
                className="approved"
                aria-label={
                  i === 0 && phase < 3 ? "Awaiting review" : "Approved"
                }
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
            <Wave purple />
          </div>
          <div className="timeline-track">
            <span>SOPHIA (ES)</span>
            <Wave />
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
          <span className="demo-caption" aria-live="polite">
            {
              [
                "Review source",
                "Translate to Spanish",
                "Match voice & timing",
                "Review approved",
                "Demo complete",
              ][phase]
            }
          </span>
          <div className="transport-rail">
            <i />
          </div>
          <span>MP4</span>
          <span>SRT</span>
          <span>VTT</span>
        </div>
      </div>
    </div>
  );
}

export default function Hero() {
  const section = useRef(null);
  const [phase, setPhase] = useState(0);
  const [visible, setVisible] = useState(false);
  const [playing, setPlaying] = useState(true);
  const [reduced, setReduced] = useState(
    () => globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const running = visible && playing && phase < 4 && !reduced;
  const shown = reduced ? 4 : phase;
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

  // Small windows, each a little DubForge file with its name underneath.
  const clips = [
    {
      file: "scene-04.mov",
      x: 60,
      y: 80,
      w: 270,
      body: (
        <div className="mini-video">
          <img
            src="/assets/scene-04-landscape.jpg"
            alt="An alpine lake beneath misty mountains, a sample scene for localization"
            width="800"
            height="533"
            draggable="false"
          />
          <span className="mini-chip">EN → ES</span>
          <span className="mini-sub">Todavía se siente como ayer.</span>
        </div>
      ),
    },
    {
      file: "transcript.txt",
      x: 520,
      y: 40,
      w: 235,
      body: (
        <div className="mini-text">
          <p>
            <time>00:00</time> <b>SOPHIA</b>
            <br />
            It still feels like yesterday.
          </p>
          <p>
            <time>00:04</time> <b>MARCUS</b>
            <br />A city that changes in quiet ways.
          </p>
        </div>
      ),
    },
    {
      file: "sophia-es.wav",
      x: 1000,
      y: 70,
      w: 255,
      body: (
        <div className="mini-wave">
          <Wave />
          <span>
            <b>ES</b> voice matched · 00:28
          </span>
        </div>
      ),
    },
    {
      file: "approve-all.app",
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
      file: "es-ES / export",
      x: 1195,
      y: 355,
      w: 215,
      body: (
        <div className="mini-files">
          {[
            ["MP4", "dubbed.mp4"],
            ["MP3", "dubbed.mp3"],
            ["SRT", "subtitles.srt"],
            ["VTT", "captions.vtt"],
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
      className={`hero ${visible ? "in-view" : ""} ${running ? "demo-running" : ""} ${running && phase === 2 ? "audio-playing" : ""}`}
    >
      <div className="canvas">
        {clips.map((clip, i) => (
          <Draggable
            key={clip.file}
            x={clip.x}
            y={clip.y}
            className="mini"
            style={{ width: clip.w, "--i": i }}
          >
            <MacWindow>{clip.body}</MacWindow>
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
            <Trinket item={item} />
          </Draggable>
        ))}

        <div className="hero-heading">
          <h1>DubForge</h1>
          <p>localize every voice, without losing the feeling</p>
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

        <MacWindow
          className="studio-window"
          title="DubForge / localization desk"
        >
          <Workspace
            phase={shown}
            running={running}
            onReplay={replay}
            onPause={() => setPlaying((value) => !value)}
          />
        </MacWindow>
      </div>
    </section>
  );
}

import { useState } from "react";
import MacWindow from "./ui/MacWindow.jsx";
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
const initial = [
  { x: 30, y: 110 },
  { x: 1130, y: 130 },
  { x: 32, y: 490 },
  { x: 1190, y: 590 },
  { x: 235, y: 460 },
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

function Workspace() {
  return (
    <div className="studio-preview">
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
        <span className="studio-demo">Demo project · drag to explore</span>
      </aside>
      <div className="studio-editor">
        <div className="studio-steps">
          {["Upload", "Review", "Translate", "Dub", "Export"].map((step, i) => (
            <span className={i === 2 ? "active" : ""} key={step}>
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
            <div className="studio-row" key={source}>
              <span className="row-number">00{i + 1}</span>
              <span>
                <b
                  className={`speaker-tag ${speaker === "Marcus" ? "blue" : ""}`}
                >
                  {speaker}
                </b>
              </span>
              <span>{source}</span>
              <span>{target}</span>
              <span className="approved" aria-label="Approved">
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
          <span>▶</span>
          <span>00:08 / 00:28</span>
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
  const [positions, setPositions] = useState(initial);
  const update = (i) => (position) =>
    setPositions((old) => old.map((p, index) => (index === i ? position : p)));
  const cards = [
    <>
      <div className="artifact-label">
        <span>SCENE 04</span>
        <span>ORIGINAL</span>
      </div>
      <div className="scene-art">
        <div className="scene-sun" />
        <div className="scene-mountain back" />
        <div className="scene-mountain" />
        <span>
          Same story.
          <br />A new audience.
        </span>
      </div>
      <div className="scene-caption">
        <span>▶ A brighter tomorrow</span>
        <span>00:28</span>
      </div>
    </>,
    <>
      <div className="artifact-label">
        <span>SOURCE AUDIO</span>
        <span>A001_C004.wav</span>
      </div>
      <Wave />
      <div className="artifact-foot">
        <span>00:00</span>
        <span>00:28</span>
      </div>
    </>,
    <>
      <div className="artifact-label">
        <span>EN → ES</span>
        <span>SUBTITLE PROOF</span>
      </div>
      <div className="proof">
        <small>EN · 00:00 – 00:03</small>
        <p>It still feels like yesterday.</p>
      </div>
      <div className="proof-arrow">↓</div>
      <div className="proof">
        <small>ES · 00:00 – 00:03</small>
        <p>Todavía se siente como ayer.</p>
      </div>
    </>,
    <>
      <div className="artifact-label">
        <span>VOICE MATCH</span>
        <span>PREVIEW</span>
      </div>
      <Wave purple />
      <div className="voice-approved">
        <b>✓</b>
        <div>
          Keep the original feeling<small>Tone · rhythm · pacing</small>
        </div>
      </div>
    </>,
  ];
  return (
    <section className="hero">
      <div className="canvas">
        <svg className="board-wires" viewBox="0 0 1440 1140" aria-hidden="true">
          {positions.slice(0, 4).map((p, i) => {
            const endX = positions[4].x + (i % 2 ? 960 : 0);
            const endY = positions[4].y + (i < 2 ? 70 : 300);
            const startX = p.x + (i % 2 ? 0 : 240);
            const startY = p.y + 110;
            return (
              <path
                key={i}
                d={`M${startX},${startY} C${startX},${endY} ${endX},${startY} ${endX},${endY}`}
              />
            );
          })}
        </svg>
        <div className="hero-heading">
          <h1>DubForge</h1>
          <p>localize every voice, without losing the feeling</p>
          <a className="hero-open" href="/app">
            Open workspace <span>↗</span>
          </a>
          <small>upload · review · translate · dub · export</small>
        </div>
        {cards.map((card, i) => (
          <Draggable
            key={i}
            x={initial[i].x}
            y={initial[i].y}
            rot={[-5, 5, -5, 5][i]}
            className={`artifact artifact-${i}`}
            onPositionChange={update(i)}
          >
            <span className="artifact-index">{i + 1}</span>
            {card}
          </Draggable>
        ))}
        <span className="board-annotation">
          keep the timing
          <br />
          natural ↙
        </span>
        <Draggable
          x={initial[4].x}
          y={initial[4].y}
          className="studio-window"
          onPositionChange={update(4)}
        >
          <MacWindow title="DubForge / localization desk">
            <Workspace />
          </MacWindow>
        </Draggable>
        <span className="board-footer">One story. Every language.</span>
      </div>
    </section>
  );
}

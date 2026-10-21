import { reviewChecks } from "../data/content.js";
import { rows } from "../data/demo.js";
import { useDeskLang } from "../hooks/useDeskLang.js";
import useReveal from "../hooks/useReveal.js";
import DeskWindow from "./ui/DeskWindow.jsx";
import SectionHead from "./ui/SectionHead.jsx";
import "./ReviewPass.css";

// The allowance is the larger of 300 ms or 15% of the original line.
const ORIGINAL = 3.2;
const DUBBED = 4.4;
const ALLOWED = Math.max(0.3, ORIGINAL * 0.15);
const SCALE = 5; // seconds across a full track

function Timing() {
  return (
    <div className="vis timing">
      <div className="t-row">
        <span>original</span>
        <div className="t-track">
          <i
            className="orig"
            style={{ "--w": `${(ORIGINAL / SCALE) * 100}%` }}
          />
        </div>
        <b>{ORIGINAL.toFixed(1)} s</b>
      </div>
      <div className="t-row">
        <span>dubbed</span>
        <div className="t-track">
          <s
            style={{
              left: `${(ORIGINAL / SCALE) * 100}%`,
              width: `${(ALLOWED / SCALE) * 100}%`,
            }}
          />
          <i className="dub" style={{ "--w": `${(DUBBED / SCALE) * 100}%` }} />
        </div>
        <b>{DUBBED.toFixed(1)} s</b>
      </div>
      <p>
        <span className="st warn">duration mismatch</span>
        <em>
          allowance for this line: ±{ALLOWED.toFixed(2)} s · dub is{" "}
          {(DUBBED - ORIGINAL).toFixed(1)} s longer
        </em>
      </p>
    </div>
  );
}

function Changes({ lang }) {
  return (
    <div className="vis">
      <small>line 3 · 00:06–00:10</small>
      <p className="line" lang={lang}>
        {rows[2][2][lang]}
      </p>
      <div className="btns">
        <span>approve</span>
        <span className="on">request changes</span>
      </div>
      <p className="lock">
        <span className="st warn">needs changes</span>
        <em>mp3 / mp4 locked · 2 of 4 lines approved</em>
      </p>
    </div>
  );
}

function Outdated() {
  return (
    <div className="vis flow">
      <div className="step">
        <span className="st ok">audio ready</span>
        <em>approved</em>
      </div>
      <i aria-hidden="true">↓ edit the translation</i>
      <div className="step now">
        <span className="st idle">audio outdated</span>
        <em>back to pending review</em>
      </div>
    </div>
  );
}

function Retry({ lang }) {
  return (
    <div className="vis">
      <small>line 4 · 00:10–00:13</small>
      <p className="line" lang={lang}>
        {rows[3][2][lang]}
      </p>
      <p className="lock">
        <span className="st warn">generation failed</span>
        <span className="btns inline">
          <span className="on">regenerate this line</span>
        </span>
      </p>
    </div>
  );
}

const visuals = {
  timing: Timing,
  changes: Changes,
  outdated: Outdated,
  retry: Retry,
};

export default function ReviewPass() {
  const lang = useDeskLang();
  const [ref, revealed] = useReveal(0.18);
  return (
    <section className="rvw" id="review">
      <SectionHead
        label="review pass"
        title="nothing ships unchecked"
        sub="every dubbed line is measured against the original, and every line needs a yes before the video exports."
      />
      <div ref={ref} className={`rvw-grid ${revealed ? "in" : ""}`}>
        {reviewChecks.map((check, i) => {
          const Visual = visuals[check.id];
          return (
            <article className="rvw-card" key={check.id} style={{ "--i": i }}>
              <DeskWindow ext={check.ext}>
                <Visual lang={lang} />
              </DeskWindow>
              <h3>{check.title}</h3>
              <p>{check.body}</p>
            </article>
          );
        })}
      </div>
    </section>
  );
}

import { rows } from "../data/demo.js";
import { langs } from "../data/langs.js";

// One small, static "screen" per pipeline stage. Demo values (durations, counts) are
// illustrative; the statuses and rules they show come from the real pipeline.

const clock = (ms) => `00:${String(Math.floor(ms / 1000)).padStart(2, "0")}`;
const spans = [
  [0, 3000],
  [3000, 6500],
  [6500, 10000],
  [10000, 13500],
];

const Head = ({ left, right }) => (
  <div className="sc-head">
    <span>{left}</span>
    <span>{right}</span>
  </div>
);

function Upload() {
  return (
    <>
      <Head left="new project" right="A brighter tomorrow" />
      <div className="sc-file">
        <span className="sc-ext">MOV</span>
        <div>
          <b>scene-04.mov</b>
          <small>demo project</small>
        </div>
      </div>
      <div className="sc-bar">
        <i style={{ "--w": "100%" }} />
      </div>
      <ul className="sc-list">
        <li className="done">video stored</li>
        <li className="done">
          audio track extracted <code>ffmpeg</code>
        </li>
        <li>queued for transcription</li>
      </ul>
    </>
  );
}

function Transcribe() {
  return (
    <>
      <Head left="transcript · English" right="4 segments" />
      <div className="sc-rows">
        {rows.map(([speaker, text], i) => (
          <div className="sc-row" key={text} style={{ "--i": i }}>
            <span className="sc-time">
              {clock(spans[i][0])}–{clock(spans[i][1])}
            </span>
            <span>{text}</span>
            <span className="st idle">{speaker}</span>
          </div>
        ))}
      </div>
      <p className="sc-note">
        speaker labels come from AssemblyAI when a key is configured.
      </p>
    </>
  );
}

function Translate({ lang }) {
  return (
    <>
      <Head left={`English → ${langs[lang].name}`} right="NLLB-200" />
      <div className="sc-rows">
        {rows.map(([, text, target], i) => (
          <div className="sc-row two" key={text} style={{ "--i": i }}>
            <span className="dim">{text}</span>
            <span className="tr" lang={lang}>
              {target[lang]}
            </span>
          </div>
        ))}
      </div>
    </>
  );
}

// original vs dubbed durations in seconds (demo values)
const timings = [
  [3.0, 3.1],
  [3.5, 3.4],
  [3.5, 4.8],
  [3.5, 3.6],
];

function Dub({ lang }) {
  return (
    <>
      <Head
        left={`dubbed audio · ${langs[lang].name}`}
        right="Edge TTS · MMS"
      />
      <div className="sc-rows">
        {timings.map(([orig, dub], i) => {
          const allowed = Math.max(0.3, orig * 0.15);
          const bad = Math.abs(dub - orig) > allowed;
          return (
            <div className="sc-dub" key={i} style={{ "--i": i }}>
              <span className="sc-time">00{i + 1}</span>
              <div className="sc-tracks">
                <div className="sc-track">
                  <i
                    className="orig"
                    style={{ "--w": `${(orig / 6) * 100}%` }}
                  />
                </div>
                <div className="sc-track">
                  <i
                    className={bad ? "dub bad" : "dub"}
                    style={{ "--w": `${(dub / 6) * 100}%` }}
                  />
                </div>
              </div>
              <span className={`st ${bad ? "warn" : "ok"}`}>
                {bad ? "duration mismatch" : "ready"}
              </span>
            </div>
          );
        })}
      </div>
      <p className="sc-note">
        top bar: original line · bottom bar: dubbed audio. a clip is flagged
        past 300 ms or 15% off.
      </p>
    </>
  );
}

const reviewStates = [
  ["approved", "ok", "ready", "ok"],
  ["approved", "ok", "ready", "ok"],
  ["needs changes", "warn", "duration mismatch", "warn"],
  ["pending", "idle", "outdated", "idle"],
];

function Review({ lang }) {
  return (
    <>
      <Head left="review" right="2 of 4 approved" />
      <div className="sc-rows">
        {rows.map(([, , target], i) => (
          <div className="sc-review" key={i} style={{ "--i": i }}>
            <span className="tr" lang={lang}>
              {target[lang]}
            </span>
            <span className="sc-chips">
              <span className={`st ${reviewStates[i][1]}`}>
                {reviewStates[i][0]}
              </span>
              <span className={`st ${reviewStates[i][3]}`}>
                {reviewStates[i][2]}
              </span>
            </span>
          </div>
        ))}
      </div>
      <div className="sc-actions">
        <span>approve</span>
        <span>request changes</span>
        <span>regenerate audio</span>
      </div>
    </>
  );
}

const exportFiles = [
  ["SRT", "subtitles", true],
  ["VTT", "web captions", true],
  ["MP3", "dubbed audio", false],
  ["MP4", "dubbed video", false],
];

function Export() {
  return (
    <>
      <Head left="export" right="2 of 4 lines approved" />
      <div className="sc-bar thin">
        <i style={{ "--w": "50%" }} />
      </div>
      <div className="sc-rows">
        {exportFiles.map(([ext, label, open], i) => (
          <div className="sc-file row" key={ext} style={{ "--i": i }}>
            <span className="sc-ext">{ext}</span>
            <div>
              <b>{label}</b>
            </div>
            <span className={`st ${open ? "ok" : "idle"}`}>
              {open ? "available" : "locked"}
            </span>
          </div>
        ))}
      </div>
      <p className="sc-note">
        MP3 and MP4 unlock once every line is approved with usable audio.
      </p>
    </>
  );
}

export const scenes = {
  upload: Upload,
  transcribe: Transcribe,
  translate: Translate,
  dub: Dub,
  review: Review,
  export: Export,
};

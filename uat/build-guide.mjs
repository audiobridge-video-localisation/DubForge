// Turns output/steps.json (written by record.mjs) into output/index.html: the visual UAT
// guide. Screenshots and videos are referenced relatively, so the output folder can be
// opened locally, zipped, or published as a whole.

import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(here, "output");

const esc = (s) =>
  String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const code = (id) => id.slice(0, 6).toUpperCase(); // uat-01-projects -> UAT-01

function stepHtml(flow, step) {
  const key = `${code(flow.id)}.${step.number}`;
  return `
      <li class="step" id="${esc(flow.id)}-${step.number}" data-key="${esc(key)}">
        <figure class="shot">
          <button type="button" class="zoom" data-src="${esc(step.shot)}" aria-label="Enlarge screenshot for step ${step.number}">
            <img src="${esc(step.shot)}" alt="Step ${step.number}: ${esc(step.caption)}" loading="lazy" width="1440" height="900">
          </button>
          ${
            step.resultShot
              ? `<figcaption><button type="button" class="zoom result" data-src="${esc(step.resultShot)}">
              <img src="${esc(step.resultShot)}" alt="Result after step ${step.number}" loading="lazy" width="1440" height="900">
              <span>What you should see after</span></button></figcaption>`
              : ""
          }
        </figure>
        <div class="body">
          <p class="num"><span class="badge">${step.number}</span><span class="key">${esc(key)}</span></p>
          <h4>${esc(step.caption)}</h4>
          <dl>
            <dt>Do</dt><dd>${esc(step.how)}</dd>
            <dt>Expect</dt><dd>${esc(step.expect)}</dd>
          </dl>
          ${step.caution ? `<p class="caution"><b>Caution</b>${esc(step.caution)}</p>` : ""}
          <div class="verdict" role="group" aria-label="Result for ${esc(key)}">
            <button type="button" data-v="pass">Pass</button>
            <button type="button" data-v="fail">Fail</button>
            <button type="button" data-v="blocked">Blocked</button>
          </div>
        </div>
      </li>`;
}

function flowHtml(flow) {
  return `
  <section class="flow" id="${esc(flow.id)}" aria-labelledby="${esc(flow.id)}-title">
    <header class="flow-head">
      <p class="flow-id">${code(flow.id)}</p>
      <h2 id="${esc(flow.id)}-title">${esc(flow.title)}</h2>
      <p class="goal">${esc(flow.goal)}</p>
    </header>
    <div class="flow-intro">
      <div class="prep">
        ${
          flow.before.length
            ? `<h3>Before you start</h3><ul>${flow.before.map((b) => `<li>${esc(b)}</li>`).join("")}</ul>`
            : ""
        }
        ${flow.cautions.map((c) => `<p class="caution"><b>Caution</b>${esc(c)}</p>`).join("")}
      </div>
      <figure class="video">
        <video src="${esc(flow.video)}" controls muted playsinline preload="metadata"></video>
        <figcaption>Whole flow, ${flow.steps.length} steps. The red ring and number show each step.</figcaption>
      </figure>
    </div>
    <ol class="steps">${flow.steps.map((s) => stepHtml(flow, s)).join("")}
    </ol>
  </section>`;
}

function page(data) {
  const recorded = new Date(data.recordedAt).toISOString().slice(0, 10);
  const total = data.flows.reduce((n, f) => n + f.steps.length, 0);
  return `<title>DubForge UAT Walkthrough</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap">
<style>
/* Layout: a test protocol. Flows run top to bottom; each step pairs its screenshot with
   Do / Expect / Caution and a verdict, numbered to match the red badge in the picture. */
:root {
  --bg: #f6f7f9; --panel: #ffffff; --ink: #14171d; --muted: #5b6270; --line: #dfe3ea;
  --mark: #e5484d; --mark-soft: #fde8e8; --warn-bg: #fff4e0; --warn-ink: #7a4a00; --warn-line: #f2c46d;
  --pass: #1f7a46; --pass-bg: #e3f4ea; --fail: #b4232a; --fail-bg: #fbe4e4; --blocked: #6b5a00; --blocked-bg: #f6efc6;
  --sans: "Instrument Sans", "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f1216; --panel: #171b21; --ink: #e9ecf1; --muted: #9aa3b2; --line: #2a313b;
  --mark: #ff6369; --mark-soft: #3a1a1c; --warn-bg: #2e2412; --warn-ink: #f5cf86; --warn-line: #6e5520;
  --pass: #63d394; --pass-bg: #17321f; --fail: #ff8a8f; --fail-bg: #3a1b1d; --blocked: #e8d36a; --blocked-bg: #33300f;
  color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0f1216; --panel: #171b21; --ink: #e9ecf1; --muted: #9aa3b2; --line: #2a313b;
  --mark: #ff6369; --mark-soft: #3a1a1c; --warn-bg: #2e2412; --warn-ink: #f5cf86; --warn-line: #6e5520;
  --pass: #63d394; --pass-bg: #17321f; --fail: #ff8a8f; --fail-bg: #3a1b1d; --blocked: #e8d36a; --blocked-bg: #33300f;
  color-scheme: dark }
* { box-sizing: border-box }
body { background: var(--bg); color: var(--ink); font: 16px/1.55 var(--sans); }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 40px 80px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
h1, h2, h3, h4 { text-wrap: balance; margin: 0; line-height: 1.2 }
h1 { font-size: clamp(30px, 4vw, 42px); font-weight: 700; letter-spacing: -0.02em }
.lede { color: var(--muted); max-width: 62ch; margin: 10px 0 0 }
.meta { font: 500 13px/1.4 var(--mono); color: var(--muted); margin-top: 14px; letter-spacing: .02em }
.legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; margin: 28px 0 0; padding: 0; list-style: none }
.legend li { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; display: flex; gap: 12px; align-items: flex-start; font-size: 14.5px }
.legend .ring { flex: none; width: 34px; height: 24px; border: 3px solid var(--mark); border-radius: 7px }
.badge { flex: none; display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--mark); color: #fff; font: 700 14px/1 var(--sans) }
.legend .warnchip { flex: none; width: 24px; height: 24px; border-radius: 6px; background: var(--warn-bg); border: 1px solid var(--warn-line) }
nav.toc { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--bg); padding-block: 12px; margin-top: 28px; border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: 8px; align-items: center }
nav.toc a { font: 500 13px/1 var(--mono); color: var(--ink); text-decoration: none; padding: 8px 11px; border: 1px solid var(--line); border-radius: 999px; background: var(--panel) }
nav.toc a:hover, nav.toc a:focus-visible { border-color: var(--mark); outline: none }
nav.toc .tally { margin-left: auto; font: 500 13px/1 var(--mono); color: var(--muted); display: flex; gap: 8px; align-items: center; flex-wrap: wrap }
.btn { font: 600 13px/1 var(--sans); padding: 9px 13px; border-radius: 8px; border: 1px solid var(--line); background: var(--panel); color: var(--ink); cursor: pointer }
.btn:hover, .btn:focus-visible { border-color: var(--ink); outline: none }
.flow { margin-top: 56px }
.flow-head { display: grid; gap: 6px }
.flow-id { font: 700 13px/1 var(--mono); color: var(--mark); letter-spacing: .08em; margin: 0 }
.flow-head h2 { font-size: 28px; letter-spacing: -0.01em }
.goal { color: var(--muted); margin: 0; max-width: 70ch }
.flow-intro { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr); gap: 20px; margin-top: 18px; align-items: start }
.prep { min-width: 0; display: grid; gap: 12px }
.prep h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted) }
.prep ul { margin: 0; padding-left: 20px }
.video { margin: 0; min-width: 0 }
.video video { width: 100%; max-width: 100%; aspect-ratio: 16 / 10; border-radius: 12px; border: 1px solid var(--line); background: #000; display: block }
.video figcaption, .result span { font-size: 13px; color: var(--muted); margin-top: 6px; display: block }
.caution { margin: 0; background: var(--warn-bg); color: var(--warn-ink); border: 1px solid var(--warn-line); border-radius: 10px; padding: 10px 12px; font-size: 14.5px }
.caution b { display: block; font-size: 12px; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 2px }
.steps { list-style: none; margin: 22px 0 0; padding: 0; display: grid; gap: 16px }
.step { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 20px; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 16px }
.step[data-v="pass"] { border-color: var(--pass) } .step[data-v="fail"] { border-color: var(--fail) } .step[data-v="blocked"] { border-color: var(--blocked) }
.shot { margin: 0; min-width: 0; display: grid; gap: 10px }
.zoom { all: unset; cursor: zoom-in; display: block; border-radius: 10px }
.zoom:focus-visible { outline: 3px solid var(--mark); outline-offset: 2px }
.zoom img { width: 100%; height: auto; border-radius: 10px; border: 1px solid var(--line); display: block }
.result { display: grid; grid-template-columns: 140px 1fr; gap: 10px; align-items: center }
.result img { width: 140px }
.body { min-width: 0; display: grid; gap: 10px; align-content: start }
.num { margin: 0; display: flex; gap: 10px; align-items: center }
.key { font: 500 12.5px/1 var(--mono); color: var(--muted) }
.body h4 { font-size: 19px }
dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 6px 12px }
dt { font: 700 12px/1.9 var(--sans); text-transform: uppercase; letter-spacing: .08em; color: var(--muted) }
dd { margin: 0 }
.verdict { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px }
.verdict button { font: 600 13px/1 var(--sans); padding: 9px 14px; border-radius: 8px; border: 1px solid var(--line); background: transparent; color: var(--ink); cursor: pointer }
.verdict button:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px }
.verdict button[aria-pressed="true"][data-v="pass"] { background: var(--pass-bg); color: var(--pass); border-color: var(--pass) }
.verdict button[aria-pressed="true"][data-v="fail"] { background: var(--fail-bg); color: var(--fail); border-color: var(--fail) }
.verdict button[aria-pressed="true"][data-v="blocked"] { background: var(--blocked-bg); color: var(--blocked); border-color: var(--blocked) }
.lightbox { position: fixed; inset: 0; z-index: 20; background: rgba(8,10,14,.88); display: grid; place-items: center; padding: max(16px, env(safe-area-inset-top, 0px)) max(16px, env(safe-area-inset-right, 0px)) max(16px, env(safe-area-inset-bottom, 0px)) max(16px, env(safe-area-inset-left, 0px)); cursor: zoom-out }
.lightbox img { max-width: 100%; max-height: 100%; border-radius: 8px }
.copied { font: 500 13px/1 var(--mono); color: var(--pass) }
textarea.fallback { width: 100%; min-height: 160px; font: 13px/1.4 var(--mono); margin-top: 8px; background: var(--panel); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; padding: 8px }
@media (max-width: 820px) { .flow-intro, .step { grid-template-columns: minmax(0, 1fr) } }
@media (prefers-reduced-motion: no-preference) { .step { transition: border-color .15s } }
</style>

<div class="wrap">
  <header>
    <h1>DubForge UAT walkthrough</h1>
    <p class="lede">Follow each flow in order on the test site. Every step shows where to click, what should happen, and what to watch out for. Mark each step Pass, Fail or Blocked as you go, then copy your results into the results log.</p>
    <p class="meta">${data.flows.length} flows · ${total} steps · recorded ${recorded} on the mock-provider test setup</p>
    <ul class="legend">
      <li><span class="ring" aria-hidden="true"></span><span>The red ring marks what to click or look at.</span></li>
      <li><span class="badge" aria-hidden="true">3</span><span>The number matches the step below the picture.</span></li>
      <li><span class="warnchip" aria-hidden="true"></span><span>Amber boxes are cautions: places testers often get caught out.</span></li>
    </ul>
  </header>

  <nav class="toc" aria-label="Flows">
    ${data.flows.map((f) => `<a href="#${esc(f.id)}">${code(f.id)} ${esc(f.title)}</a>`).join("\n    ")}
    <span class="tally"><span id="tally">0 of ${total} marked</span>
      <button type="button" class="btn" id="copy">Copy results</button>
      <button type="button" class="btn" id="clear">Clear</button>
      <span id="copied" class="copied" role="status"></span></span>
  </nav>
  <div id="fallback-slot"></div>

  ${data.flows.map(flowHtml).join("\n")}
</div>

<script>
(() => {
  const STORE = "dubforge-uat-results";
  const steps = [...document.querySelectorAll(".step")];
  let results = {};
  try { results = JSON.parse(localStorage.getItem(STORE) || "{}") || {}; } catch { results = {}; }
  const save = () => { try { localStorage.setItem(STORE, JSON.stringify(results)); } catch {} };
  const tally = document.getElementById("tally");

  function paint() {
    let n = 0;
    for (const li of steps) {
      const v = results[li.dataset.key];
      if (v) { li.dataset.v = v; n++; } else { delete li.dataset.v; }
      for (const b of li.querySelectorAll(".verdict button")) b.setAttribute("aria-pressed", String(b.dataset.v === v));
    }
    tally.textContent = n + " of " + steps.length + " marked";
  }

  for (const li of steps) {
    li.querySelector(".verdict").addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      const key = li.dataset.key;
      results[key] = results[key] === b.dataset.v ? undefined : b.dataset.v;
      if (!results[key]) delete results[key];
      save(); paint();
    });
  }

  function report() {
    const lines = ["Step\\tCaption\\tResult"];
    for (const li of steps) {
      const v = results[li.dataset.key] || "not run";
      lines.push(li.dataset.key + "\\t" + li.querySelector("h4").textContent + "\\t" + v);
    }
    return lines.join("\\n");
  }

  const copied = document.getElementById("copied");
  document.getElementById("copy").addEventListener("click", () => {
    const text = report();
    const done = () => { copied.textContent = "Copied"; setTimeout(() => (copied.textContent = ""), 2000); };
    const fallback = () => {
      const slot = document.getElementById("fallback-slot");
      slot.innerHTML = "";
      const ta = document.createElement("textarea");
      ta.className = "fallback"; ta.id = "results-text"; ta.readOnly = true; ta.value = text;
      slot.append(ta); ta.focus(); ta.select();
      copied.textContent = "Select all and copy";
    };
    try { navigator.clipboard.writeText(text).then(done, fallback); } catch { fallback(); }
  });
  document.getElementById("clear").addEventListener("click", () => { results = {}; save(); paint(); });

  document.addEventListener("click", (e) => {
    const z = e.target.closest(".zoom"); if (!z) return;
    const box = document.createElement("div");
    box.className = "lightbox"; box.tabIndex = 0;
    const img = document.createElement("img"); img.src = z.dataset.src; img.alt = "";
    box.append(img); document.body.append(box); box.focus();
    const close = () => box.remove();
    box.addEventListener("click", close);
    box.addEventListener("keydown", (k) => { if (k.key === "Escape") close(); });
  });

  paint();
})();
</script>
`;
}

const data = JSON.parse(await readFile(path.join(OUT, "steps.json"), "utf8"));
await writeFile(path.join(OUT, "index.html"), page(data));
console.log(`Wrote ${path.join(OUT, "index.html")}`);

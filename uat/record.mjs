// Records the DubForge UAT walkthroughs against a running app.
//
//   UAT_BASE_URL=http://localhost:8090 npm run record
//
// For every step: the element to use gets a highlight box and a numbered caption, a
// screenshot is taken, then the step is performed. Each flow is also recorded as a video.
// Output (uat/output/): shots/<flow>/<nn>.png, videos/<flow>.webm, steps.json. Run
// `node build-guide.mjs` afterwards to turn steps.json into the visual guide.
//
// The flows build on each other (the project made in flow 1 is used until it is deleted
// in the last one), so always run them all, in order.

import { mkdir, rm, rename, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { flows } from "./flows.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.UAT_BASE_URL ?? "http://localhost:8090";
const OUT = path.join(here, "output");
const VIEWPORT = { width: 1440, height: 900 };
// how long the highlight stays on screen in the video before the action happens
const HOLD_MS = Number(process.env.UAT_HOLD_MS ?? 1400);

const ACCENT = "#e5484d";

async function showOverlay(page, target, number, caption) {
  const box = target ? await target.boundingBox() : null;
  await page.evaluate(
    ({ box, number, caption, accent }) => {
      document.getElementById("__uat")?.remove();
      const root = document.createElement("div");
      root.id = "__uat";
      root.style.cssText =
        "position:fixed;inset:0;pointer-events:none;z-index:2147483647;font-family:system-ui,sans-serif";
      if (box) {
        const pad = 6;
        const ring = document.createElement("div");
        ring.style.cssText = `position:fixed;left:${box.x - pad}px;top:${box.y - pad}px;width:${box.width + pad * 2}px;height:${box.height + pad * 2}px;border:3px solid ${accent};border-radius:10px;box-shadow:0 0 0 4000px rgba(10,12,16,.28)`;
        const badge = document.createElement("div");
        badge.textContent = String(number);
        const bx = Math.max(4, box.x - pad - 16);
        const by = Math.max(4, box.y - pad - 16);
        badge.style.cssText = `position:fixed;left:${bx}px;top:${by}px;width:30px;height:30px;border-radius:50%;background:${accent};color:#fff;font-weight:700;font-size:15px;display:grid;place-items:center;box-shadow:0 1px 4px rgba(0,0,0,.35)`;
        root.append(ring, badge);
      }
      const bar = document.createElement("div");
      bar.textContent = `Step ${number} · ${caption}`;
      bar.style.cssText =
        "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);max-width:80%;background:rgba(17,19,24,.92);color:#fff;font-size:17px;font-weight:600;padding:12px 20px;border-radius:12px;box-shadow:0 4px 18px rgba(0,0,0,.3)";
      root.append(bar);
      document.body.append(root);
    },
    { box, number, caption, accent: ACCENT },
  );
}

async function hideOverlay(page) {
  await page.evaluate(() => document.getElementById("__uat")?.remove());
}

async function recordFlow(browser, flow, state) {
  const shotDir = path.join(OUT, "shots", flow.id);
  await mkdir(shotDir, { recursive: true });
  const context = await browser.newContext({
    viewport: VIEWPORT,
    acceptDownloads: true,
    recordVideo: { dir: path.join(OUT, "videos", "_raw"), size: VIEWPORT },
  });
  const page = await context.newPage();
  // window.confirm prompts (delete project, approve lines marked "needs changes") are
  // accepted; the guide tells testers they will see one.
  page.on("dialog", (dialog) => {
    state.lastDialog = dialog.message();
    void dialog.accept();
  });

  const ctx = { page, base: BASE, state, samples: path.join(here, "samples") };
  const recorded = [];
  try {
    if (flow.start) await flow.start(ctx);
    for (const [i, step] of flow.steps.entries()) {
      const number = i + 1;
      const target = step.target ? step.target(ctx) : null;
      if (target) {
        await target.waitFor({ state: "visible", timeout: 60_000 });
        await target.scrollIntoViewIfNeeded();
      }
      await showOverlay(page, target, number, step.caption);
      await page.waitForTimeout(HOLD_MS);
      const shot = `shots/${flow.id}/${String(number).padStart(2, "0")}.png`;
      await page.screenshot({ path: path.join(OUT, shot) });
      await hideOverlay(page);

      if (step.act) await step.act(ctx, target);
      let resultShot = null;
      if (step.waitFor) await step.waitFor(ctx);
      if (step.resultShot) {
        await page.waitForTimeout(400);
        resultShot = `shots/${flow.id}/${String(number).padStart(2, "0")}-result.png`;
        await page.screenshot({ path: path.join(OUT, resultShot) });
      }
      recorded.push({
        number,
        caption: step.caption,
        how: step.how,
        expect: step.expect,
        caution: step.caution ?? null,
        shot,
        resultShot,
      });
      console.log(`  ${flow.id} ${number}. ${step.caption}`);
    }
  } finally {
    const video = page.video();
    await context.close();
    if (video) {
      const raw = await video.path();
      await rename(raw, path.join(OUT, "videos", `${flow.id}.webm`));
    }
  }
  return recorded;
}

async function main() {
  if (existsSync(OUT)) await rm(OUT, { recursive: true });
  await mkdir(path.join(OUT, "videos", "_raw"), { recursive: true });

  const browser = await chromium.launch();
  const state = {};
  const result = [];
  try {
    for (const flow of flows) {
      console.log(`${flow.id}: ${flow.title}`);
      const steps = await recordFlow(browser, flow, state);
      result.push({
        id: flow.id,
        title: flow.title,
        goal: flow.goal,
        before: flow.before ?? [],
        cautions: flow.cautions ?? [],
        video: `videos/${flow.id}.webm`,
        steps,
      });
    }
  } finally {
    await browser.close();
    await rm(path.join(OUT, "videos", "_raw"), { recursive: true, force: true });
  }
  await writeFile(
    path.join(OUT, "steps.json"),
    JSON.stringify({ recordedAt: new Date().toISOString(), base: BASE, flows: result }, null, 2),
  );
  console.log(`\nRecorded ${result.length} flows into ${OUT}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

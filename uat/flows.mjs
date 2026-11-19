// The UAT walkthroughs, in the order they must run. Each step says what the tester does
// (caption + how), what they should see (expect), and, where people tend to get caught
// out, a caution. `target` is the element highlighted in the screenshot; `act` performs
// the step; `waitFor` holds until its result is on screen.

import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_VIDEO = path.join(here, "..", "samples", "demo-speech.mp4");
const NOT_A_VIDEO = path.join(here, "samples", "not-a-video.txt");
// unique per run, so a rerun never trips over a project an earlier run left behind
const PROJECT_NAME = `UAT - Demo clip ${new Date().toISOString().slice(5, 16).replace("T", " ")}`;
const LONG = 180_000;

const rows = (page) => page.locator("tr.row");
const meter = (page, label) => page.locator(".meter", { hasText: label });
const exportRow = (page, kind) => page.locator(".export-job", { hasText: kind });

async function download(page, trigger, state, name) {
  const [file] = await Promise.all([page.waitForEvent("download"), trigger.click()]);
  state.downloads ??= {};
  state.downloads[name] = file.suggestedFilename();
}

export const flows = [
  {
    id: "uat-01-projects",
    title: "Create a project",
    goal: "A tester can create a named project and lands on its page.",
    before: ["Open the app in Chrome, Edge or Firefox (latest version)."],
    start: async ({ page, base }) => {
      await page.goto(`${base}/app`);
    },
    steps: [
      {
        caption: "Open the Projects page",
        how: "Go to the app address and add /app, or click Projects in the top bar.",
        expect: "A page headed Projects, a New project card, and a Your projects list.",
        target: ({ page }) => page.getByRole("heading", { level: 1, name: "Projects" }),
      },
      {
        caption: "Try to create a project with no name",
        how: "Leave the name box empty and click Create project.",
        expect: 'A red message "Give the project a name." appears and no project is created.',
        target: ({ page }) => page.getByRole("button", { name: "Create project" }),
        act: async (_, target) => target.click(),
        resultShot: true,
      },
      {
        caption: "Type a project name",
        how: `Click the Project name box and type a name, for example "${PROJECT_NAME}".`,
        expect: "The red message goes away as soon as you start typing.",
        target: ({ page }) => page.getByLabel("Project name"),
        act: async (_, target) => target.fill(PROJECT_NAME),
      },
      {
        caption: "Create the project",
        how: "Click Create project.",
        expect:
          "The project page opens with the project name at the top, a Waiting for a video badge, and an Upload a video card.",
        target: ({ page }) => page.getByRole("button", { name: "Create project" }),
        act: async ({ page, state }, target) => {
          await target.click();
          await page.waitForURL(/\/projects\//);
          state.projectUrl = page.url();
          state.projectName = PROJECT_NAME;
        },
        resultShot: true,
      },
    ],
  },
  {
    id: "uat-02-upload",
    title: "Upload a video and wait for processing",
    goal: "A video uploads, is transcribed and translated, and its lines appear for review.",
    before: [
      "Have a short test video ready (under 1 minute, English speech). The team's sample is samples/demo-speech.mp4.",
      "Also have any non-video file (a .txt or .pdf) to check the file check.",
    ],
    cautions: [
      "Keep the tab open while the upload bar moves. Closing it cancels the upload. Once the bar finishes, processing runs on the server and you can leave the page.",
    ],
    start: async ({ page, state }) => {
      await page.goto(state.projectUrl);
    },
    steps: [
      {
        caption: "Try to upload a file that is not a video",
        how: "Click browse your files (or drag a file onto the box) and pick a .txt or .pdf file.",
        expect:
          "A red Can't use that file box says .txt files aren't supported and asks for a video (MP4, MOV, MKV or WebM). Nothing uploads. Choose another file clears it.",
        target: ({ page }) => page.locator(".dz-body"),
        act: async ({ page }) => page.locator("input[type=file]").setInputFiles(NOT_A_VIDEO),
        resultShot: true,
      },
      {
        caption: "Choose the test video",
        how: "Click browse your files again and pick the test video.",
        expect:
          "The file name and size show in a chip, with a Dub into choice and an Upload and process button.",
        target: ({ page }) => page.locator(".dz-body"),
        act: async ({ page }) => page.locator("input[type=file]").setInputFiles(SAMPLE_VIDEO),
      },
      {
        caption: "Pick the language to dub into",
        how: "Open the Dub into list and choose Hindi (or Bengali when testing Bengali).",
        expect: "The chosen language shows in the list.",
        caution:
          "The language is fixed once the upload starts. To try another language, upload the video again.",
        target: ({ page }) => page.locator(".dz-lang select"),
        act: async (_, target) => target.selectOption("hi"),
      },
      {
        caption: "Upload and start processing",
        how: "Click Upload and process, then wait. The mock setup takes a few seconds; real voices and translation can take several minutes.",
        expect:
          "An upload bar fills, the video's badge shows Queued, then Processing, then Processed, and the Transcript and translation table appears.",
        caution:
          "If the status shows Failed, click Retry once. If it fails again, report it with the error text shown on the card.",
        target: ({ page }) => page.getByRole("button", { name: "Upload and process" }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) =>
          page
            .getByRole("heading", { name: "Transcript and translation" })
            .waitFor({ timeout: LONG }),
        resultShot: true,
      },
      {
        caption: "Check the video card",
        how: "Look at the top of the video card.",
        expect:
          "The file name, Uploaded just now · Dubbing into Hindi, and a Processed badge on the right.",
        target: ({ page }) => page.locator(".media-head"),
      },
    ],
  },
  {
    id: "uat-03-review",
    title: "Review, edit and approve lines",
    goal: "A reviewer can check each line, fix it, flag it, and approve lines one by one or all at once.",
    before: ["Flow UAT-02 is done: the project has a processed video with lines."],
    start: async ({ page, state }) => {
      await page.goto(state.projectUrl);
      await rows(page).first().waitFor();
    },
    steps: [
      {
        caption: "Read the lines table",
        how: "Scroll to Transcript and translation.",
        expect:
          "One row per spoken line: number, time, duration, speaker, source text, translation, and review/audio status. Every line starts as Pending.",
        target: ({ page }) => page.locator(".table-wrap"),
      },
      {
        caption: "Play a line in the original video",
        how: "Click the time of line 1.",
        expect: "The original video jumps to that moment and plays the line.",
        target: ({ page }) => page.locator(".time-btn").first(),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Open the editor for line 1",
        how: "Click Edit on line 1.",
        expect: "An edit panel opens under the line with Source text, Translation, Speaker, Start and End.",
        target: ({ page }) => rows(page).first().getByRole("button", { name: "Edit" }),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Change the translation",
        how: "Change the text in the Translation box.",
        expect: '"Unsaved changes" appears next to the buttons.',
        caution:
          "Saving any change sends the line back to Pending and marks its dubbed audio Outdated. It must be approved and its audio generated again. A much longer translation also shows a Heads up box saying the line is probably too long for its slot: shorten it before generating audio.",
        target: ({ page }) => page.locator("form.edit textarea").nth(1),
        act: async (_, target) => target.fill("[hi] Hello, this is a test. (edited in UAT)"),
      },
      {
        caption: "Save the change",
        how: "Click Save changes (or press Ctrl/Cmd + Enter).",
        expect: "The panel closes and line 1 shows the new translation, still Pending.",
        target: ({ page }) => page.getByRole("button", { name: "Save changes" }),
        act: async (_, target) => target.click(),
        resultShot: true,
      },
      {
        caption: "Filter to pending lines",
        how: "Click the Pending chip above the table.",
        expect: "Only lines still waiting for review are listed.",
        target: ({ page }) => page.getByRole("group", { name: "Filter lines" }).getByRole("button", { name: /^Pending/ }),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Show all lines again",
        how: "Click the All chip.",
        expect: "Every line is listed again.",
        target: ({ page }) => page.getByRole("group", { name: "Filter lines" }).getByRole("button", { name: /^All/ }),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Open more actions for line 2",
        how: "Click the ⋯ button on line 2.",
        expect: "A small menu with Request changes and Regenerate audio.",
        target: ({ page }) => rows(page).nth(1).getByLabel("More actions"),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Flag line 2 as needing changes",
        how: "Click Request changes.",
        expect: "Line 2's review status becomes Needs changes.",
        target: ({ page }) => rows(page).nth(1).getByRole("button", { name: "Request changes" }),
        act: async (_, target) => target.click(),
        resultShot: true,
      },
      {
        caption: "Approve line 1",
        how: "Click Approve on line 1.",
        expect:
          "Line 1 shows Approved, its Approve button greys out, and Lines approved goes up by one.",
        target: ({ page }) => rows(page).first().getByRole("button", { name: "Approve" }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) => meter(page, "Lines approved").getByText("1 / 2").waitFor(),
      },
      {
        caption: "Approve all remaining lines",
        how: "Click Approve all (the number shows how many lines are left).",
        expect:
          "Every line shows Approved, Lines approved is full (for example 2 / 2), and the Approve all button disappears.",
        caution:
          'When a line is marked Needs changes, a pop-up asks whether to approve it too. Click OK only if the change was really made; otherwise click Cancel and fix the line first.',
        target: ({ page }) => page.getByRole("button", { name: /^Approve all/ }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) => meter(page, "Lines approved").getByText("2 / 2").waitFor(),
        resultShot: true,
      },
    ],
  },
  {
    id: "uat-04-dub-audio",
    title: "Generate and check the dubbed audio",
    goal: "Every line gets dubbed audio that fits its slot, with the chosen voice.",
    before: ["Flow UAT-03 is done: all lines are approved."],
    cautions: [
      "On the test setup with mock voices the dubbed audio is silent. Listening checks need the staging setup with real voices.",
    ],
    start: async ({ page, state }) => {
      await page.goto(state.projectUrl);
      await rows(page).first().waitFor();
    },
    steps: [
      {
        caption: "Choose the dub voice",
        how: "In Dub voice, pick Female or Male (Default keeps the standard voice).",
        expect: "The choice stays selected after a page refresh.",
        caution:
          "The voice applies only to audio generated after the change. Lines already dubbed keep the old voice until they are regenerated.",
        target: ({ page }) => page.locator(".voice-gender-select select"),
        act: async (_, target) => target.selectOption("female"),
      },
      {
        caption: "Generate dubbed audio for every line",
        how: "Click Generate dubbed audio (the number is how many lines have no audio yet).",
        expect:
          "Each line shows Generating, then Ready. Dubbed audio ready fills up (for example 2 / 2).",
        caution:
          "A line marked Stretched will slow the video slightly in the export; Mismatch means the dub is too long even then. Edit the translation shorter and regenerate it.",
        target: ({ page }) => page.getByRole("button", { name: /^Generate dubbed audio/ }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) =>
          meter(page, "Dubbed audio ready").getByText("2 / 2").waitFor({ timeout: LONG }),
        resultShot: true,
      },
      {
        caption: "Listen to a dubbed line",
        how: "Click the play button in line 1's status column.",
        expect: "The dubbed line plays; the button changes to Stop while it plays.",
        target: ({ page }) => rows(page).first().getByRole("button", { name: /^Play dubbed audio/ }),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Open more actions for line 1",
        how: "Click the ⋯ button on line 1.",
        expect: "The menu shows Regenerate audio.",
        target: ({ page }) => rows(page).first().getByLabel("More actions"),
        act: async (_, target) => target.click(),
      },
      {
        caption: "Regenerate one line's audio",
        how: "Click Regenerate audio.",
        expect: "Line 1 shows Generating, then Ready again. Its review status stays Approved.",
        target: ({ page }) => rows(page).first().getByRole("button", { name: "Regenerate audio" }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) =>
          meter(page, "Dubbed audio ready").getByText("2 / 2").waitFor({ timeout: LONG }),
        resultShot: true,
      },
    ],
  },
  {
    id: "uat-05-export",
    title: "Mark ready and export",
    goal: "A fully approved and dubbed video can be marked ready and exported as subtitles, MP3 and MP4.",
    before: ["Flow UAT-04 is done: every line is approved and its audio is Ready."],
    start: async ({ page, state }) => {
      await page.goto(state.projectUrl);
      await rows(page).first().waitFor();
    },
    steps: [
      {
        caption: "Mark the video ready for dubbing",
        how: "Click Mark ready for dubbing.",
        expect: "The button changes to Marked ready for dubbing and greys out.",
        caution:
          "The button only works when every line is approved and has usable audio. If it stays grey, look for a line that is Pending, Needs changes, Outdated or Mismatch.",
        target: ({ page }) => page.getByRole("button", { name: "Mark ready for dubbing" }),
        act: async (_, target) => target.click(),
        resultShot: true,
      },
      {
        caption: "Check readiness in the Export center",
        how: "Scroll to Export center.",
        expect: "Every Readiness check is ticked, and Project summary shows the file, lines, speakers, length, language and voice.",
        target: ({ page }) => page.getByRole("heading", { name: "Export center" }),
      },
      {
        caption: "Download the SRT subtitles",
        how: "Click Download SRT.",
        expect:
          "An .srt file downloads. Opened in a text editor it shows numbered lines with times and the translated text.",
        target: ({ page }) => page.getByRole("link", { name: "Download SRT" }),
        act: async ({ page, state }, target) => download(page, target, state, "srt"),
      },
      {
        caption: "Download the VTT subtitles",
        how: "Click Download VTT.",
        expect: "A .vtt file downloads, starting with WEBVTT.",
        target: ({ page }) => page.getByRole("link", { name: "Download VTT" }),
        act: async ({ page, state }, target) => download(page, target, state, "vtt"),
      },
      {
        caption: "Export the dubbed audio (MP3)",
        how: "Click Export MP3 and wait.",
        expect: "A Dubbed audio (MP3) row appears: Queued, then Exporting with a progress bar, then Ready with a Download link.",
        target: ({ page }) => page.getByRole("button", { name: "Export MP3" }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) =>
          exportRow(page, "MP3").getByRole("link", { name: "Download" }).waitFor({ timeout: LONG }),
        resultShot: true,
      },
      {
        caption: "Export the dubbed video (MP4)",
        how: "Click Export MP4 and wait.",
        expect: "A Dubbed video (MP4) row appears, goes Queued, then Exporting, and ends Ready with a Download link.",
        caution:
          "MP4 takes longer than MP3. With real voices and background sound it can take several minutes for a short clip. Don't click Export again while it is running.",
        target: ({ page }) => page.getByRole("button", { name: "Export MP4" }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page }) =>
          exportRow(page, "MP4").getByRole("link", { name: "Download" }).waitFor({ timeout: LONG }),
        resultShot: true,
      },
      {
        caption: "Download and watch the MP4",
        how: "Click Download on the Dubbed video (MP4) row and play the file.",
        expect:
          "The video plays with the dubbed voice in place of the original speech and translated subtitles that can be turned on in the player.",
        caution:
          "Where a dub runs long the picture may slow slightly or hold a frame for a moment. That is expected. Report it only if voice and lips drift apart by more than about half a second.",
        target: ({ page }) => exportRow(page, "MP4").getByRole("link", { name: "Download" }),
        act: async ({ page, state }, target) => download(page, target, state, "mp4"),
      },
    ],
  },
  {
    id: "uat-06-delete",
    title: "Delete a project",
    goal: "A project and everything in it can be deleted from the Projects page.",
    before: ["Use a throwaway project. Never delete a project someone else is working on."],
    cautions: [
      "Deleting is permanent. The video, lines, dubbed audio and exports are removed and cannot be brought back.",
    ],
    start: async ({ page, base }) => {
      await page.goto(`${base}/app`);
    },
    steps: [
      {
        caption: "Find the project on the Projects page",
        how: "Go to Projects and find the card for your test project.",
        expect: "The card shows the project name and when it was created, with a Delete button in its corner.",
        target: ({ page, state }) => page.locator(".project-item", { hasText: state.projectName }),
      },
      {
        caption: "Delete the project",
        how: "Click Delete on the card, read the pop-up, and click OK.",
        expect:
          'A pop-up asks to confirm, naming the project. After OK the card disappears and the project count drops by one.',
        caution:
          "Check the project name in the pop-up before clicking OK. Click Cancel and nothing is deleted.",
        target: ({ page, state }) =>
          page.getByRole("button", { name: `Delete project ${state.projectName}` }),
        act: async (_, target) => target.click(),
        waitFor: async ({ page, state }) =>
          page.locator(".project-item", { hasText: state.projectName }).waitFor({ state: "detached" }),
        resultShot: true,
      },
      {
        caption: "Open the deleted project's old link",
        how: "Paste the old project address into the browser.",
        expect: "A page says We couldn't open this project, Project not found, with a Back to projects button.",
        target: null,
        act: async ({ page, state }) => {
          await page.goto(state.projectUrl);
          await page.getByText(/not found|could not be found/i).first().waitFor();
        },
        resultShot: true,
      },
    ],
  },
];

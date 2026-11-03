# DubForge demo script and smoke-test log

A 6–8 minute walkthrough, then the record of the last smoke run.

## Reset and repeat

```bash
scripts/demo.sh fresh      # delete all demo data, then upload samples/demo-speech.mp4 and wait
scripts/demo.sh reset      # only delete (asks you to type "reset"; add --yes to skip the prompt)
scripts/demo.sh seed       # only upload the sample and print the project link
```

It keeps the downloaded models. If your compose needs an env file, set `DEMO_ENV_FILE=...`.
`samples/demo-speech.mp4` is the known-good input: 7 sentences, 17 seconds.

## Before you start

- Run the stack: `docker compose up --build` (add `--env-file` for mock providers if you do not want to download models).
- Open the web address and sign in if the site is password protected.
- Have a **short video with speech** ready (under 1 minute is plenty). `.mp4` is safest.
- Mock providers produce the same two lines and **silent** dubbed audio. That is expected. Say so up front.

## The script

| # | Do this | Say this | You should see |
|---|---------|----------|----------------|
| 1 | Open **Projects**, create "Demo". | "One project holds a video and everything made from it." | The project opens on an empty page: "No videos yet". |
| 2 | Drop a `.pdf` on the upload box. | "It checks the file before uploading." | A red message: ".pdf files aren't supported…". |
| 3 | Drop the demo video. Click **Upload and process**. | "Upload progress is live." | A progress bar, then "uploaded". |
| 4 | Watch processing. | "It listens, transcribes and translates." | A stage label and percent, then "Processed". |
| 5 | Click a line. | "Clicking a line jumps the original video to that moment." | The video seeks and the line highlights. |
| 6 | Edit a translation. | "Unsaved changes are flagged so nothing is lost." | An "Unsaved changes" label until saved. |
| 7 | Click **Request changes** on one line, **Approve** on the rest. | "The reviewer can approve or send a line back." | Counts update: "Lines approved". |
| 8 | Scroll to **Export center**. | "This says exactly what stands between us and an export." | "1 thing is blocking export: 1 line needs changes. Line 2." Export buttons are disabled. |
| 9 | Fix and approve the line. Click **Generate dubbed audio**. | "Now it makes the voice for each line." | Audio states move pending → ready. |
| 10 | Press **Play dub** on a line. | "Each line can be heard on its own." | The clip plays (silent on mock). |
| 11 | Make one translation very long, save, **Regenerate**. | "Small timing problems fix themselves." | Small gaps are time-fitted. A dub far longer than its slot stays flagged "too long" and appears in the Export center. |
| 12 | Back in **Export center**, clear every blocker. | "Ready means every line is approved and has usable audio." | "Ready to export", the project summary, and the export buttons enabled. |
| 13 | Click **Export MP3** and **Export MP4**. | "Exports run in the background." | A progress bar, then **Download**. |
| 14 | **Refresh the page** while an export runs, then after it finishes. | "Nothing is stored in the browser. The page asks the server." | The same export state comes back; finished exports still offer **Download**. |
| 15 | Download SRT and VTT. | "Subtitles are available as soon as there are lines." | Files download. |

If the demo goes wrong, the fastest recovery is **Projects → New project → upload again**.

## Smoke-test log

### Run 1 — API level, local Docker, mock providers

Sample video: a short test clip (mock speech-to-text returns two lines); stack rebuilt from the current branch. 21 checks, 21 passed.

| Check | Result |
|-------|--------|
| Create project, upload, processing completes | Pass (2 lines found) |
| Export list empty before any export | Pass |
| Export refused before review, and when approved but no audio | Pass (409) |
| A line marked "needs changes" is visible and not counted as approved | Pass |
| All audio ready, then MP3 and MP4 export | Pass |
| Export list returned from the API with no browser state (the "after refresh" case) | Pass, both kinds |
| Exports download | Pass (MP3 about 127 KB, MP4 about 9 KB) |
| SRT download | Pass |
| Editing a line makes its audio outdated, un-approves it and blocks export again | Pass |
| Unknown media returns 404 | Pass |

### Run 2 — the real UI, driven in a simulated browser (jsdom) against the live local stack

22 of 22 steps passed: create project (including the blank-name error); upload refusals (.pdf, empty, no extension); two-file drop notice; upload and processing; Export center blockers and locked export; click a line to seek the source video; speaker colours; edit with the "Unsaved changes" label; request changes shown as a blocker; approve; generate audio; export unlock and summary; MP3 and MP4 export with Download links; mark ready; "audio changed after this export" note; and a **refresh** in a brand-new window, which restored the exports from the API; no JS errors logged.

This runs the real app code, but it is not a real browser: there is no layout or styling, and no actual audio or video playback.

### Run 4 — the plan's October 31 acceptance test, real providers, `samples/demo-speech.mp4`

Run with the timing changes from the stacked timing PR applied (without them, long Hindi lines can be flagged as too long and need editing). Simulated-browser run of the whole path: create project, upload checks, process (Whisper, NLLB, local MMS voice), edit, approve all 7 lines, generate audio (7 of 7 usable), play buttons, SRT and VTT download, MP3 and MP4 export and download, then a refresh in a new window. 14 of 14 steps passed.

Hardening drills on the live stack:

| Drill | Result |
|-------|--------|
| Job stuck at 70% for 10 minutes (as after a worker restart) | The page shows a Retry button; Retry re-runs it |
| Re-processing a video that already had dubbed audio | Completes (this used to be a 500); the old audio rows and files are removed and "ready for dubbing" is cleared |
| Export download with `output_path` = `../../etc/passwd` | 404; nothing outside storage is served |
| `/api/internal/*`, `/api/docs`, `/api/openapi.json` through the web address | All 404; the API port itself is published on localhost only |
| `scripts/demo.sh` on a separate throwaway stack | Wrong confirmation cancels; `reset --yes` empties projects, queues and files but keeps the model cache; `fresh` rebuilds the demo |

### What these runs did not cover

- **A person looking at it in a real browser.** How it looks (layout, colours, spacing) and real audio and video playback are still to be confirmed by eye.
- Real models (Whisper, NLLB, edge or MMS voices) were not used.
- Uploading a file near the 2 GB limit was not tried. The page checks size before uploading; the server also refuses it (413, shown as "too large").

### Things noticed

- The server's refusal message for a blocked export is generic ("All segments must be approved and have usable dubbed audio before exporting"). The Export center is what explains which lines and why.
- The API reads an upload fully into memory, so very large files are risky on a small server. The page warns above 500 MB.

### Blank template for the next run

| Step | Expected | Actual | Pass? | Notes / screenshot |
|------|----------|--------|-------|--------------------|
|      |          |        |       |                    |

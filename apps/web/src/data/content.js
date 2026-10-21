// Landing page copy lives here so components stay presentational. Every claim is
// checked against the code in apps/api and pipeline.
export const brand = "DubForge";

export const navLinks = [
  { label: "how it works", href: "#how" },
  { label: "review", href: "#review" },
  { label: "early access", href: "#start" },
  { label: "faq", href: "#faq" },
];

export const pipelineSteps = [
  {
    id: "upload",
    title: "upload a video",
    body: "start a project and upload your video. FFmpeg pulls the audio track out so the models can work on it.",
    chips: ["FFmpeg"],
  },
  {
    id: "transcribe",
    title: "transcribe the dialogue",
    body: "faster-whisper turns English speech into timed segments. with an AssemblyAI key it also labels who is speaking. lines shorter than half a second are merged so they stay speakable.",
    chips: ["faster-whisper", "AssemblyAI"],
  },
  {
    id: "translate",
    title: "translate line by line",
    body: "NLLB-200 translates each segment from English into Hindi or Bengali, one line at a time. every project dubs into one target language.",
    chips: ["NLLB-200", "English → Hindi / Bengali"],
  },
  {
    id: "dub",
    title: "give every line a voice",
    body: "a text-to-speech voice reads each translated line. DubForge then measures each clip against the original line's duration.",
    chips: ["Edge TTS", "MMS-TTS"],
  },
  {
    id: "review",
    title: "review before it ships",
    body: "approve a line, request changes, edit the text, or regenerate just that line's audio. editing a line marks its old audio outdated.",
    chips: ["approve", "request changes", "regenerate"],
  },
  {
    id: "export",
    title: "export the dub",
    body: "subtitles export as soon as a project has segments. the dubbed video and audio unlock once every line is approved and its audio fits.",
    chips: ["MP4", "MP3", "SRT", "VTT"],
  },
];

export const reviewChecks = [
  {
    id: "timing",
    ext: "TIME",
    title: "timing is measured, not assumed",
    body: "a dubbed line is flagged when it runs more than 300 ms or 15% off the original, whichever allowance is larger.",
  },
  {
    id: "changes",
    ext: "FIX",
    title: "send a line back",
    body: "request changes on any line. the dubbed video and audio stay locked until every line is approved.",
  },
  {
    id: "outdated",
    ext: "OLD",
    title: "stale audio can't slip out",
    body: "edit a translation and its old audio is marked outdated while the line returns to pending review.",
  },
  {
    id: "retry",
    ext: "RETRY",
    title: "retry one line, not the whole video",
    body: "if a voice fails to generate, regenerate only that line and keep everything else you've approved.",
  },
];

export const statement =
  "dubbing is editing, not magic. DubForge keeps the original line, its translation and the timing side by side, so every line is checked before anything ships.";

export const todayFacts = [
  ["source language", "English"],
  ["dub into", "Hindi or Bengali"],
  ["voices", "Edge TTS or Meta MMS-TTS"],
  ["review", "approve, request changes, regenerate per line"],
  ["export", "MP4, MP3, SRT and VTT"],
];

export const faqs = [
  [
    "what is DubForge?",
    "a workspace for dubbing video into another language. you upload a video, get a timed transcript, a translation and a dubbed voice for every line, review them, then export.",
  ],
  [
    "which languages work today?",
    "the source audio is English, and you can dub into Hindi or Bengali. each project translates into one target language.",
  ],
  [
    "what runs under the hood?",
    "faster-whisper (or AssemblyAI, if you add a key) for transcription, Meta's NLLB-200 for translation, and Edge TTS or Meta's MMS-TTS models for the voices. FFmpeg handles the audio and video.",
  ],
  [
    "does it clone the original speaker's voice?",
    "no. lines are spoken by stock text-to-speech voices. DubForge checks timing, not vocal likeness.",
  ],
  [
    "what happens when a dubbed line runs long?",
    "it's flagged as a duration mismatch when the clip is more than 300 ms or 15% off the original line, whichever allowance is larger. edit the line or regenerate its audio, then review it again.",
  ],
  [
    "what can i export?",
    "SRT and VTT subtitles are available as soon as a project has segments. MP3 audio and the MP4 with the dubbed track unlock once every line is approved and has usable audio.",
  ],
  [
    "can i use the dubbed audio commercially?",
    "check first. DubForge is an MVP: the Edge TTS option uses an unofficial service meant for demos, and MMS-TTS has its own license terms. review the license of the voice you use before publishing.",
  ],
  [
    "can a team review together?",
    "not yet. this version has no user accounts or roles, just projects, their lines and review states.",
  ],
  [
    "how much does it cost?",
    "there is no pricing yet. DubForge is in early access.",
  ],
].map(([q, a]) => ({ q, a }));

export const footerColumns = [
  {
    title: "explore",
    links: [
      ["how it works", "#how"],
      ["review pass", "#review"],
      ["early access", "#start"],
      ["faq", "#faq"],
    ],
  },
  {
    title: "try it",
    links: [["open workspace", "/app"]],
  },
];

// Open-source and third-party pieces the pipeline is built on (plain credits, no links).
export const builtWith = [
  "faster-whisper",
  "AssemblyAI",
  "NLLB-200",
  "Edge TTS",
  "MMS-TTS",
  "FFmpeg",
];

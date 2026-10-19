// All page copy and layout data lives here so components stay presentational.
export const brand = "DubForge";

export const navLinks = [
  { label: "features", href: "#feat" },
  { label: "pricing", href: "#pr" },
  { label: "trust", href: "#" },
  { label: "changelog", href: "#" },
  { label: "careers", href: "#" },
];

// Hero decorations are positioned on a fixed 1440px canvas.
export const heroClips = [
  {
    file: "translate-anything.mov",
    art: "art1",
    x: 140,
    y: 76,
    w: 123,
    h: 232,
  },
  { file: "voice-match.mov", art: "art2", x: 543, y: 26, w: 181, h: 130 },
  { file: "multi-language.mov", art: "art3", x: 1011, y: 62, w: 250, h: 150 },
  { file: "review-pass.mov", art: "art4", x: 1278, y: 379, w: 147, h: 278 },
  { file: "dubbing-studio.mov", art: "art5", x: 53, y: 406, w: 221, h: 148 },
];

export const decor = [
  { type: "tag", tone: "blue", x: 331, y: 25, rot: 4 },
  { type: "tag", tone: "red", x: 1255, y: 140, rot: -7.5 },
  { type: "kao", text: "^ ω ^", x: 396, y: 121, rot: -8, size: 24 },
  { type: "kao", text: "¯\\_(ツ)_/¯", x: 880, y: 81, rot: -7.7, size: 18 },
  { type: "kao", text: "{ ^-^ }", x: 1200, y: 392, rot: 7, size: 24 },
  { type: "kao", text: "(¬_¬)", x: 305, y: 458, rot: -7.7, size: 18 },
  { type: "folder", x: 326, y: 240 },
  { type: "folder", x: 1170, y: 478 },
  { type: "trash", x: 62, y: 280 },
  { type: "beach", x: 828, y: 202 },
];

export const features = [
  {
    phrases: [
      "DubForge, translate this cut",
      "keep the timing natural",
      "show me the review pass",
    ],
    title: "translate without losing the edit",
    body: "move from source audio to a reviewable localized cut while the timing, intent, and scene context stay together.",
    windowTitle: "Translation desk",
    art: "art3",
  },
  {
    phrases: [
      "match the speaker tone",
      "flag this line for review",
      "export the approved version",
    ],
    title: "review every voice in one place",
    body: "keep dialogue, translations, approvals, and final delivery connected in a focused browser workspace.",
    windowTitle: "Review room",
    art: "art2",
  },
];

export const manifesto = [
  "great localization should preserve the feeling of the original performance.",
  "DubForge keeps the creative team close to the words, timing, and voice at every step.",
  "upload a cut, shape the translation, and ship the version that feels right.",
];

export const marqueeWords = ["they", "use", "it", "every", "day"];

// Placeholder testimonials — replace with real ones.
export const testimonials = [
  [
    "alex rivera",
    "@alex",
    "this is the first ai thing that actually feels like a tool, not a chat window.",
    "4/2/26, 9:14 AM",
  ],
  [
    "sam okafor",
    "@samok",
    "been screenshotting everything into a chatbot. this is the 10x version.",
    "4/6/26, 6:12 PM",
  ],
  [
    "jo tanaka",
    "@jotanaka",
    "learning my editing app right now with it. so good.",
    "4/6/26, 5:46 PM",
  ],
  [
    "priya nair",
    "@priyan",
    "my favorite onboarding in a long time. so unique and engaging.",
    "4/27/26, 1:51 PM",
  ],
  [
    "mika lund",
    "@mikalund",
    "it pointed at the exact button i was hunting for. tiny thing, huge deal.",
    "5/1/26, 11:20 AM",
  ],
  [
    "dev patel",
    "@devp",
    "asked it to tidy my inbox out loud and it just… did.",
    "5/3/26, 8:02 PM",
  ],
  [
    "lee chen",
    "@leechen",
    "showed my dad. he installed it in two minutes.",
    "5/9/26, 3:30 PM",
  ],
  [
    "nora blake",
    "@norab",
    "the draw-on-screen thing is wild.",
    "5/12/26, 10:05 AM",
  ],
  [
    "omar haddad",
    "@omarh",
    "feels like having a patient friend sitting next to me.",
    "5/20/26, 7:44 PM",
  ],
  [
    "ines costa",
    "@inesc",
    "finally an ai interface i don’t have to type into.",
    "5/22/26, 2:18 PM",
  ],
  [
    "kai morgan",
    "@kaim",
    "replaced three tutorials for me this week.",
    "5/28/26, 9:50 AM",
  ],
  [
    "zoe wright",
    "@zoew",
    "privacy approach is exactly what i wanted.",
    "6/1/26, 12:31 PM",
  ],
].map(([name, handle, text, date]) => ({ name, handle, text, date }));

export const plans = [
  {
    name: "free",
    blurb: "best for trying it out",
    monthly: 0,
    yearly: 0,
    note: "free forever, no card needed",
    cta: "start free",
    variant: "secondary",
    includes: [
      "25 talk messages a month",
      "plenty of dictation",
      "25 agent messages a month",
    ],
  },
  {
    name: "pro",
    blurb: "best for everyday use",
    monthly: 20,
    yearly: 16,
    popular: true,
    cta: "get pro",
    variant: "primary",
    includes: [
      "unlimited talk",
      "unlimited dictation",
      "150 agent messages a month",
    ],
  },
  {
    name: "max",
    blurb: "best for power users",
    monthly: 100,
    yearly: 80,
    cta: "get max",
    variant: "secondary",
    includes: [
      "unlimited talk",
      "unlimited dictation",
      "1,000 agent messages a month",
    ],
  },
];

export const faqs = [
  [
    "what is DubForge?",
    "DubForge is a browser workspace for translating, reviewing, dubbing, and exporting video dialogue without losing the context of the original cut.",
  ],
  [
    "does it work in the browser?",
    "yes. the workspace is designed to run in the browser, so your team can review the same project without installing a desktop app.",
  ],
  [
    "can we review translations together?",
    "yes. each project keeps the source line, localized line, speaker context, and review state together.",
  ],
  [
    "what does DubForge preserve?",
    "timing, speaker intent, scene context, and the character of the original performance stay visible throughout the workflow.",
  ],
  [
    "which languages are supported?",
    "language availability depends on the configured project voices and translation services. DubForge keeps the workflow ready for multilingual delivery.",
  ],
  [
    "can we export approved work?",
    "yes. once the project is reviewed, approved deliverables can be exported from the workspace.",
  ],
  [
    "do i need to install anything?",
    "no. DubForge is built as a web workspace, so there is no downloadable app requirement.",
  ],
  [
    "is there a free way to try it?",
    "the workspace can be explored with a starter project before you commit to a plan.",
  ],
  [
    "can i invite collaborators?",
    "yes. projects are structured for a shared review process across editors, translators, and producers.",
  ],
  ["can i cancel anytime?", "yes. plans are month-to-month with no lock-in."],
].map(([q, a]) => ({ q, a }));

export const footerColumns = [
  {
    title: "product",
    links: [
      ["features", "#feat"],
      ["pricing", "#pr"],
      ["changelog", "#"],
      ["try it", "#"],
    ],
  },
  {
    title: "resources",
    links: [
      ["trust", "#"],
      ["privacy", "#"],
      ["referrals", "#"],
      ["support", "#"],
    ],
  },
  {
    title: "connect",
    links: [
      ["instagram", "#"],
      ["x (twitter)", "#"],
      ["linkedin", "#"],
      ["youtube", "#"],
    ],
  },
];

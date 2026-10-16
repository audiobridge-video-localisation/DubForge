// Small inline icons used by the menubar and buttons.
export const Apple = (props) => (
  <svg viewBox="0 0 14 17" fill="currentColor" {...props}>
    <path d="M11.6 9c0-2 1.6-2.9 1.7-3-.9-1.4-2.4-1.5-2.9-1.6-1.2-.1-2.4.7-3 .7-.6 0-1.6-.7-2.6-.7C3.4 4.4 2 5.2 1.3 6.5c-1.5 2.6-.4 6.4 1 8.5.7 1 1.5 2.1 2.6 2.1 1 0 1.4-.7 2.6-.7s1.6.7 2.7.7 1.8-1 2.5-2c.8-1.1 1.1-2.2 1.1-2.3 0 0-2.2-.9-2.2-3.8zM9.6 2.9C10.2 2.2 10.6 1.2 10.5.2c-.9 0-2 .6-2.6 1.3-.6.6-1.1 1.6-.9 2.6 1 .1 2-.5 2.6-1.2z" />
  </svg>
);

export const Windows = (props) => (
  <svg viewBox="0 0 20 20" fill="currentColor" {...props}>
    <path d="M2 3.5l7-1v7H2zM10 2.4l8-1.2v8.3h-8zM2 10.5h7v7l-7-1zM10 10.5h8v8.3l-8-1.2z" />
  </svg>
);

const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export const Wifi = () => (
  <svg viewBox="0 0 16 16" {...stroke}>
    <path d="M1.5 6a9 9 0 0 1 13 0M3.7 8.6a6 6 0 0 1 8.6 0M6 11.2a3 3 0 0 1 4 0" />
    <circle cx="8" cy="13.4" r=".6" fill="currentColor" />
  </svg>
);
export const Headphones = () => (
  <svg viewBox="0 0 16 16" {...stroke}>
    <path d="M2.5 10V8a5.5 5.5 0 0 1 11 0v2M2.5 9h2v4h-2zM11.5 9h2v4h-2z" />
  </svg>
);
export const Bluetooth = () => (
  <svg viewBox="0 0 16 16" {...stroke}>
    <path d="M4.5 5l7 6-3.5 3V2l3.5 3-7 6" />
  </svg>
);

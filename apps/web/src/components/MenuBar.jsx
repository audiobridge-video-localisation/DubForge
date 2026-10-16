import useClock from "../hooks/useClock.js";
import { brand, navLinks } from "../data/content.js";
import { Bluetooth, Headphones, Wifi } from "./ui/Icons.jsx";
import "./MenuBar.css";

const Eye = ({ delay }) => (
  <g className="eye" style={{ animationDelay: delay }}>
    <ellipse
      cx="0"
      cy="16"
      rx="8"
      ry="10"
      fill="#fff"
      stroke="#000"
      strokeWidth="2"
    />
    <circle className="pupil" cx="0" cy="16" r="3.2" fill="#000" />
  </g>
);

export default function MenuBar() {
  const time = useClock();
  return (
    <header className="menubar">
      <div className="left">
        <nav className="menu-items">
          <a className="brand" href="#">
            {brand}
          </a>
          {navLinks.map((l) => (
            <a key={l.label} href={l.href}>
              {l.label}
            </a>
          ))}
        </nav>
      </div>

      <svg className="logo" viewBox="0 0 56 32" aria-label="logo">
        <g transform="translate(18 0)">
          <Eye />
        </g>
        <g transform="translate(38 0)">
          <Eye delay=".08s" />
        </g>
      </svg>

      <div className="right">
        <div className="status">
          <Wifi />
          <Headphones />
          <Bluetooth />
          <span className="time">{time}</span>
        </div>
        <a className="getbtn" href="/app">
          open workspace
        </a>
      </div>
    </header>
  );
}

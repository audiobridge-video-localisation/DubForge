import { useRef } from "react";
import { statement } from "../data/content.js";
import useScrollProgress from "../hooks/useScrollProgress.js";
import "./Statement.css";

// A pinned sentence that lights up word by word as you scroll through the section.
export default function Statement() {
  const section = useRef(null);
  useScrollProgress(section, "pin");
  const words = statement.split(" ");
  return (
    <section className="stmt" ref={section}>
      <div className="stmt-pin">
        <div className="arches" aria-hidden="true" />
        <span className="plabel">how we think</span>
        <p className="stmt-text">
          {words.map((word, i) => (
            <span
              className="w"
              key={i}
              style={{ "--s": (0.08 + (0.74 * i) / words.length).toFixed(3) }}
            >
              {word}{" "}
            </span>
          ))}
        </p>
      </div>
    </section>
  );
}

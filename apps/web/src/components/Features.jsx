import { useRef } from "react";
import { features } from "../data/content.js";
import useReveal from "../hooks/useReveal.js";
import useFocusedChild from "../hooks/useFocusedChild.js";
import MacWindow from "./ui/MacWindow.jsx";
import Bubble from "./ui/Bubble.jsx";
import Waveform from "./ui/Waveform.jsx";
import "./Features.css";

function FeatureRow({ feature, flip, active }) {
  const [ref, revealed] = useReveal(0.15);
  const cls = [
    "feat-row",
    flip && "align-right",
    revealed && "in",
    revealed && !active && "dimmed",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div ref={ref} className={cls}>
      <div className="copy">
        <Bubble phrases={feature.phrases} />
        <Waveform live={active} />
        <div>
          <h3>{feature.title}</h3>
          <p>{feature.body}</p>
        </div>
      </div>
      <MacWindow
        title={feature.windowTitle}
        className="feat-win"
        screenClass={`${feature.art} ${active ? "playing" : ""}`}
      >
        <div className="ph">feature demo</div>
        <div className="player">
          <div className="pplay">
            <i />
          </div>
          <div className="pbar">
            <div className="pfill" />
          </div>
        </div>
      </MacWindow>
    </div>
  );
}

export default function Features() {
  const section = useRef(null);
  const focused = useFocusedChild(section, ".feat-row");

  return (
    <section className="feat" id="feat" ref={section}>
      {features.map((f, i) => (
        <FeatureRow
          key={f.title}
          feature={f}
          flip={i % 2 === 1}
          active={focused === i}
        />
      ))}
    </section>
  );
}

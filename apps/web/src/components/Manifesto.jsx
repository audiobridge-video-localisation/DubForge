import { manifesto } from "../data/content.js";
import useReveal from "../hooks/useReveal.js";
import MacWindow from "./ui/MacWindow.jsx";
import "./Manifesto.css";

export default function Manifesto() {
  const [ref, revealed] = useReveal();
  return (
    <section ref={ref} className={`man reveal ${revealed ? "in" : ""}`}>
      <div className="arches" />
      <div className="rainbow" />
      <span className="plabel">the dream</span>
      <MacWindow title="notes" className="notes">
        <div className="paper">
          {manifesto.map((line, i) => (
            <p key={i}>
              {line}
              {i === manifesto.length - 1 && <span className="caret" />}
            </p>
          ))}
          <div className="sig">— the founder</div>
        </div>
      </MacWindow>
    </section>
  );
}

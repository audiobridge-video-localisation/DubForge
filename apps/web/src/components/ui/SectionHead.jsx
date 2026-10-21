import useReveal from "../../hooks/useReveal.js";

// Shared section header: a small label, the display title and an optional sub line.
export default function SectionHead({ label, title, sub }) {
  const [ref, revealed] = useReveal();
  return (
    <div ref={ref} className={`sec-head reveal ${revealed ? "in" : ""}`}>
      <span className="plabel">{label}</span>
      <h2 className="sec-title">{title}</h2>
      {sub && <p className="sec-sub">{sub}</p>}
    </div>
  );
}

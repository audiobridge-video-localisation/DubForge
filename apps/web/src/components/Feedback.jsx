import { testimonials } from "../data/content.js";
import useReveal from "../hooks/useReveal.js";
import Marquee from "./Marquee.jsx";
import TestimonialCard from "./TestimonialCard.jsx";
import "./Feedback.css";

const COLUMN_OFFSETS = [0, 36, 12];
const columns = COLUMN_OFFSETS.map((_, c) =>
  testimonials.map((t, i) => ({ t, i })).filter(({ i }) => i % 3 === c),
);

export default function Feedback() {
  const [ref, revealed] = useReveal();
  return (
    <section ref={ref} className={`fb reveal ${revealed ? "in" : ""}`} id="fb">
      <span className="plabel">feedback</span>
      <Marquee />
      <div className="wall">
        {columns.map((col, c) => (
          <div key={c} className="col" style={{ marginTop: COLUMN_OFFSETS[c] }}>
            {col.map(({ t, i }) => (
              <TestimonialCard key={i} item={t} index={i} />
            ))}
          </div>
        ))}
      </div>
      <div className="banner">
        25,000+ happy users and counting. <a href="#">join them</a>
      </div>
    </section>
  );
}

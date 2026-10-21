import { useState } from "react";
import { faqs } from "../data/content.js";
import SectionHead from "./ui/SectionHead.jsx";
import "./Faq.css";

export default function Faq() {
  const [open, setOpen] = useState(0); // one answer open at a time
  return (
    <section className="faq" id="faq">
      <SectionHead
        label="faq"
        title="straight answers"
        sub="what DubForge does today, and what it doesn't."
      />
      <div className="faq-list">
        {faqs.map((item, i) => (
          <div key={item.q} className={`qa ${open === i ? "open" : ""}`}>
            <button
              type="button"
              aria-expanded={open === i}
              onClick={() => setOpen(open === i ? -1 : i)}
            >
              {item.q}
            </button>
            <div className="a">
              <div>
                <p>{item.a}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

import { useState } from "react";
import { faqs } from "../data/content.js";
import "./Faq.css";

export default function Faq() {
  const [open, setOpen] = useState(0); // one answer open at a time
  return (
    <section className="faq">
      <h2 className="sec-title">frequently asked questions</h2>
      <p className="sec-sub">
        what to know about the DubForge workflow and getting started.
      </p>
      <div className="faq-list">
        {faqs.map((item, i) => (
          <div key={item.q} className={`qa ${open === i ? "open" : ""}`}>
            <button onClick={() => setOpen(open === i ? -1 : i)}>
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

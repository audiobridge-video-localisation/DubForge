import { useState } from "react";
import { plans } from "../data/content.js";
import PlanCard from "./PlanCard.jsx";
import "./Pricing.css";

export default function Pricing() {
  const [yearly, setYearly] = useState(false);
  return (
    <section className="pr" id="pr">
      <span className="plabel">pricing</span>
      <h2 className="sec-title">localization that fits the team</h2>
      <p className="sec-sub">
        simple plans for independent creators and production teams.
      </p>

      <div className="toggle">
        <button className={yearly ? "" : "on"} onClick={() => setYearly(false)}>
          monthly
        </button>
        <button className={yearly ? "on" : ""} onClick={() => setYearly(true)}>
          yearly<em>-20%</em>
        </button>
      </div>

      <div className="plans">
        {plans.map((p) => (
          <PlanCard key={p.name} plan={p} yearly={yearly} />
        ))}
      </div>

      <div className="student">
        <b>&lt; student discount &gt;</b> show a school email or student id and
        get 50% off your first month on pro. <a href="#">reach out to us</a>
      </div>
    </section>
  );
}

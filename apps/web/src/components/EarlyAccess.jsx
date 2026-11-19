import { todayFacts } from "../data/content.js";
import Button from "./ui/Button.jsx";
import DeskWindow from "./ui/DeskWindow.jsx";
import SectionHead from "./ui/SectionHead.jsx";
import "./EarlyAccess.css";

// No plans or prices: DubForge is an MVP, so this section says what works today.
export default function EarlyAccess() {
  return (
    <section className="start" id="start">
      <SectionHead
        label="early access"
        title="try the pipeline on your own video"
        sub="DubForge is an MVP, so there are no plans or prices yet. here is exactly what works today."
      />
      <div className="start-grid">
        <DeskWindow ext="NOW" title="what works today">
          <dl className="facts">
            {todayFacts.map(([term, value]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </DeskWindow>
        <div className="start-cta">
          <h3>no sign-up, no card</h3>
          <p>
            this version has no accounts or billing. open the workspace, create
            a project and upload a video to see how far it gets.
          </p>
          <div className="ctas">
            <Button variant="primary" href="/app">
              open workspace
            </Button>
            <Button variant="secondary" href="#how">
              how it works
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

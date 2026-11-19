import { useEffect, useRef, useState } from "react";
import { pipelineSteps } from "../data/content.js";
import { useDeskLang } from "../hooks/useDeskLang.js";
import useScrollProgress from "../hooks/useScrollProgress.js";
import DeskWindow from "./ui/DeskWindow.jsx";
import SectionHead from "./ui/SectionHead.jsx";
import { scenes } from "./PipelineScenes.jsx";
import "./Pipeline.css";

// Pinned walkthrough: the steps scroll on the left, and the screen on the right follows
// whichever step is in the middle of the viewport. On small screens each step carries
// its own screen instead.
export default function Pipeline() {
  const lang = useDeskLang();
  const track = useRef(null);
  const stepRefs = useRef([]);
  const [active, setActive] = useState(0);
  useScrollProgress(track, "line");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries)
          if (entry.isIntersecting) setActive(Number(entry.target.dataset.i));
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    stepRefs.current.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <section className="how" id="how">
      <SectionHead
        label="how it works"
        title="from upload to export"
        sub="what actually runs when you drop a video in, one stage at a time."
      />
      <div className="how-grid">
        <div className="how-steps" ref={track}>
          <div className="how-rail" aria-hidden="true">
            <i />
          </div>
          {pipelineSteps.map((step, i) => {
            const Scene = scenes[step.id];
            return (
              <article
                key={step.id}
                className={`how-step ${active === i ? "on" : ""}`}
                data-i={i}
                ref={(el) => (stepRefs.current[i] = el)}
              >
                <span className="dot" aria-hidden="true">
                  {i + 1}
                </span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
                <div className="chips">
                  {step.chips.map((chip) => (
                    <span key={chip}>{chip}</span>
                  ))}
                </div>
                <div className="step-inline">
                  <DeskWindow ext="DF" title="DubForge / project">
                    <div className="scene on static">
                      <Scene lang={lang} />
                    </div>
                  </DeskWindow>
                </div>
              </article>
            );
          })}
        </div>

        <div className="how-stage" aria-hidden="true">
          <DeskWindow ext="DF" title="DubForge / project">
            <div className="stage-body">
              {pipelineSteps.map((step, i) => {
                const Scene = scenes[step.id];
                return (
                  <div
                    key={step.id}
                    className={`scene ${active === i ? "on" : ""}`}
                  >
                    <Scene lang={lang} />
                  </div>
                );
              })}
            </div>
          </DeskWindow>
        </div>
      </div>
    </section>
  );
}

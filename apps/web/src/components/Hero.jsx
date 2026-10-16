import { decor, heroClips } from "../data/content.js";
import MacWindow from "./ui/MacWindow.jsx";
import Button from "./ui/Button.jsx";
import Draggable from "./ui/Draggable.jsx";
import Decor from "./Decor.jsx";
import "./Hero.css";

export default function Hero() {
  return (
    <section className="hero">
      <div className="canvas">
        {heroClips.map((clip) => (
          <div key={clip.file}>
            <Draggable
              x={clip.x}
              y={clip.y}
              style={{ width: clip.w, height: clip.h }}
            >
              <MacWindow className="fill" screenClass={clip.art}>
                <div className="ph">localization preview</div>
              </MacWindow>
            </Draggable>
            <div
              className="cap"
              style={{ left: clip.x, top: clip.y + clip.h + 10, width: clip.w }}
            >
              {clip.file}
            </div>
          </div>
        ))}
        {decor.map((item, index) => (
          <Decor key={index} item={item} />
        ))}

        <h1>DubForge</h1>
        <div className="sub">
          localize every voice, without losing the feeling
        </div>
        <div className="ctas">
          <Button variant="primary" href="/app">
            open workspace
          </Button>
          <Button variant="secondary" href="#feat">
            see the workflow
          </Button>
        </div>
        <div className="note">upload · review · translate · dub · export</div>

        <MacWindow className="big" title="DubForge / localization desk">
          <img
            className="hero-art"
            src="/assets/dubforge-hero-localization.jpg"
            alt="Abstract blue and white localization artwork with subtitle tiles"
          />
          <div className="playpill">
            <i />
            watch the workflow
          </div>
        </MacWindow>
      </div>
    </section>
  );
}

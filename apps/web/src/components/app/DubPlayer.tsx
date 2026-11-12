import { useEffect, useRef, useState, type RefObject } from "react";

import {
  exportDownloadUrl,
  type ExportJob,
  type ExportKind,
  type Segment,
} from "../../api/client";
import { formatTimestamp } from "../../lib/workflow";

// Plays the finished dub (the exported MP4 with the dubbed track, or the MP3) and tells
// the transcript which line is playing. Only exports can be played: the API serves no
// other media files.
export function DubPlayer({
  jobs,
  segments,
  mediaRef,
  activeId,
  onActive,
}: {
  jobs: Partial<Record<ExportKind, ExportJob>>;
  segments: Segment[];
  mediaRef: RefObject<HTMLMediaElement | null>;
  activeId: string | null;
  onActive: (segmentId: string | null) => void;
}) {
  const ready: ExportKind[] = (["mp4", "mp3"] as const).filter(
    (kind) => jobs[kind]?.status === "completed",
  );
  const [chosen, setChosen] = useState<ExportKind | null>(null);
  const kind = chosen && ready.includes(chosen) ? chosen : ready[0];
  const job = kind ? jobs[kind] : undefined;

  const frame = useRef(0);
  const card = useRef<HTMLDivElement>(null);
  const [offscreen, setOffscreen] = useState(false);
  const [playing, setPlaying] = useState(false);

  // is the player card on screen? if not, a mini bar keeps the controls reachable
  useEffect(() => {
    const el = card.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setOffscreen(!entry.isIntersecting),
      { threshold: 0.1 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [kind]);

  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  if (!job || !kind) return null;

  const stale = segments.some(
    (s) =>
      s.artifact && new Date(s.artifact.updated_at) > new Date(job.updated_at),
  );

  function tick() {
    const el = mediaRef.current;
    if (!el) return;
    const ms = el.currentTime * 1000;
    const hit = segments.find((s) => ms >= s.start_ms && ms < s.end_ms);
    onActive(hit?.id ?? null);
  }
  function loop() {
    tick();
    frame.current = requestAnimationFrame(loop);
  }
  function stop() {
    cancelAnimationFrame(frame.current);
    tick();
  }

  const src = exportDownloadUrl(job.id);
  const events = {
    onPlay: () => {
      setPlaying(true);
      cancelAnimationFrame(frame.current);
      loop();
    },
    onPause: () => {
      setPlaying(false);
      stop();
    },
    onEnded: () => {
      setPlaying(false);
      stop();
    },
    onSeeked: tick,
    onTimeUpdate: tick,
  };

  const active = segments.find((s) => s.id === activeId);

  return (
    <>
      <div className="player" ref={card}>
        <div className="player-head">
          <h3>Preview the dub</h3>
          {ready.length > 1 && (
            <div className="seg" role="group" aria-label="Preview format">
              {ready.map((k) => (
                <button
                  key={k}
                  type="button"
                  className={k === kind ? "seg-on" : undefined}
                  aria-pressed={k === kind}
                  onClick={() => setChosen(k)}
                >
                  {k === "mp4" ? "Video" : "Audio"}
                </button>
              ))}
            </div>
          )}
        </div>

        {kind === "mp4" ? (
          <video
            key={src}
            ref={mediaRef as RefObject<HTMLVideoElement>}
            className="player-video"
            src={src}
            controls
            playsInline
            preload="metadata"
            {...events}
          />
        ) : (
          <audio
            key={src}
            ref={mediaRef as RefObject<HTMLAudioElement>}
            className="player-audio"
            src={src}
            controls
            preload="metadata"
            {...events}
          />
        )}

        <p className="player-now" aria-live="polite">
          {active
            ? `Line ${active.index + 1} · ${active.translated_text ?? active.text}`
            : "Press play, or choose a line's time in the table to jump to it."}
        </p>
        {stale && (
          <p className="player-stale" role="status">
            You've changed lines since this export was built. Export again to
            hear the latest.
          </p>
        )}
      </div>

      {offscreen && (playing || active) && (
        <div className="mini-player" role="region" aria-label="Playback">
          <button
            type="button"
            className="btn btn-sm btn-primary"
            onClick={() => {
              const el = mediaRef.current;
              if (!el) return;
              if (el.paused) void el.play();
              else el.pause();
            }}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <span>
            {active
              ? `Line ${active.index + 1}`
              : formatTimestamp((mediaRef.current?.currentTime ?? 0) * 1000)}
          </span>
          <button
            type="button"
            className="btn btn-sm btn-quiet"
            onClick={() =>
              card.current?.scrollIntoView({
                behavior: "smooth",
                block: "center",
              })
            }
          >
            Show player
          </button>
        </div>
      )}
    </>
  );
}

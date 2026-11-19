import type { RefObject } from "react";

import { sourceMediaUrl, type Segment } from "../../api/client";

// The uploaded video, so a reviewer can see and hear the original line they are checking.
// Selecting a line in the table seeks it (see MediaPanel); playing it highlights the line.
export function SourcePlayer({
  mediaId,
  segments,
  videoRef,
  onActive,
}: {
  mediaId: string;
  segments: Segment[];
  videoRef: RefObject<HTMLVideoElement | null>;
  onActive: (segmentId: string | null) => void;
}) {
  function onTimeUpdate() {
    const ms = (videoRef.current?.currentTime ?? 0) * 1000;
    const current = segments.find((s) => ms >= s.start_ms && ms < s.end_ms);
    onActive(current?.id ?? null);
  }

  return (
    <div className="source-player">
      <video
        ref={videoRef}
        src={sourceMediaUrl(mediaId)}
        controls
        preload="metadata"
        playsInline
        onTimeUpdate={onTimeUpdate}
      >
        Your browser can't play this video.
      </video>
    </div>
  );
}

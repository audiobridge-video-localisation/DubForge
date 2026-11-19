import type { ReactNode } from "react";

import type { Tone } from "../../lib/workflow";

export function StatusBadge({
  tone = "neutral",
  pulse = false,
  children,
}: {
  tone?: Tone;
  pulse?: boolean;
  children: ReactNode;
}) {
  return (
    <span className={`badge badge-${tone}`}>
      <i className={pulse ? "pulse" : undefined} aria-hidden="true" />
      {children}
    </span>
  );
}

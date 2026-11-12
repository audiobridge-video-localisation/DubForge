import { Link } from "react-router-dom";

import type { MediaWithJob, Project } from "../../api/client";
import {
  WORKFLOW_STEPS,
  deriveWorkflow,
  detectTargetLanguage,
  lastUpdated,
  primaryMedia,
  relativeTime,
} from "../../lib/workflow";
import { StatusBadge } from "./StatusBadge";

// Project name, status, target language, current workflow step and last-updated time,
// plus the five-step workflow with the current step marked.
export function ProjectHeader({
  project,
  media,
}: {
  project: Project;
  media: MediaWithJob[];
}) {
  const workflow = deriveWorkflow(primaryMedia(media));
  const language = detectTargetLanguage(media);
  const updated = lastUpdated(project, media);
  const live = workflow.step === 1 && workflow.tone === "info";

  return (
    <section className="card project-header" aria-label="Project overview">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/app">Projects</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{project.name}</span>
      </nav>

      <div className="project-title">
        <h1>{project.name}</h1>
        <StatusBadge tone={workflow.tone} pulse={live}>
          {workflow.label}
        </StatusBadge>
      </div>
      <p className="project-detail" role="status">
        {workflow.detail}
      </p>

      <dl className="meta">
        <div>
          <dt>Target language</dt>
          <dd>{language ?? "Not detected yet"}</dd>
        </div>
        <div>
          <dt>Current step</dt>
          <dd>
            {workflow.step + 1} of {WORKFLOW_STEPS.length} ·{" "}
            {WORKFLOW_STEPS[workflow.step]}
          </dd>
        </div>
        <div>
          <dt>Last updated</dt>
          <dd title={updated.toLocaleString()}>{relativeTime(updated)}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>{new Date(project.created_at).toLocaleDateString()}</dd>
        </div>
      </dl>

      <ol className="stepper" aria-label="Workflow">
        {WORKFLOW_STEPS.map((step, i) => {
          const state =
            i < workflow.step
              ? "done"
              : i === workflow.step
                ? workflow.tone === "ok"
                  ? "done"
                  : "current"
                : "todo";
          return (
            <li
              key={step}
              className={`wf-step wf-${state}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="wf-dot" aria-hidden="true">
                {state === "done" ? "✓" : i + 1}
              </span>
              <span className="wf-name">{step}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

import { Check, CircleAlert } from "lucide-react";
import Spinner from "./Spinner.jsx";

const LABELS = {
  intake: "Trip details",
  retrieve: "Travel guides",
  fetch: "Weather and costs",
  draft: "Itinerary draft",
  locate: "Place locations",
  check: "Plan checks",
  revise: "Draft revision",
};

export default function ProgressSteps({ steps = [], status = "idle", message = "" }) {
  const counts = {};
  const announcement = status === "error" ? message : status === "complete" ? "Planning finished. Your itinerary is below." : steps.at(-1)?.message || "Planning in progress";

  return (
    <section aria-labelledby="progress-heading" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id="progress-heading" className="text-h3">Planning progress</h3>
        {status === "complete" && (
          <span className="inline-flex items-center gap-1.5 rounded-pill bg-success-soft px-3 py-1 text-small font-semibold text-success">
            <Check aria-hidden="true" className="size-4" />
            Finished
          </span>
        )}
      </div>
      <p aria-live="polite" aria-atomic="true" className="sr-only">{announcement}</p>
      {status === "idle" && <p className="mt-2 text-small text-text-muted">Completed steps appear as the planner reports them.</p>}
      <ol className="mt-4 space-y-3">
        {steps.map((step, index) => {
          counts[step.name] = (counts[step.name] || 0) + 1;
          const round = counts[step.name];
          return (
            <li key={index} className="flex items-start gap-3">
              <Check aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-success" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="text-small text-text">{LABELS[step.name] || step.name}{round > 1 ? ` (round ${round})` : ""}</p>
                  <span className="text-caption text-text-muted">Done · {step.elapsed_seconds.toFixed(1)}s</span>
                </div>
                <p className="mt-1 text-small text-text-muted">{step.message}</p>
              </div>
            </li>
          );
        })}
      </ol>
      {status === "planning" && (
        <p className="mt-4 flex items-center gap-3 text-small font-semibold text-primary"><Spinner className="size-5" showText={false} />Planning in progress</p>
      )}
      {status === "error" && (
        <div className="mt-4 flex items-start gap-3 text-small text-danger">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          <p><strong className="font-semibold">Error</strong><span className="mt-1 block break-words">{message}</span></p>
        </div>
      )}
    </section>
  );
}

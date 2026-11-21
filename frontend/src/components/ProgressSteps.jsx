import { Check, Circle, CircleAlert } from "lucide-react";
import Spinner from "./Spinner.jsx";

const BASE_STEPS = [
  { name: "intake", label: "Trip details" },
  { name: "retrieve", label: "Travel guides" },
  { name: "fetch", label: "Weather and costs" },
  { name: "draft", label: "Itinerary draft" },
  { name: "check", label: "Plan checks" },
];
const LABELS = { ...Object.fromEntries(BASE_STEPS.map(({ name, label }) => [name, label])), revise: "Draft revision" };

function rowsFor(steps, status) {
  if (status === "idle") return BASE_STEPS.map((step) => ({ ...step, key: step.name, state: "pending" }));
  const counts = {};
  const rows = steps.map((step, index) => {
    counts[step.name] = (counts[step.name] || 0) + 1;
    const round = counts[step.name];
    return { ...step, key: `done-${index}`, label: `${LABELS[step.name] || step.name}${round > 1 ? ` (round ${round})` : ""}`, state: "done" };
  });

  if (status === "complete") return rows;
  const last = steps.at(-1)?.name;
  const next = last === "check" ? "finalize" : last === "revise" ? "check" : BASE_STEPS[BASE_STEPS.findIndex((step) => step.name === last) + 1]?.name;
  if (status === "planning" || status === "error") {
    rows.push({ key: "current", name: next, label: next === "finalize" ? "Finalizing the plan" : LABELS[next] || "Preparing your plan", state: status === "error" ? "error" : "active" });
  }
  for (const step of BASE_STEPS) {
    if (!steps.some((done) => done.name === step.name) && step.name !== next) {
      rows.push({ ...step, key: `pending-${step.name}`, state: "pending" });
    }
  }
  return rows;
}

export default function ProgressSteps({ steps = [], status = "idle", message = "" }) {
  const rows = rowsFor(steps, status);
  const announcement = status === "error" ? message : status === "complete" ? "Planning finished. Your itinerary is below." : steps.at(-1)?.message || "";

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
      {status === "idle" && <p className="mt-2 text-small text-text-muted">The planner's steps will appear here.</p>}
      <ol className="mt-4 space-y-3">
        {rows.map((row) => (
          <li key={row.key} className="flex items-start gap-3" aria-current={row.state === "active" ? "step" : undefined}>
            <span className={`mt-0.5 inline-flex min-w-5 shrink-0 ${row.state === "done" ? "text-success" : row.state === "error" ? "text-danger" : row.state === "active" ? "text-primary" : "text-text-muted"}`}>
              {row.state === "done" ? <Check aria-hidden="true" className="size-5" /> : row.state === "error" ? <CircleAlert aria-hidden="true" className="size-5" /> : row.state === "active" ? <Spinner className="size-5" showText={false} /> : <Circle aria-hidden="true" className="size-5" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <p className={`text-small ${row.state === "active" ? "font-semibold text-primary" : row.state === "error" ? "font-semibold text-danger" : row.state === "pending" ? "text-text-muted" : "text-text"}`}>{row.label}</p>
                <span className="text-caption text-text-muted">
                  {row.state === "done" ? `Done · ${row.elapsed_seconds.toFixed(1)}s` : row.state === "active" ? "In progress" : row.state === "error" ? "Error" : "Pending"}
                </span>
              </div>
              {row.state === "done" && <p className="mt-1 text-small text-text-muted">{row.message}</p>}
              {row.state === "error" && <p className="mt-1 break-words text-small text-danger">{message}</p>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

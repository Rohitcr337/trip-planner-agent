import { ChevronDown, CircleCheck, CircleMinus, CircleX } from "lucide-react";

const STATES = {
  PASS: { Icon: CircleCheck, tone: "bg-success-soft text-success" },
  FAIL: { Icon: CircleX, tone: "bg-danger-soft text-danger" },
  SKIPPED: { Icon: CircleMinus, tone: "bg-surface-muted text-text-muted" },
};
const LABELS = { budget: "Budget", logistics: "Travel and timing", sources: "Sources" };

export default function ChecksPanel({ checks = [], revisions = 0 }) {
  return (
    <details className="group rounded-card bg-surface p-4 shadow-1 sm:p-6">
      <summary className="flex min-h-11 cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 rounded-control [&::-webkit-details-marker]:hidden">
        <h3 className="flex-1 text-h3">Plan checks</h3>
        <span className="text-small text-text-muted">Revisions: {revisions}</span>
        <ChevronDown aria-hidden="true" className="size-5 shrink-0 text-text-muted transition-transform duration-(--duration-press) group-open:rotate-180" />
      </summary>
      {checks.length ? (
        <ul className="mt-4 space-y-4 border-t border-border pt-4">
          {checks.map((check, index) => {
            const state = /^\s*skipped:/i.test(check.reason) ? "SKIPPED" : check.passed ? "PASS" : "FAIL";
            const { Icon, tone } = STATES[state];
            return (
              <li key={index}>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-small font-semibold">{LABELS[check.name] || check.name}</p>
                  <span className={`inline-flex items-center gap-1.5 rounded-tag px-2 py-1 text-caption ${tone}`}>
                    <Icon aria-hidden="true" className="size-4 shrink-0" />
                    {state}
                  </span>
                </div>
                <p className="mt-2 break-words text-small text-text-muted">{check.reason}</p>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-4 text-small text-text-muted">No checks were reported.</p>
      )}
    </details>
  );
}

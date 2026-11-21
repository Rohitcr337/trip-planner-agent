import { CircleAlert, CircleCheck, TriangleAlert, Wallet } from "lucide-react";
import { formatInr } from "../format.js";

export default function CostSummary({ estimate = null, budget = null, loading = false }) {
  if (loading) {
    return (
      <section aria-labelledby="cost-heading" aria-busy="true" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
        <h3 id="cost-heading" className="text-h3">Estimated stop costs</h3>
        <p className="sr-only">Calculating estimated stop costs</p>
        <div aria-hidden="true" className="mt-4 space-y-3">
          <div className="h-5 w-32 animate-pulse rounded-tag bg-surface-muted motion-reduce:animate-none" />
          <div className="h-3 animate-pulse rounded-pill bg-surface-muted motion-reduce:animate-none" />
        </div>
      </section>
    );
  }

  if (estimate === null || budget === null) {
    return (
      <section aria-labelledby="cost-heading" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
        <h3 id="cost-heading" className="flex items-center gap-2 text-h3"><Wallet aria-hidden="true" className="size-6 shrink-0 text-primary" />Estimated stop costs</h3>
        <p className="mt-2 text-small text-text-muted">The comparison with your budget will appear once a draft is ready.</p>
      </section>
    );
  }

  const fraction = estimate / budget;
  const tone = fraction <= 0.85 ? "success" : fraction <= 1 ? "warning" : "danger";
  const label = tone === "success" ? "Within budget" : tone === "warning" ? "Close to budget" : `Over budget by ${formatInr(estimate - budget)}`;
  const Icon = tone === "success" ? CircleCheck : tone === "warning" ? TriangleAlert : CircleAlert;
  const tones = {
    success: { status: "bg-success-soft text-success", fill: "bg-success" },
    warning: { status: "bg-warning-soft text-warning", fill: "bg-warning" },
    danger: { status: "bg-danger-soft text-danger", fill: "bg-danger" },
  };

  return (
    <section aria-labelledby="cost-heading" className="animate-enter rounded-card bg-surface p-4 shadow-1 motion-reduce:animate-fade sm:p-6">
      <h3 id="cost-heading" className="text-h3">Estimated stop costs</h3>
      <div className="mt-4 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-h3 tabular-nums">{formatInr(estimate)} <span className="text-small font-normal text-text-muted">estimated</span></p>
        <p className="text-small text-text-muted">of {formatInr(budget)} budget</p>
      </div>
      <div aria-hidden="true" className="mt-3 h-3 overflow-hidden rounded-pill bg-surface-muted">
        <div className={`h-full rounded-pill ${tones[tone].fill}`} style={{ width: `${Math.min(fraction * 100, 100)}%` }} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className={`inline-flex items-center gap-1.5 rounded-pill px-3 py-1 text-small font-semibold ${tones[tone].status}`}>
          <Icon aria-hidden="true" className="size-4 shrink-0" />
          {label}
        </p>
        <p className="text-small text-text-muted">{Math.round(fraction * 100)}% of budget</p>
      </div>
      <p className="mt-4 max-w-prose text-small text-text-muted">
        Meals, local transport and stay are not included in this figure; the planner's budget check accounts for them.
      </p>
    </section>
  );
}

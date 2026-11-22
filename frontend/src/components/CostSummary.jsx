import { CircleAlert, CircleCheck, TriangleAlert, Wallet } from "lucide-react";
import { formatInr } from "../format.js";

const TONES = {
  success: { status: "bg-success-soft text-success", fill: "bg-success", Icon: CircleCheck },
  warning: { status: "bg-warning-soft text-warning", fill: "bg-warning", Icon: TriangleAlert },
  danger: { status: "bg-danger-soft text-danger", fill: "bg-danger", Icon: CircleAlert },
};

export default function CostSummary({ breakdown = null, loading = false }) {
  if (loading) {
    return (
      <section aria-labelledby="cost-heading" aria-busy="true" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
        <h3 id="cost-heading" className="text-h3">Trip cost estimate</h3>
        <p className="sr-only">Calculating the trip estimate</p>
        <div aria-hidden="true" className="mt-4 space-y-3">
          <div className="h-5 w-32 animate-pulse rounded-tag bg-surface-muted motion-reduce:animate-none" />
          <div className="h-3 animate-pulse rounded-pill bg-surface-muted motion-reduce:animate-none" />
        </div>
      </section>
    );
  }

  if (!breakdown) {
    return (
      <section aria-labelledby="cost-heading" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
        <h3 id="cost-heading" className="flex items-center gap-2 text-h3"><Wallet aria-hidden="true" className="size-6 shrink-0 text-primary" />Trip cost estimate</h3>
        <p className="mt-2 text-small text-text-muted">The comparison with your budget will appear once a draft is ready.</p>
      </section>
    );
  }

  const complete = breakdown.complete === true;
  const estimate = complete ? breakdown.estimate_inr : breakdown.stops_inr;
  const budget = breakdown.budget_inr;
  const fraction = complete && budget > 0 ? estimate / budget : null;
  const tone = fraction <= 0.85 ? "success" : fraction <= 1 ? "warning" : "danger";
  const label = tone === "success" ? "Within budget" : tone === "warning" ? "Close to budget" : `Over budget by ${formatInr(estimate - budget)}`;
  const { Icon, status, fill } = TONES[tone];

  return (
    <section aria-labelledby="cost-heading" className="animate-enter rounded-card bg-surface p-4 shadow-1 motion-reduce:animate-fade sm:p-6">
      <h3 id="cost-heading" className="text-h3">{complete ? "Trip cost estimate" : "Estimated stop costs"}</h3>
      <div className="mt-4 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-h3 tabular-nums">{formatInr(estimate)} <span className="text-small font-normal text-text-muted">{complete ? "whole trip, per person" : "stops only"}</span></p>
        {budget !== null && <p className="text-small text-text-muted">{formatInr(budget)} budget</p>}
      </div>
      {fraction !== null ? (
        <>
          <div aria-hidden="true" className="mt-3 h-3 overflow-hidden rounded-pill bg-surface-muted">
            <div className={`h-full rounded-pill ${fill}`} style={{ width: `${Math.min(fraction * 100, 100)}%` }} />
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <p className={`inline-flex items-center gap-1.5 rounded-pill px-3 py-1 text-small font-semibold ${status}`}>
              <Icon aria-hidden="true" className="size-4 shrink-0" />
              {label}
            </p>
            <p className="text-small text-text-muted">{Math.round(fraction * 100)}% of budget</p>
          </div>
        </>
      ) : (
        <p className="mt-3 flex items-start gap-2 text-small text-warning">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          The full trip estimate is unavailable. This figure covers stops only; it cannot confirm that the whole trip fits your budget.
        </p>
      )}
      <dl className="mt-5 space-y-2 border-t border-border pt-4 text-small">
        {[["Stops", breakdown.stops_inr], ["Transport and meals", breakdown.transport_meals_inr], ["Stay", breakdown.stay_inr]].map(([name, amount]) => (
          <div key={name} className="flex flex-wrap justify-between gap-x-4 gap-y-1">
            <dt className="text-text-muted">{name}</dt>
            <dd className="tabular-nums text-text">{amount === null ? "Unavailable" : formatInr(amount)}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-4 text-small text-text-muted">Costs are estimates, not live prices.</p>
    </section>
  );
}

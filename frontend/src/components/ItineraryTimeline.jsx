import { Clock, Info, MapPin, TriangleAlert } from "lucide-react";
import { formatDate, formatInr } from "../format.js";
import SourceBadge from "./SourceBadge.jsx";
import UnverifiedBadge from "./UnverifiedBadge.jsx";

const SLOTS = { morning: "Morning", afternoon: "Afternoon", evening: "Evening" };

function EmptyIllustration() {
  return (
    <svg aria-hidden="true" viewBox="0 0 80 80" className="size-20 text-primary" fill="none">
      <rect x="12" y="10" width="56" height="60" rx="12" className="fill-primary-soft" />
      <path d="M26 27h28M26 40h20M26 53h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <circle cx="54" cy="53" r="4" className="fill-accent" />
    </svg>
  );
}

function ItinerarySkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading itinerary" className="space-y-6">
      <p className="sr-only">Preparing your day-by-day plan</p>
      {[1, 2].map((day) => (
        <div key={day} aria-hidden="true" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
          <div className="h-6 w-32 animate-pulse rounded-tag bg-surface-muted motion-reduce:animate-none" />
          <div className="mt-4 space-y-4 border-l border-border pl-4">
            {[1, 2].map((stop) => (
              <div key={stop} className="space-y-3 rounded-control border border-border p-4">
                <div className="h-4 w-20 animate-pulse rounded-pill bg-surface-muted motion-reduce:animate-none" />
                <div className="h-5 w-2/3 animate-pulse rounded-tag bg-surface-muted motion-reduce:animate-none" />
                <div className="h-4 w-full animate-pulse rounded-tag bg-surface-muted motion-reduce:animate-none" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function UnresolvedIssues({ issues }) {
  if (!issues.length) return null;
  return (
    <section aria-labelledby="unresolved-heading" className="rounded-card bg-warning-soft p-4 text-warning sm:p-6">
      <h3 id="unresolved-heading" className="flex items-center gap-2 text-h3">
        <TriangleAlert aria-hidden="true" className="size-6 shrink-0" />
        Still needs attention
      </h3>
      <p className="mt-2 text-small">These issues remain after the planner's checks. Review them before relying on the plan.</p>
      <ul className="mt-3 list-disc space-y-2 pl-6 text-small">
        {issues.map((issue, index) => <li key={index} className="break-words">{issue}</li>)}
      </ul>
    </section>
  );
}

export default function ItineraryTimeline({ draft = null, costsAreEstimates = false, unresolved = [], status = "idle" }) {
  if (status === "planning") return <ItinerarySkeleton />;
  if (!draft || !draft.days.length) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col items-start rounded-card bg-surface p-4 shadow-1 sm:p-6">
          <EmptyIllustration />
          <p className="mt-4 text-large">{status === "complete" ? "No itinerary was drafted" : "Your next trip starts here"}</p>
          <p className="mt-2 max-w-prose text-text-muted">
            {status === "complete" ? "The planner finished without a day-by-day draft. Review the issues below and try different trip details." : "Choose a destination, pace and interests. Your days, estimated costs and guide sources will appear here."}
          </p>
        </div>
        <UnresolvedIssues issues={unresolved} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {costsAreEstimates && (
        <p className="flex items-start gap-2 rounded-control bg-surface-muted px-4 py-3 text-small text-text-muted">
          <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span><strong className="font-semibold text-text">Costs are estimates.</strong> Confirm current prices and opening times before you go.</span>
        </p>
      )}
      {draft.days.map((day) => {
        const total = day.stops.reduce((sum, stop) => sum + stop.est_cost_inr, 0);
        return (
          <article key={day.day} aria-labelledby={`day-${day.day}-heading`} className="animate-enter rounded-card bg-surface p-4 shadow-1 motion-reduce:animate-fade sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 id={`day-${day.day}-heading`} className="text-h3">Day {day.day}</h3>
                {day.date && <time dateTime={day.date} className="mt-1 block text-small text-text-muted">{formatDate(day.date)}</time>}
              </div>
              <p className="rounded-pill bg-primary-soft px-3 py-1 text-small text-text">{formatInr(total)} <span className="text-text-muted">est. stops</span></p>
            </div>
            {day.weather_note && <p className="mt-3 flex items-start gap-2 rounded-control bg-surface-muted p-3 text-small text-text-muted"><Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />{day.weather_note}</p>}
            {day.stops.length ? (
              <ol className="mt-6 space-y-4 border-l border-border pl-4 sm:pl-6">
                {day.stops.map((stop, index) => (
                  <li key={index} className="relative">
                    <span aria-hidden="true" className="absolute top-6 -left-[21px] size-2 rounded-pill bg-accent sm:-left-[29px]" />
                    <article aria-labelledby={`day-${day.day}-stop-${index}-heading`} className="min-w-0 rounded-control border border-border p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span aria-label={`Stop ${index + 1}`} className="inline-flex size-6 items-center justify-center rounded-pill bg-primary-soft text-caption font-semibold text-primary">{index + 1}</span>
                        <span className="rounded-pill bg-surface-muted px-3 py-1 text-caption text-text-muted">{SLOTS[stop.time_slot]}</span>
                        {stop.kind && <span className="text-caption capitalize text-text-muted">{stop.kind}</span>}
                        {stop.unverified && <UnverifiedBadge />}
                      </div>
                      <h4 id={`day-${day.day}-stop-${index}-heading`} className="mt-3 break-words text-large text-text">{stop.name}</h4>
                      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-2 text-small text-text-muted">
                        <div className="inline-flex min-w-0 items-start gap-1.5"><dt className="sr-only">Area</dt><MapPin aria-hidden="true" className="mt-0.5 size-4 shrink-0" /><dd className="break-words">{stop.area}</dd></div>
                        <div className="inline-flex items-center gap-1.5"><dt className="sr-only">Duration</dt><Clock aria-hidden="true" className="size-4" /><dd>{stop.duration_minutes} min</dd></div>
                        <div className="rounded-pill bg-primary-soft px-3 py-1 text-text"><dt className="sr-only">Estimated cost</dt><dd>{formatInr(stop.est_cost_inr)} est.</dd></div>
                      </dl>
                      {stop.excerpt && <p className="mt-3 max-w-prose break-words text-small text-text">{stop.excerpt.slice(0, 200)}</p>}
                      {stop.notes && <p className="mt-3 max-w-prose break-words text-small text-text-muted">{stop.notes}</p>}
                      <div className="mt-4 flex flex-wrap gap-2">
                        {stop.sources.map((source, sourceIndex) => <SourceBadge key={sourceIndex} source={source} />)}
                      </div>
                    </article>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="mt-4 text-small text-text-muted">No stops were included for this day.</p>
            )}
          </article>
        );
      })}
      <UnresolvedIssues issues={unresolved} />
      {draft.assumptions.length > 0 && (
        <section aria-labelledby="assumptions-heading" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
          <h3 id="assumptions-heading" className="text-h3">Planning assumptions</h3>
          <ul className="mt-3 list-disc space-y-2 pl-6 text-small text-text-muted">
            {draft.assumptions.map((assumption, index) => <li key={index} className="break-words">{assumption}</li>)}
          </ul>
        </section>
      )}
    </div>
  );
}

import { Info } from "lucide-react";

export default function DemoBanner() {
  return (
    <div
      role="status"
      className="flex animate-enter gap-3 rounded-card border border-primary bg-primary-soft p-4 text-text motion-reduce:animate-fade"
    >
      <Info aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-primary" />
      <div>
        <p className="font-semibold">Sample plan (demo)</p>
        <p className="mt-1 text-small text-text-muted">
          The planner is running in demo mode, so this plan was put together offline from the
          travel guides. Check names, times and costs before you go.
        </p>
      </div>
    </div>
  );
}

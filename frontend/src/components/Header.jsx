import { Compass } from "lucide-react";

export default function Header() {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-content items-center gap-3 px-4 py-4 sm:px-6">
        <span
          aria-hidden="true"
          className="relative flex size-10 items-center justify-center rounded-control bg-primary-soft text-primary"
        >
          <Compass className="size-6" strokeWidth={1.75} />
          <span className="absolute -top-1 -right-1 size-2 rounded-pill bg-accent" />
        </span>
        <div>
          <p className="text-large text-text">Trip Planner</p>
          <p className="text-caption text-text-muted">Jaipur · Chennai · Goa</p>
        </div>
      </div>
    </header>
  );
}

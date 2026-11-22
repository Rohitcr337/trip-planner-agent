import { Info } from "lucide-react";

export default function PreviewChip() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-pill border border-border-strong bg-surface-muted px-3 py-1 text-caption text-text">
      <Info aria-hidden="true" className="size-3.5 shrink-0 text-primary" />
      Preview · sample data
    </span>
  );
}

import { TriangleAlert } from "lucide-react";

export default function UnverifiedBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-tag bg-warning-soft px-2 py-1 text-caption text-warning">
      <TriangleAlert aria-hidden="true" className="size-4" />
      Unverified
    </span>
  );
}

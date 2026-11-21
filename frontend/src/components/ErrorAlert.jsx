import { CircleAlert, RotateCcw } from "lucide-react";

export default function ErrorAlert({ title = "Something went wrong", message, onRetry, retryLabel = "Try again" }) {
  return (
    <div
      role="alert"
      className="flex animate-enter gap-3 rounded-card border border-danger bg-danger-soft p-4 text-danger motion-reduce:animate-fade"
    >
      <CircleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{title}</p>
        {message && <p className="mt-1 text-small">{message}</p>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex min-h-11 items-center gap-2 rounded-control border border-danger bg-surface px-4 text-small font-semibold text-danger transition-colors duration-(--duration-press) ease-standard hover:bg-danger-soft active:bg-danger-soft"
          >
            <RotateCcw aria-hidden="true" className="size-4" />
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}

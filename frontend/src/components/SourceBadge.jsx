import { CircleAlert, ExternalLink } from "lucide-react";

function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

export default function SourceBadge({ source }) {
  const href = safeUrl(source.source_url);
  const label = `${source.source_name}: ${source.section}`;
  const classes = "inline-flex min-h-11 max-w-full items-center gap-2 rounded-pill border border-border-strong bg-surface px-3 py-2 text-small";

  if (!href) {
    return (
      <span className={`${classes} text-text-muted`}>
        <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
        <span className="break-words">{label} — link unavailable</span>
      </span>
    );
  }

  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={`${classes} text-primary transition-colors duration-(--duration-press) ease-standard hover:bg-primary-soft hover:underline hover:underline-offset-2`}>
      <span className="min-w-0 break-words">{label}</span>
      <ExternalLink aria-hidden="true" className="size-4 shrink-0" />
      <span className="sr-only">(opens in a new tab)</span>
    </a>
  );
}

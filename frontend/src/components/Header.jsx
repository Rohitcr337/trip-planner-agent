export function CairnMark({ className = "size-8" }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 32 32" className={`text-primary ${className}`} fill="currentColor">
      <rect x="4" y="21" width="24" height="8" rx="4" />
      <rect x="7.5" y="12.5" width="17" height="7" rx="3.5" />
      <rect x="11" y="4.5" width="10" height="6.5" rx="3.25" />
    </svg>
  );
}

export default function Header() {
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-content items-center px-4 py-3 sm:px-6">
        <a href="/" className="inline-flex min-h-11 items-center gap-2.5 rounded-control pr-2 text-text">
          <CairnMark />
          <span className="text-large font-semibold tracking-tight">Cairn</span>
        </a>
      </div>
    </header>
  );
}

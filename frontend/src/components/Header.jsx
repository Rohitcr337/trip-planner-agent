import { useEffect, useRef, useState } from "react";
import { useAuth } from "./AuthProvider.jsx";

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
  const { user, openSignIn, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const accountRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return undefined;
    const items = [...(menuRef.current?.querySelectorAll('[role="menuitem"]') || [])];
    items[0]?.focus();
    function onKey(event) {
      if (event.key === "Escape") {
        setMenuOpen(false);
        accountRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-content items-center px-4 py-3 sm:px-6">
        <a href="/" className="inline-flex min-h-11 items-center gap-2.5 rounded-control pr-2 text-text">
          <CairnMark />
          <span className="text-large font-semibold tracking-tight">Cairn</span>
        </a>
        <div className="relative ml-auto">
          {user ? (
            <>
              <button
                ref={accountRef}
                type="button"
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
                className="inline-flex min-h-11 max-w-64 items-center truncate rounded-control border border-border-strong bg-surface px-3 text-small font-semibold text-text hover:bg-surface-muted"
              >
                {user.email}
              </button>
              {menuOpen && (
                <div
                  ref={menuRef}
                  role="menu"
                  aria-label="Account"
                  onKeyDown={(event) => {
                    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
                    event.preventDefault();
                    const items = [...(menuRef.current?.querySelectorAll('[role="menuitem"]') || [])];
                    const current = items.indexOf(document.activeElement);
                    const direction = event.key === "ArrowDown" ? 1 : -1;
                    items[(current + direction + items.length) % items.length]?.focus();
                  }}
                  className="absolute right-0 z-20 mt-2 min-w-44 rounded-card border border-border bg-surface p-2 shadow-2"
                >
                  <a role="menuitem" href="#/trips" onClick={() => setMenuOpen(false)} className="flex min-h-11 items-center rounded-control px-3 text-small font-semibold text-text hover:bg-surface-muted">
                    My trips
                  </a>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setMenuOpen(false);
                      signOut();
                    }}
                    className="flex min-h-11 w-full items-center rounded-control px-3 text-left text-small font-semibold text-text hover:bg-surface-muted"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </>
          ) : (
            <button
              type="button"
              onClick={() => openSignIn()}
              className="inline-flex min-h-11 items-center rounded-control bg-primary px-4 text-small font-semibold text-on-primary hover:bg-primary-hover"
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

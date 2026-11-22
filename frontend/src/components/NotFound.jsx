import { useEffect } from "react";
import { CairnMark } from "./Header.jsx";

export default function NotFound() {
  useEffect(() => {
    const previous = document.title;
    document.title = "Page not found · Cairn";
    return () => {
      document.title = previous;
    };
  }, []);

  return (
    <section aria-labelledby="not-found-heading" className="mx-auto flex max-w-prose flex-col items-start py-16 lg:py-24">
      <CairnMark className="size-12" />
      <h1 id="not-found-heading" className="mt-6 text-display-phone sm:text-display">Page not found</h1>
      <p className="mt-3 text-large text-text-muted">This page doesn't exist or has moved.</p>
      <a
        href="/"
        className="mt-8 inline-flex min-h-11 items-center justify-center rounded-control bg-primary px-5 text-body font-semibold text-on-primary shadow-1 transition-colors duration-(--duration-press) ease-standard hover:bg-primary-hover"
      >
        Plan a trip
      </a>
    </section>
  );
}

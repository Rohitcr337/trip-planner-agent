import Header from "./components/Header.jsx";

export default function App() {
  return (
    <div className="min-h-screen bg-bg text-text">
      <Header />
      <main className="mx-auto max-w-content px-4 pb-16 sm:px-6">
        <section className="max-w-prose py-8 lg:py-12">
          <h1 className="text-display-phone text-text sm:text-display">
            Plan a calm, well-sourced trip
          </h1>
          <p className="mt-3 text-large text-text-muted">
            Day-by-day plans for Jaipur, Chennai and Goa, built from travel guides and checked
            against your budget.
          </p>
        </section>

        <div className="grid gap-8 lg:grid-cols-[var(--container-form)_minmax(0,1fr)] lg:gap-12">
          <section
            aria-labelledby="form-heading"
            className="rounded-card bg-surface p-4 shadow-1 sm:p-6 lg:sticky lg:top-6 lg:self-start"
          >
            <h2 id="form-heading" className="text-h3 text-text">
              Plan your trip
            </h2>
          </section>

          <section aria-labelledby="results-heading" className="min-w-0">
            <h2 id="results-heading" className="text-h2-phone text-text sm:text-h2">
              Your itinerary
            </h2>
          </section>
        </div>
      </main>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { streamPlan } from "./api.js";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import NotFound from "./components/NotFound.jsx";
import TripForm from "./components/TripForm.jsx";
import PreviewChip from "./components/PreviewChip.jsx";
import ErrorAlert from "./components/ErrorAlert.jsx";
import ProgressSteps from "./components/ProgressSteps.jsx";
import ItineraryTimeline from "./components/ItineraryTimeline.jsx";
import CostSummary from "./components/CostSummary.jsx";

const HOME_PATHS = new Set(["/", "/index.html"]);

function Planner() {
  const [plan, setPlan] = useState({ status: "idle", request: null, steps: [], result: null, message: "" });
  const controllerRef = useRef(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const startPlan = async (request) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setPlan({ status: "planning", request, steps: [], result: null, message: "" });
    await streamPlan(request, ({ type, data }) => {
      if (controller.signal.aborted) return;
      if (type === "step") {
        setPlan((current) => ({ ...current, steps: [...current.steps, data] }));
      } else if (type === "result") {
        setPlan((current) => ({ ...current, status: "complete", result: data }));
      } else if (type === "error") {
        setPlan((current) => ({ ...current, status: "error", message: data.message }));
      }
    }, { signal: controller.signal });
  };

  return (
    <>
      <section className="max-w-prose py-8 lg:py-12">
        <h1 className="text-display-phone text-text sm:text-display">
          Trip plans, traced to their sources.
        </h1>
        <p className="mt-3 text-large text-text-muted">
          Itineraries built from travel guides, checked against your budget and travel times.
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
          <TripForm onSubmit={startPlan} planning={plan.status === "planning"} />
        </section>

        <section aria-labelledby="results-heading" className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h2 id="results-heading" className="text-h2-phone text-text sm:text-h2">
              Your itinerary
            </h2>
            {plan.result?.demo === true && <PreviewChip />}
          </div>
          <div className="mt-6 space-y-8 lg:space-y-12">
            {plan.status !== "idle" && (
              <ProgressSteps steps={plan.steps} status={plan.status} message={plan.message} />
            )}
            {plan.status === "error" ? (
              <ErrorAlert title="Your plan could not be completed" message={plan.message} onRetry={() => startPlan(plan.request)} />
            ) : (
              <>
                <CostSummary estimate={plan.result?.draft?.total_est_cost_inr ?? null} budget={plan.request?.budget ?? null} loading={plan.status === "planning"} />
                <ItineraryTimeline draft={plan.result?.draft ?? null} costsAreEstimates={plan.result?.costs_are_estimates === true} unresolved={plan.result?.unresolved ?? []} status={plan.status} />
              </>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-bg text-text">
      <Header />
      <main className="mx-auto w-full max-w-content flex-1 px-4 pb-16 sm:px-6">
        {HOME_PATHS.has(window.location.pathname) ? <Planner /> : <NotFound />}
      </main>
      <Footer />
    </div>
  );
}

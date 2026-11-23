import { useCallback, useEffect, useRef, useState } from "react";
import { streamPlan } from "./api.js";
import AuthProvider from "./components/AuthProvider.jsx";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import NotFound from "./components/NotFound.jsx";
import TripForm from "./components/TripForm.jsx";
import PreviewChip from "./components/PreviewChip.jsx";
import ErrorAlert from "./components/ErrorAlert.jsx";
import ProgressSteps from "./components/ProgressSteps.jsx";
import ItineraryTimeline from "./components/ItineraryTimeline.jsx";
import CostSummary from "./components/CostSummary.jsx";
import MapView from "./components/MapView.jsx";
import ChecksPanel from "./components/ChecksPanel.jsx";
import SavePlanActions from "./components/SavePlanActions.jsx";

const HOME_PATHS = new Set(["/", "/index.html"]);

function Planner() {
  const [plan, setPlan] = useState({ status: "idle", request: null, steps: [], result: null, message: "" });
  const [formRequest, setFormRequest] = useState(null);
  const [avoid, setAvoid] = useState([]);
  const [swapCount, setSwapCount] = useState(0);
  const controllerRef = useRef(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const requestKey = (request) => JSON.stringify({
    destination: request?.destination,
    days: request?.days,
    budget: request?.budget,
    interests: request?.interests,
    style: request?.style,
    start_date: request?.start_date,
  });

  const startPlan = async (request, nextAvoid = avoid) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const planningRequest = { ...request, avoid: nextAvoid };
    setPlan((current) => ({ ...current, status: "planning", request: planningRequest, steps: [], message: "" }));
    await streamPlan(planningRequest, ({ type, data }) => {
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

  const handleFormRequestChange = useCallback((request) => setFormRequest(request), []);
  const hasFormChanges = Boolean(plan.result && (!formRequest || requestKey(formRequest) !== requestKey(plan.request)));

  const replanWithAvoid = (nextAvoid) => {
    if (!plan.request || swapCount >= 10 && nextAvoid.length > avoid.length) return;
    setAvoid(nextAvoid);
    setSwapCount((count) => nextAvoid.length > avoid.length ? count + 1 : count);
    startPlan({ ...plan.request, avoid: undefined }, nextAvoid);
  };

  const swapStop = (name) => {
    if (avoid.some((item) => item.toLowerCase() === name.toLowerCase()) || swapCount >= 10) return;
    replanWithAvoid([...avoid, name]);
  };

  const removeAvoid = (name) => replanWithAvoid(avoid.filter((item) => item !== name));
  const clearAvoid = () => replanWithAvoid([]);
  const updatePlan = () => {
    if (!formRequest) return;
    startPlan(formRequest, avoid);
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
          <TripForm onSubmit={(request) => startPlan(request, avoid)} onRequestChange={handleFormRequestChange} planning={plan.status === "planning"} />
        </section>

        <section aria-labelledby="results-heading" className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <h2 id="results-heading" className="text-h2-phone text-text sm:text-h2">
              {plan.request ? `Your ${plan.request.destination} itinerary` : "Your itinerary"}
            </h2>
            {plan.result?.demo === true && <PreviewChip />}
          </div>
          <div className="mt-6 space-y-8 lg:space-y-12">
            {avoid.length > 0 && (
              <section aria-label="Places to avoid" className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-small font-semibold text-text">Avoiding:</span>
                  {avoid.map((name) => (
                    <button
                      type="button"
                      key={name}
                      onClick={() => removeAvoid(name)}
                      className="inline-flex min-h-11 items-center gap-2 rounded-pill bg-primary-soft px-3 text-small text-text hover:bg-surface-muted"
                      aria-label={`Stop avoiding ${name}`}
                    >
                      {name} <span aria-hidden="true">x</span>
                    </button>
                  ))}
                  <button type="button" onClick={clearAvoid} className="min-h-11 rounded-control px-3 text-small font-semibold text-primary underline underline-offset-2">
                    Clear all
                  </button>
                </div>
                <p className="text-small text-text-muted">Re-planning builds a new plan that avoids these places.</p>
              </section>
            )}
            {hasFormChanges && (
              <button type="button" onClick={updatePlan} className="min-h-11 rounded-control bg-primary px-4 text-small font-semibold text-on-primary hover:bg-primary-hover">
                Update plan
              </button>
            )}
            {plan.status !== "idle" && (
              <ProgressSteps steps={plan.steps} status={plan.status} message={plan.message} />
            )}
            {plan.status === "error" && (
              <ErrorAlert title="Your plan could not be completed" message={plan.message} onRetry={() => startPlan(plan.request, avoid)} />
            )}
            <div aria-busy={plan.status === "planning"} className={plan.status === "planning" && plan.result ? "opacity-60 transition-opacity" : ""}>
              <CostSummary breakdown={plan.result?.cost_breakdown ?? null} loading={plan.status === "planning"} />
              {plan.result && (
                <>
                  {plan.status === "complete" && <SavePlanActions request={plan.request} result={plan.result} formChanged={hasFormChanges} />}
                  <MapView key={plan.result.draft?.city} draft={plan.result.draft} cityCenter={plan.result.city_center} />
                  <ChecksPanel checks={plan.result.checks} revisions={plan.result.revisions} />
                </>
              )}
              <ItineraryTimeline draft={plan.result?.draft ?? null} costsAreEstimates={plan.result?.costs_are_estimates === true} unresolved={plan.result?.unresolved ?? []} status={plan.status} onSwap={plan.result ? swapStop : undefined} />
            </div>
          </div>
        </section>
      </div>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <div className="flex min-h-screen flex-col bg-bg text-text">
        <Header />
        <main className="mx-auto w-full max-w-content flex-1 px-4 pb-16 sm:px-6">
          {HOME_PATHS.has(window.location.pathname) ? <Planner /> : <NotFound />}
        </main>
        <Footer />
      </div>
    </AuthProvider>
  );
}

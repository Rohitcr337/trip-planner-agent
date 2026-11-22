import { useCallback, useEffect, useRef, useState } from "react";
import { Check, CircleAlert } from "lucide-react";
import { fetchOptions } from "../api.js";
import ErrorAlert from "./ErrorAlert.jsx";
import Spinner from "./Spinner.jsx";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const FIELD_ORDER = ["destination", "days", "budget", "interests", "style", "startDate"];
const FIELD_LABELS = {
  destination: "City",
  days: "Days",
  budget: "Budget",
  interests: "Interests",
  style: "Pace",
  startDate: "Start date",
};

const inputBase =
  "block min-h-11 w-full rounded-control border bg-surface px-3 text-body text-text transition-colors duration-(--duration-press) ease-standard hover:border-text focus:border-primary disabled:cursor-not-allowed disabled:border-border disabled:bg-surface-muted disabled:text-text-muted";

function capitalise(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function uniqueInterests(values) {
  const seen = new Set();
  return values.filter((value) => {
    const key = value.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function parseOtherInterests(text) {
  return String(text || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

function isRealDate(text) {
  if (!ISO_DATE.test(text)) return false;
  const parsed = new Date(`${text}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === text;
}

export function validateTrip(values, options) {
  const errors = {};
  const { min, max } = options.day_range;

  if (!options.cities.includes(values.destination)) errors.destination = "Choose a city.";

  const daysText = String(values.days ?? "").trim();
  const days = Number(daysText);
  if (!daysText || !Number.isInteger(days) || days < min || days > max) {
    errors.days = `Enter a whole number of days from ${min} to ${max}.`;
  }

  const budgetText = String(values.budget ?? "").trim();
  const budget = Number(budgetText);
  if (!budgetText || !Number.isFinite(budget) || budget <= 0) {
    errors.budget = "Enter a budget in INR that is more than 0.";
  }

  const interests = uniqueInterests([...values.interests, ...parseOtherInterests(values.otherInterests)]);
  if (!interests.length) errors.interests = "Choose at least one interest or type your own.";

  if (!options.styles.includes(values.style)) errors.style = "Choose a pace.";

  const dateText = String(values.startDate ?? "").trim();
  if (dateText && !isRealDate(dateText)) errors.startDate = "Enter a real date, or leave it empty.";

  if (Object.keys(errors).length) return { errors, request: null };
  return {
    errors,
    request: {
      destination: values.destination,
      days,
      budget,
      interests,
      style: values.style,
      start_date: dateText || null,
    },
  };
}

function initialValues(options) {
  const { min, max } = options.day_range;
  return {
    destination: "",
    days: String(Math.min(Math.max(3, min), max)),
    budget: "",
    interests: [],
    otherInterests: "",
    style: options.styles.includes("relaxed") ? "relaxed" : options.styles[0] ?? "",
    startDate: "",
  };
}

function FieldMessage({ id, error, hint }) {
  return (
    <>
      {hint && (
        <p id={`${id}-hint`} className="mt-1 text-small text-text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 flex items-start gap-1.5 text-small text-danger">
          <CircleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </p>
      )}
    </>
  );
}

function describedBy(id, { hint, error }) {
  return [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
}

function OptionsSkeleton() {
  return (
    <div role="status" className="mt-6 space-y-6">
      <span className="sr-only">Loading trip options</span>
      {[0, 1, 2, 3].map((row) => (
        <div key={row} aria-hidden="true" className="space-y-2">
          <div className="h-4 w-24 animate-pulse rounded-tag bg-surface-muted motion-reduce:animate-none" />
          <div className="h-11 w-full animate-pulse rounded-control bg-surface-muted motion-reduce:animate-none" />
        </div>
      ))}
      <Spinner />
    </div>
  );
}

export default function TripForm({ onSubmit, planning = false }) {
  const [load, setLoad] = useState({ status: "loading", options: null, message: "" });
  const [values, setValues] = useState(null);
  const [showErrors, setShowErrors] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const summaryRef = useRef(null);
  const loadController = useRef(null);

  const loadOptions = useCallback(async () => {
    loadController.current?.abort();
    const controller = new AbortController();
    loadController.current = controller;
    setLoad({ status: "loading", options: null, message: "" });
    const outcome = await fetchOptions({ signal: controller.signal });
    if (controller.signal.aborted || outcome.aborted) return;
    if (outcome.ok) {
      setValues((current) => current ?? initialValues(outcome.options));
      setLoad({ status: "ready", options: outcome.options, message: "" });
    } else {
      setLoad({ status: "error", options: null, message: outcome.message });
    }
  }, []);

  useEffect(() => {
    loadOptions();
    return () => loadController.current?.abort();
  }, [loadOptions]);

  useEffect(() => {
    if (attempt > 0) summaryRef.current?.focus();
  }, [attempt]);

  if (load.status === "loading") return <OptionsSkeleton />;
  if (load.status === "error") {
    return (
      <div className="mt-6">
        <ErrorAlert title="Trip options are unavailable" message={load.message} onRetry={loadOptions} />
      </div>
    );
  }

  const { options } = load;
  const { errors } = validateTrip(values, options);
  const visibleErrors = showErrors ? errors : {};
  const errorList = FIELD_ORDER.filter((field) => visibleErrors[field]);
  const interestTargetId = options.interest_suggestions.length ? "trip-interest-0" : "trip-interests-other";
  const focusTargets = {
    destination: "trip-destination",
    days: "trip-days",
    budget: "trip-budget",
    interests: interestTargetId,
    style: "trip-style-0",
    startDate: "trip-start-date",
  };

  const update = (field, value) => setValues((current) => ({ ...current, [field]: value }));
  const toggleInterest = (interest) =>
    setValues((current) => ({
      ...current,
      interests: current.interests.includes(interest)
        ? current.interests.filter((item) => item !== interest)
        : [...current.interests, interest],
    }));

  const handleSubmit = (event) => {
    event.preventDefault();
    if (planning) return;
    const outcome = validateTrip(values, options);
    if (outcome.request) {
      setShowErrors(false);
      onSubmit?.(outcome.request);
      return;
    }
    setShowErrors(true);
    setAttempt((count) => count + 1);
  };

  const daysHint = `From ${options.day_range.min} to ${options.day_range.max} days.`;
  const budgetHint = "Total per person, in INR, for the whole trip.";
  const otherHint = "Optional. Separate with commas, for example: street art, cycling.";
  const dateHint = "Optional. Weather is added when the trip starts within the next 16 days.";

  return (
    <form noValidate onSubmit={handleSubmit} className="mt-6" aria-describedby={errorList.length ? "trip-errors-title" : undefined}>
      {errorList.length > 0 && (
        <div
          ref={summaryRef}
          tabIndex={-1}
          role="alert"
          aria-labelledby="trip-errors-title"
          className="mb-6 rounded-control border border-danger bg-danger-soft p-4 text-danger"
        >
          <p id="trip-errors-title" className="flex items-center gap-2 font-semibold">
            <CircleAlert aria-hidden="true" className="size-5 shrink-0" />
            {errorList.length === 1
              ? "There is 1 problem with your trip details"
              : `There are ${errorList.length} problems with your trip details`}
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-7 text-small">
            {errorList.map((field) => (
              <li key={field}>
                <a
                  href={`#${focusTargets[field]}`}
                  onClick={(event) => {
                    event.preventDefault();
                    document.getElementById(focusTargets[field])?.focus();
                  }}
                  className="inline-flex min-h-11 items-center underline underline-offset-2 hover:no-underline"
                >
                  {FIELD_LABELS[field]}: {visibleErrors[field]}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <fieldset disabled={planning} className="min-w-0 space-y-6">
        <div>
          <label htmlFor="trip-destination" className="text-small font-semibold text-text">
            City
          </label>
          <select
            id="trip-destination"
            value={values.destination}
            onChange={(event) => update("destination", event.target.value)}
            aria-invalid={Boolean(visibleErrors.destination)}
            aria-describedby={describedBy("trip-destination", { error: visibleErrors.destination })}
            className={`${inputBase} mt-2 ${visibleErrors.destination ? "border-danger hover:border-danger" : "border-border-strong"}`}
          >
            <option value="">Choose a city</option>
            {options.cities.map((city) => (
              <option key={city} value={city}>
                {city}
              </option>
            ))}
          </select>
          <FieldMessage id="trip-destination" error={visibleErrors.destination} />
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
          <div>
            <label htmlFor="trip-days" className="text-small font-semibold text-text">
              Days
            </label>
            <input
              id="trip-days"
              type="number"
              inputMode="numeric"
              min={options.day_range.min}
              max={options.day_range.max}
              step="1"
              value={values.days}
              onChange={(event) => update("days", event.target.value)}
              aria-invalid={Boolean(visibleErrors.days)}
              aria-describedby={describedBy("trip-days", { hint: daysHint, error: visibleErrors.days })}
              className={`${inputBase} mt-2 ${visibleErrors.days ? "border-danger hover:border-danger" : "border-border-strong"}`}
            />
            <FieldMessage id="trip-days" hint={daysHint} error={visibleErrors.days} />
          </div>

          <div>
            <label htmlFor="trip-budget" className="text-small font-semibold text-text">
              Budget (INR)
            </label>
            <input
              id="trip-budget"
              type="number"
              inputMode="decimal"
              min="0"
              step="any"
              value={values.budget}
              onChange={(event) => update("budget", event.target.value)}
              aria-invalid={Boolean(visibleErrors.budget)}
              aria-describedby={describedBy("trip-budget", { hint: budgetHint, error: visibleErrors.budget })}
              className={`${inputBase} mt-2 ${visibleErrors.budget ? "border-danger hover:border-danger" : "border-border-strong"}`}
            />
            <FieldMessage id="trip-budget" hint={budgetHint} error={visibleErrors.budget} />
          </div>
        </div>

        <fieldset
          className="min-w-0"
          aria-describedby={describedBy("trip-interests", { error: visibleErrors.interests })}
        >
          <legend className="text-small font-semibold text-text">Interests</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {options.interest_suggestions.map((interest, index) => {
              const selected = values.interests.includes(interest);
              return (
                <button
                  key={interest}
                  id={`trip-interest-${index}`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggleInterest(interest)}
                  className={`inline-flex min-h-11 items-center gap-1.5 rounded-pill border px-4 text-small transition-colors duration-(--duration-press) ease-standard disabled:cursor-not-allowed disabled:border-border disabled:bg-surface-muted disabled:text-text-muted ${
                    selected
                      ? "border-primary bg-primary-soft font-semibold text-text hover:border-primary-hover"
                      : "border-border-strong bg-surface text-text hover:bg-surface-muted"
                  }`}
                >
                  {selected && <Check aria-hidden="true" className="size-4 text-primary" />}
                  {capitalise(interest)}
                </button>
              );
            })}
          </div>
          <label htmlFor="trip-interests-other" className="mt-4 block text-small font-semibold text-text">
            Other interests
          </label>
          <input
            id="trip-interests-other"
            type="text"
            value={values.otherInterests}
            onChange={(event) => update("otherInterests", event.target.value)}
            aria-invalid={Boolean(visibleErrors.interests)}
            aria-describedby={describedBy("trip-interests-other", { hint: otherHint })}
            className={`${inputBase} mt-2 ${visibleErrors.interests ? "border-danger hover:border-danger" : "border-border-strong"}`}
          />
          <FieldMessage id="trip-interests-other" hint={otherHint} />
          <FieldMessage id="trip-interests" error={visibleErrors.interests} />
        </fieldset>

        <fieldset
          className="min-w-0"
          aria-describedby={describedBy("trip-style", { error: visibleErrors.style })}
        >
          <legend className="text-small font-semibold text-text">Pace</legend>
          <div className="mt-2 grid grid-cols-2 gap-1 rounded-control border border-border-strong bg-surface p-1">
            {options.styles.map((style, index) => (
              <label
                key={style}
                className="flex min-h-11 cursor-pointer items-center justify-center gap-1.5 rounded-tag px-3 text-small font-semibold text-text transition-colors duration-(--duration-press) ease-standard hover:bg-surface-muted has-checked:bg-primary has-checked:text-on-primary has-checked:hover:bg-primary-hover has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary has-disabled:cursor-not-allowed has-disabled:text-text-muted has-disabled:has-checked:bg-surface-muted"
              >
                <input
                  id={`trip-style-${index}`}
                  type="radio"
                  name="trip-style"
                  value={style}
                  checked={values.style === style}
                  onChange={() => update("style", style)}
                  className="sr-only"
                />
                {values.style === style && <Check aria-hidden="true" className="size-4" />}
                {capitalise(style)}
              </label>
            ))}
          </div>
          <FieldMessage id="trip-style" error={visibleErrors.style} />
        </fieldset>

        <div>
          <label htmlFor="trip-start-date" className="text-small font-semibold text-text">
            Start date
          </label>
          <input
            id="trip-start-date"
            type="date"
            value={values.startDate}
            onChange={(event) => update("startDate", event.target.value)}
            aria-invalid={Boolean(visibleErrors.startDate)}
            aria-describedby={describedBy("trip-start-date", { hint: dateHint, error: visibleErrors.startDate })}
            className={`${inputBase} mt-2 ${visibleErrors.startDate ? "border-danger hover:border-danger" : "border-border-strong"}`}
          />
          <FieldMessage id="trip-start-date" hint={dateHint} error={visibleErrors.startDate} />
        </div>

        <button
          type="submit"
          disabled={planning}
          className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-control bg-primary px-5 text-body font-semibold text-on-primary shadow-1 transition-[background-color,translate] duration-(--duration-press) ease-standard hover:bg-primary-hover active:translate-y-px active:bg-primary-hover disabled:cursor-wait disabled:hover:bg-primary disabled:active:translate-y-0 motion-reduce:active:translate-y-0"
        >
          {planning ? (
            <>
              <Spinner />
              Planning...
            </>
          ) : (
            "Plan my trip"
          )}
        </button>
      </fieldset>
    </form>
  );
}

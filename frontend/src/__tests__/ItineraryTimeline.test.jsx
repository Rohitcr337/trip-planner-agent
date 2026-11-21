import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ItineraryTimeline from "../components/ItineraryTimeline.jsx";
import SourceBadge from "../components/SourceBadge.jsx";

const source = { source_name: "Wikivoyage", source_url: "https://en.wikivoyage.org/wiki/Jaipur", section: "See > Forts" };
const stop = { name: "Amber Fort", area: "Amer", time_slot: "morning", duration_minutes: 90, est_cost_inr: 500, notes: "Check opening times.", sources: [source], unverified: false };
const draft = { city: "Jaipur", days: [{ day: 1, date: "2026-12-01", stops: [stop, { ...stop, name: "Guide passage", est_cost_inr: 100, sources: [], unverified: true }], weather_note: "Weather is unavailable." }], total_est_cost_inr: 600, assumptions: ["Stop costs are estimates."] };

describe("ItineraryTimeline", () => {
  it("renders days, stop details, totals, weather and assumptions", () => {
    render(<ItineraryTimeline draft={draft} status="complete" />);
    expect(screen.getByRole("heading", { name: "Day 1", level: 3 })).toBeTruthy();
    expect(screen.getByText("1 Dec 2026")).toBeTruthy();
    const card = screen.getByRole("article", { name: "Amber Fort" });
    for (const text of ["Morning", "Amer", "90 min", "Rs 500 est.", "Check opening times."]) {
      expect(within(card).getByText(text)).toBeTruthy();
    }
    expect(screen.getByText("Rs 600", { exact: false })).toBeTruthy();
    expect(screen.getByText("Weather is unavailable.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Planning assumptions" })).toBeTruthy();
  });

  it("shows the unverified badge only on the unverified stop", () => {
    render(<ItineraryTimeline draft={draft} status="complete" />);
    expect(within(screen.getByRole("article", { name: "Guide passage" })).getByText("Unverified")).toBeTruthy();
    expect(within(screen.getByRole("article", { name: "Amber Fort" })).queryByText("Unverified")).toBeNull();
  });

  it("shows the estimates notice when the backend flag is true", () => {
    render(<ItineraryTimeline draft={draft} costsAreEstimates status="complete" />);
    expect(screen.getByText("Costs are estimates.")).toBeTruthy();
  });

  it("links out to each source with descriptive text and safe new-tab attributes", () => {
    render(<ItineraryTimeline draft={draft} status="complete" />);
    const link = screen.getByRole("link", { name: /Wikivoyage: See > Forts/ });
    expect(link.getAttribute("href")).toBe(source.source_url);
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("shows unresolved issues even when there is no draft", () => {
    render(<ItineraryTimeline status="complete" unresolved={["Budget is too low."]} />);
    expect(screen.getByText("No itinerary was drafted")).toBeTruthy();
    expect(screen.getByText("Budget is too low.")).toBeTruthy();
  });

  it("has idle, loading and empty-day states", () => {
    const { rerender } = render(<ItineraryTimeline />);
    expect(screen.getByText("Your next trip starts here")).toBeTruthy();
    rerender(<ItineraryTimeline status="planning" />);
    expect(screen.getByLabelText("Loading itinerary").getAttribute("aria-busy")).toBe("true");
    rerender(<ItineraryTimeline draft={{ ...draft, days: [{ ...draft.days[0], stops: [] }] }} status="complete" />);
    expect(screen.getByText("No stops were included for this day.")).toBeTruthy();
  });
});

it("does not turn unsafe source URLs into links", () => {
  render(<SourceBadge source={{ ...source, source_url: "javascript:alert(1)" }} />);
  expect(screen.queryByRole("link")).toBeNull();
  expect(screen.getByText(/link unavailable/)).toBeTruthy();
});

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import { deleteTrip, fetchMe, fetchOptions, fetchTrip, listTrips } from "../api.js";
import { clearSession, endSession, setSession } from "../auth.js";

vi.mock("../api.js", () => ({
  approveTrip: vi.fn(), createTrip: vi.fn(), deleteTrip: vi.fn(), fetchMe: vi.fn(), fetchOptions: vi.fn(), fetchTrip: vi.fn(),
  listTrips: vi.fn(), loginAccount: vi.fn(), logoutAccount: vi.fn(), registerAccount: vi.fn(), streamPlan: vi.fn(),
}));
vi.mock("../components/MapView.jsx", () => ({ default: () => <section aria-label="Saved map">Saved map</section> }));

const draft = { city: "Jaipur", days: [{ day: 1, date: "2026-11-20", weather: { date: "2026-11-20", temp_max_c: 28, temp_min_c: 20, precip_mm: 14, rainy: true }, weather_note: "Rain likely (14 mm); indoor options preferred", stops: [{ name: "Amber Fort", area: "Amer", time_slot: "morning", duration_minutes: 60, est_cost_inr: 500, notes: "Visit the fort.", passage_ids: [], sources: [], unverified: true }] }], total_est_cost_inr: 500, assumptions: [] };
const trip = { id: 21, title: "Jaipur · 2 days", request: { destination: "Jaipur", days: 2, budget: 10000 }, draft, checks: [{ name: "budget", passed: true, reason: "Within budget." }], cost_breakdown: { complete: true, stops_inr: 500, transport_meals_inr: 1000, stay_inr: 500, estimate_inr: 2000, budget_inr: 10000 }, created_at: "2026-11-20T12:00:00Z", approved_at: "2026-11-20T12:00:00Z", status: "approved" };
const options = { destinations: [{ name: "Jaipur", lat: 26.9, lon: 75.8 }] };

function signedIn() {
  setSession("saved-trips-token");
  fetchMe.mockResolvedValue({ ok: true, data: { id: 1, email: "person@example.com" } });
}

async function openTrips(path = "#/trips") {
  window.location.hash = path;
  render(<App />);
  await screen.findByRole("button", { name: "person@example.com" });
}

beforeEach(() => {
  clearSession();
  window.location.hash = "";
  vi.clearAllMocks();
  fetchMe.mockResolvedValue({ ok: false });
  fetchOptions.mockResolvedValue({ ok: true, options });
  listTrips.mockResolvedValue({ ok: true, data: { trips: [trip] } });
  fetchTrip.mockResolvedValue({ ok: true, data: trip });
  deleteTrip.mockResolvedValue({ ok: true, status: 204 });
});
afterEach(() => { cleanup(); clearSession(); window.location.hash = ""; });

describe("saved trips", () => {
  it("lists saved trips with estimate, budget, days and approval date", async () => {
    signedIn();
    await openTrips();
    expect(await screen.findByRole("heading", { name: trip.title })).toBeTruthy();
    expect(screen.getByText(/Rs 2,000 against Rs 10,000/)).toBeTruthy();
    expect(screen.getByText(/2 days/)).toBeTruthy();
    expect(listTrips).toHaveBeenCalled();
  });

  it("opens a saved itinerary in read-only mode", async () => {
    signedIn();
    await openTrips("#/trips/21");
    expect(await screen.findByRole("heading", { name: trip.title })).toBeTruthy();
    expect(await screen.findByRole("heading", { name: "Day 1" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Saved map" })).toBeTruthy();
    expect(screen.getByText("Trip cost estimate")).toBeTruthy();
    expect(screen.getByText("Plan checks")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Weather for day 1" })).toBeTruthy();
    expect(screen.getByText("Rain likely (14 mm); indoor options preferred")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Swap/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Update plan" })).toBeNull();
    expect(fetchTrip).toHaveBeenCalledWith("21");
  });

  it("requires confirmation before deleting a saved trip", async () => {
    signedIn();
    await openTrips();
    await screen.findByRole("heading", { name: trip.title });
    fireEvent.click(screen.getByRole("button", { name: "Delete", exact: true }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(deleteTrip).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Delete trip" }));
    expect(await screen.findByText("No saved trips yet")).toBeTruthy();
    expect(deleteTrip).toHaveBeenCalledWith(21);
  });

  it("shows the empty state", async () => {
    signedIn();
    listTrips.mockResolvedValueOnce({ ok: true, data: { trips: [] } });
    await openTrips();
    expect(await screen.findByText("No saved trips yet")).toBeTruthy();
  });

  it("shows loading and retryable errors", async () => {
    signedIn();
    let resolve;
    listTrips.mockReturnValueOnce(new Promise((done) => { resolve = done; }));
    await openTrips();
    expect(await screen.findByText("Loading saved trips…")).toBeTruthy();
    resolve({ ok: false, message: "Trips are unavailable." });
    expect(await screen.findByRole("alert")).toBeTruthy();
    listTrips.mockResolvedValueOnce({ ok: true, data: { trips: [] } });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No saved trips yet")).toBeTruthy();
  });

  it("returns to sign in after a session-ending 401", async () => {
    signedIn();
    listTrips.mockImplementationOnce(async () => {
      endSession();
      return { ok: false, status: 401, message: "Your session ended. Please sign in again." };
    });
    await openTrips();
    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(screen.getByText("Your session ended. Please sign in again.")).toBeTruthy();
  });

  it("keeps unknown hash routes on the not-found page", async () => {
    window.location.hash = "#/missing";
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Page not found" })).toBeTruthy();
  });
});

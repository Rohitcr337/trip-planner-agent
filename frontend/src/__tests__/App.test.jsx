import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import { fetchOptions, streamPlan } from "../api.js";

vi.mock("../api.js", () => ({ fetchOptions: vi.fn(), streamPlan: vi.fn() }));
const options = { cities: ["Jaipur", "Chennai", "Goa"], destinations: [{ name: "Jaipur", lat: 26.9, lon: 75.8 }, { name: "Chennai", lat: 13.1, lon: 80.3 }, { name: "Goa", lat: 15.5, lon: 73.8 }], styles: ["relaxed", "packed"], day_range: { min: 1, max: 7 }, interest_suggestions: ["history", "food"] };
const draft = { city: "Jaipur", days: [{ day: 1, date: null, weather_note: null, stops: [{ name: "Amber Fort", area: "Amer", time_slot: "morning", duration_minutes: 90, est_cost_inr: 500, notes: "Verify details.", sources: [], unverified: true }] }], total_est_cost_inr: 500, assumptions: [] };
const result = { draft, city_center: { lat: 26.9124, lon: 75.7873 }, cost_breakdown: { stops_inr: 500, transport_meals_inr: 1000, stay_inr: 1000, estimate_inr: 2500, budget_inr: 10000, complete: true }, checks: [], revisions: 0, unresolved: [], costs_are_estimates: true, demo: true };

beforeEach(() => {
  vi.clearAllMocks();
  fetchOptions.mockResolvedValue({ ok: true, options });
});

async function fillAndSubmit() {
  await screen.findByRole("button", { name: "Plan my trip" });
  fireEvent.change(screen.getByLabelText("Destination"), { target: { value: "Jaipur" } });
  fireEvent.change(screen.getByLabelText("Budget (INR)"), { target: { value: "10000" } });
  fireEvent.click(screen.getByRole("button", { name: "History" }));
  fireEvent.click(screen.getByRole("button", { name: "Plan my trip" }));
}

describe("App", () => {
  it("contains no destination name before the field is used", async () => {
    render(<App />);
    await screen.findByRole("combobox", { name: "Destination" });
    for (const name of options.cities) expect(document.body.textContent).not.toContain(name);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("shows a streamed error message and can retry", async () => {
    streamPlan.mockImplementationOnce(async (_request, onEvent) => {
      onEvent({ type: "error", data: { message: "Planning failed. Please retry." } });
    }).mockImplementationOnce(async (_request, onEvent) => {
      onEvent({ type: "result", data: result });
    });
    render(<App />);
    await fillAndSubmit();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Planning failed. Please retry.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("heading", { name: "Amber Fort" });
    expect(streamPlan).toHaveBeenCalledTimes(2);
    expect(streamPlan.mock.calls[1][0]).toEqual(streamPlan.mock.calls[0][0]);
  });

  it("uses the real result fields and shows the preview chip only when demo is true", async () => {
    streamPlan.mockImplementation(async (_request, onEvent) => {
      onEvent({ type: "step", data: { name: "intake", message: "Trip details validated.", elapsed_seconds: 0.1 } });
      onEvent({ type: "result", data: result });
    });
    render(<App />);
    expect(screen.queryByText("Preview · sample data")).toBeNull();
    await fillAndSubmit();
    expect(await screen.findByText("Preview · sample data")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Amber Fort" })).toBeTruthy();
    expect(screen.getByText("Costs are estimates.")).toBeTruthy();
    expect(screen.getByText("Within budget")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Your Jaipur itinerary" })).toBeTruthy();
    expect(screen.getByText(/Rs 2,500/)).toBeTruthy();
    expect(screen.getByText("Revisions: 0")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Map for day 1" })).toBeTruthy();
    expect(document.querySelectorAll("h1")).toHaveLength(1);
  });

  it("shows planning skeletons and does not show the preview chip for a live result", async () => {
    let finish;
    streamPlan.mockImplementation((_request, onEvent) => new Promise((resolve) => {
      finish = () => { onEvent({ type: "result", data: { ...result, demo: false } }); resolve({ ok: true }); };
    }));
    render(<App />);
    await fillAndSubmit();
    expect(await screen.findByRole("button", { name: "Planning..." })).toBeTruthy();
    expect(screen.getByLabelText("Loading itinerary")).toBeTruthy();
    await act(async () => finish());
    await waitFor(() => expect(screen.getByRole("heading", { name: "Amber Fort" })).toBeTruthy());
    expect(screen.queryByText("Preview · sample data")).toBeNull();
  });
});

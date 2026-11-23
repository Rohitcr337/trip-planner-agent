import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import { approveTrip, createTrip, fetchMe, fetchOptions, loginAccount, logoutAccount, registerAccount, streamPlan } from "../api.js";
import { clearSession, setSession } from "../auth.js";

vi.mock("../api.js", () => ({
  approveTrip: vi.fn(), createTrip: vi.fn(), fetchMe: vi.fn(), fetchOptions: vi.fn(),
  loginAccount: vi.fn(), logoutAccount: vi.fn(), registerAccount: vi.fn(), streamPlan: vi.fn(),
}));

const options = { cities: ["Jaipur"], destinations: [{ name: "Jaipur", lat: 26.9, lon: 75.8 }], styles: ["relaxed", "packed"], day_range: { min: 1, max: 7 }, interest_suggestions: ["history"] };
const draft = { city: "Jaipur", days: [{ day: 1, date: null, stops: [{ name: "Amber Fort", area: "Amer", time_slot: "morning", duration_minutes: 90, est_cost_inr: 500, notes: "Check details.", passage_ids: [], sources: [], unverified: true }] }], total_est_cost_inr: 500, assumptions: [] };
const result = { draft, city_center: { lat: 26.9, lon: 75.8 }, cost_breakdown: { stops_inr: 500, transport_meals_inr: 500, stay_inr: 500, estimate_inr: 1500, budget_inr: 10000, complete: true }, checks: [{ name: "budget", passed: true, reason: "Within budget." }], revisions: 0, unresolved: [], costs_are_estimates: true, demo: false };

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function planTrip(planResult = result) {
  await screen.findByRole("button", { name: "Plan my trip" });
  fireEvent.change(screen.getByLabelText("Destination"), { target: { value: "Jaipur" } });
  fireEvent.change(screen.getByLabelText("Budget (INR)"), { target: { value: "10000" } });
  fireEvent.click(screen.getByRole("button", { name: "History" }));
  streamPlan.mockImplementationOnce(async (_request, onEvent) => onEvent({ type: "result", data: planResult }));
  fireEvent.click(screen.getByRole("button", { name: "Plan my trip" }));
  await screen.findByRole("heading", { name: "Amber Fort" });
}

function signInAsUser() {
  setSession("session-token");
  fetchMe.mockResolvedValue({ ok: true, data: { id: 1, email: "person@example.com" } });
}

async function renderSignedInApp() {
  signInAsUser();
  render(<App />);
  await screen.findByRole("button", { name: "person@example.com" });
}

beforeEach(() => {
  clearSession();
  sessionStorage.clear();
  vi.clearAllMocks();
  fetchOptions.mockResolvedValue({ ok: true, options });
  fetchMe.mockResolvedValue({ ok: false });
  logoutAccount.mockResolvedValue({ ok: true });
  loginAccount.mockResolvedValue({ ok: true, data: { token: "session-token", user: { id: 1, email: "person@example.com" } } });
  createTrip.mockResolvedValue({ ok: true, data: { id: 12 } });
  approveTrip.mockResolvedValue({ ok: true, data: { id: 12, status: "approved" } });
});

afterEach(() => {
  cleanup();
  clearSession();
  sessionStorage.clear();
});

describe("approve and save", () => {
  it("shows the sample-plan message instead of save actions", async () => {
    render(<App />);
    await planTrip({ ...result, demo: true });
    expect(screen.getByText("Sample plans can't be saved")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Approve and save" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Discard" })).toBeNull();
  });

  it("opens sign in and continues after successful authentication", async () => {
    render(<App />);
    await planTrip();
    fireEvent.click(screen.getByRole("button", { name: "Approve and save" }));
    await screen.findByRole("dialog");
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse" } });
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("link", { name: "View My trips" })).toBeTruthy();
    expect(createTrip).toHaveBeenCalledWith(expect.objectContaining({ destination: "Jaipur", avoid: [] }), result);
    expect(approveTrip).toHaveBeenCalledWith(12);
  });

  it("shows progress and disables actions through save and approval", async () => {
    await renderSignedInApp();
    const saving = deferred();
    const approving = deferred();
    createTrip.mockReturnValueOnce(saving.promise);
    approveTrip.mockReturnValueOnce(approving.promise);
    await planTrip();
    fireEvent.click(screen.getByRole("button", { name: "Approve and save" }));
    expect(screen.getByRole("button", { name: "Saving your plan…" }).disabled).toBe(true);
    await act(async () => saving.resolve({ ok: true, data: { id: 14 } }));
    expect(screen.getByRole("button", { name: "Approving your trip…" }).disabled).toBe(true);
    await act(async () => approving.resolve({ ok: true, data: { id: 14 } }));
    expect(await screen.findByRole("link", { name: "View My trips" })).toBeTruthy();
  });

  it.each([[409, "Trip limit reached."], [413, "Trip payload is too large."]])(
    "shows a clear HTTP %s error and lets the user retry", async (status, message) => {
      await renderSignedInApp();
      createTrip.mockResolvedValueOnce({ ok: false, status, message });
      await planTrip();
      fireEvent.click(screen.getByRole("button", { name: "Approve and save" }));
      expect((await screen.findByRole("alert")).textContent).toBe(message);
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
      expect(await screen.findByRole("link", { name: "View My trips" })).toBeTruthy();
    },
  );

  it("retries approval without creating a second trip", async () => {
    await renderSignedInApp();
    approveTrip.mockResolvedValueOnce({ ok: false, status: 503, message: "Could not reach the planner." });
    await planTrip();
    fireEvent.click(screen.getByRole("button", { name: "Approve and save" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Could not reach the planner.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: "View My trips" })).toBeTruthy();
    expect(createTrip).toHaveBeenCalledTimes(1);
    expect(approveTrip).toHaveBeenCalledTimes(2);
  });

  it("discards a plan", async () => {
    render(<App />);
    await planTrip();
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(screen.getByRole("status").textContent).toBe("This plan was discarded.");
  });

  it("marks a saved plan unsaved when the form changes", async () => {
    await renderSignedInApp();
    await planTrip();
    fireEvent.click(screen.getByRole("button", { name: "Approve and save" }));
    await screen.findByRole("link", { name: "View My trips" });
    fireEvent.change(screen.getByLabelText("Budget (INR)"), { target: { value: "12000" } });
    expect(await screen.findByText("Update the plan before saving these form changes.")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "View My trips" })).toBeNull();
    expect(screen.getByRole("button", { name: "Approve and save" }).disabled).toBe(true);
  });
});

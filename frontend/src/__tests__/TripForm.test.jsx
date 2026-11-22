import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TripForm, { validateTrip } from "../components/TripForm.jsx";
import { fetchOptions } from "../api.js";

vi.mock("../api.js", () => ({ fetchOptions: vi.fn() }));

const options = { cities: ["Jaipur", "Chennai", "Goa"], destinations: [{ name: "Jaipur", lat: 26.9, lon: 75.8 }, { name: "Chennai", lat: 13.1, lon: 80.3 }, { name: "Goa", lat: 15.5, lon: 73.8 }], styles: ["relaxed", "packed"], day_range: { min: 1, max: 7 }, interest_suggestions: ["history", "food"] };
const validValues = { destination: "Jaipur", days: "3", budget: "15000", interests: ["history"], otherInterests: "", style: "relaxed", startDate: "" };

beforeEach(() => fetchOptions.mockResolvedValue({ ok: true, options }));
afterEach(() => vi.clearAllMocks());

describe("validation", () => {
  it.each([0, 8, 1.5, "", "no", Infinity])("rejects invalid days %s", (days) => {
    expect(validateTrip({ ...validValues, days }, options).errors.days).toBeTruthy();
  });

  it.each([0, -1, "", "NaN", Infinity])("rejects invalid budget %s", (budget) => {
    expect(validateTrip({ ...validValues, budget }, options).errors.budget).toBeTruthy();
  });

  it.each([1, 7])("accepts the day boundary %s", (days) => {
    expect(validateTrip({ ...validValues, days }, options).request.days).toBe(days);
  });

  it("requires a supported city, an interest and a supported pace", () => {
    const outcome = validateTrip({ ...validValues, destination: "Delhi", interests: [], style: "fast" }, options);
    expect(Object.keys(outcome.errors)).toEqual(["destination", "interests", "style"]);
    expect(outcome.request).toBeNull();
  });

  it("accepts and deduplicates comma-separated custom interests", () => {
    const outcome = validateTrip({ ...validValues, otherInterests: " History, street art, , cycling, Street Art " }, options);
    expect(outcome.request.interests).toEqual(["history", "street art", "cycling"]);
    expect(outcome.request.start_date).toBeNull();
  });

  it("accepts a real optional ISO date, but rejects an impossible date", () => {
    expect(validateTrip({ ...validValues, startDate: "2027-02-28" }, options).request.start_date).toBe("2027-02-28");
    expect(validateTrip({ ...validValues, startDate: "2027-02-30" }, options).errors.startDate).toBeTruthy();
  });
});

describe("TripForm", () => {
  it("loads options and presents a linked, focused error summary", async () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} />);
    const submit = await screen.findByRole("button", { name: "Plan my trip" });
    fireEvent.click(submit);
    const summary = screen.getByRole("alert");
    await waitFor(() => expect(document.activeElement).toBe(summary));
    expect(screen.getByRole("link", { name: /Destination: Choose a destination from the list/ }).getAttribute("href")).toBe("#trip-destination");
    fireEvent.click(screen.getByRole("link", { name: /Destination: Choose a destination from the list/ }));
    expect(document.activeElement).toBe(screen.getByLabelText("Destination"));
    expect(screen.getByLabelText("Budget (INR)").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText(/Total per person, in INR/)).toBeTruthy();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a structured request, combining selected and custom interests", async () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} />);
    await screen.findByRole("button", { name: "Plan my trip" });
    fireEvent.change(screen.getByLabelText("Destination"), { target: { value: "Goa" } });
    fireEvent.change(screen.getByLabelText("Days"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Budget (INR)"), { target: { value: "12000" } });
    fireEvent.click(screen.getByRole("button", { name: "Food" }));
    expect(screen.getByRole("button", { name: "Food" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.change(screen.getByLabelText("Other interests"), { target: { value: "cycling" } });
    fireEvent.click(screen.getByLabelText("Packed"));
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-12-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan my trip" }));
    expect(onSubmit).toHaveBeenCalledWith({ destination: "Goa", days: 2, budget: 12000, interests: ["food", "cycling"], style: "packed", start_date: "2026-12-01" });
  });

  it("can deselect an interest and submit custom interests alone", async () => {
    const onSubmit = vi.fn();
    render(<TripForm onSubmit={onSubmit} />);
    await screen.findByRole("button", { name: "Plan my trip" });
    fireEvent.change(screen.getByLabelText("Destination"), { target: { value: "Chennai" } });
    fireEvent.change(screen.getByLabelText("Budget (INR)"), { target: { value: "5000" } });
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.click(screen.getByRole("button", { name: "History" }));
    fireEvent.change(screen.getByLabelText("Other interests"), { target: { value: "art" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan my trip" }));
    expect(onSubmit.mock.calls[0][0].interests).toEqual(["art"]);
  });

  it("disables controls and shows Planning... while planning", async () => {
    render(<TripForm planning />);
    const button = await screen.findByRole("button", { name: "Planning..." });
    expect(button.disabled).toBe(true);
    expect(screen.getByLabelText("Destination").closest("fieldset").disabled).toBe(true);
  });

  it("shows an options error and retries", async () => {
    fetchOptions.mockResolvedValueOnce({ ok: false, message: "Offline" });
    render(<TripForm />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText("Offline")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByRole("button", { name: "Plan my trip" });
    expect(fetchOptions).toHaveBeenCalledTimes(2);
  });
});

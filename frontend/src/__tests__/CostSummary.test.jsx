import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CostSummary from "../components/CostSummary.jsx";

const breakdown = { stops_inr: 200, transport_meals_inr: 300, stay_inr: 300, estimate_inr: 800, budget_inr: 1000, complete: true };

describe("CostSummary", () => {
  it.each([
    [800, "Within budget"],
    [850, "Within budget"],
    [900, "Close to budget"],
    [1000, "Close to budget"],
    [1100, "Over budget by Rs 100"],
  ])("uses the whole-trip estimate for Rs %s of Rs 1000", (estimate, label) => {
    render(<CostSummary breakdown={{ ...breakdown, estimate_inr: estimate }} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText(`${Math.round(estimate / 10)}% of budget`)).toBeTruthy();
    expect(screen.getByText(label).querySelector("svg")).toBeTruthy();
  });

  it("shows the whole-trip figure and all cost categories", () => {
    const { container } = render(<CostSummary breakdown={breakdown} />);
    expect(screen.getByRole("heading", { name: "Trip cost estimate" })).toBeTruthy();
    expect(screen.getByText("whole trip, per person")).toBeTruthy();
    expect([...container.querySelectorAll("dt")].map((el) => el.textContent)).toEqual(["Stops", "Transport and meals", "Stay"]);
    expect([...container.querySelectorAll("dd")].map((el) => el.textContent)).toEqual(["Rs 200", "Rs 300", "Rs 300"]);
  });

  it("uses an honest stops-only fallback without a misleading budget band", () => {
    render(<CostSummary breakdown={{ ...breakdown, complete: false, estimate_inr: null, stay_inr: null }} />);
    expect(screen.getByRole("heading", { name: "Estimated stop costs" })).toBeTruthy();
    expect(screen.getByText("stops only")).toBeTruthy();
    expect(screen.getByText(/full trip estimate is unavailable/)).toBeTruthy();
    expect(screen.getByText("Unavailable")).toBeTruthy();
    expect(screen.queryByText("Within budget")).toBeNull();
    expect(screen.queryByText(/% of budget/)).toBeNull();
  });

  it("uses stops only even when an incomplete breakdown has a partial estimate", () => {
    render(<CostSummary breakdown={{ ...breakdown, complete: false }} />);
    expect(screen.queryByText(/Rs 800/)).toBeNull();
    expect(screen.getByText(/full trip estimate is unavailable/)).toBeTruthy();
  });

  it("handles a zero-cost draft, no draft and loading", () => {
    const { rerender } = render(<CostSummary breakdown={{ ...breakdown, estimate_inr: 0 }} />);
    expect(screen.getByText("Within budget")).toBeTruthy();
    expect(screen.getByText("0% of budget")).toBeTruthy();
    rerender(<CostSummary />);
    expect(screen.getByText(/once a draft is ready/)).toBeTruthy();
    rerender(<CostSummary loading />);
    expect(screen.getByText("Calculating the trip estimate")).toBeTruthy();
  });
});

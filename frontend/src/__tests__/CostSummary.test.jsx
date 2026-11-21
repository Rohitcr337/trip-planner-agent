import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CostSummary from "../components/CostSummary.jsx";

describe("CostSummary", () => {
  it.each([
    [800, "Within budget"],
    [850, "Within budget"],
    [900, "Close to budget"],
    [1000, "Close to budget"],
    [1100, "Over budget by Rs 100"],
  ])("uses the right label for Rs %s of Rs 1000", (estimate, label) => {
    render(<CostSummary estimate={estimate} budget={1000} />);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText(`${Math.round(estimate / 10)}% of budget`)).toBeTruthy();
  });

  it("honestly labels the comparison as stop costs", () => {
    render(<CostSummary estimate={800} budget={1000} />);
    expect(screen.getByRole("heading", { name: "Estimated stop costs" })).toBeTruthy();
    expect(screen.getByText(/Meals, local transport and stay are not included/)).toBeTruthy();
  });

  it("handles a zero-cost draft, no draft and loading", () => {
    const { rerender } = render(<CostSummary estimate={0} budget={1000} />);
    expect(screen.getByText("Within budget")).toBeTruthy();
    expect(screen.getByText("0% of budget")).toBeTruthy();
    rerender(<CostSummary />);
    expect(screen.getByText(/once a draft is ready/)).toBeTruthy();
    rerender(<CostSummary loading />);
    expect(screen.getByText("Calculating estimated stop costs")).toBeTruthy();
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ChecksPanel from "../components/ChecksPanel.jsx";

const checks = [
  { name: "budget", passed: true, reason: "Costs fit the budget." },
  { name: "logistics", passed: false, reason: "Too many stops on day 1." },
  { name: "sources", passed: true, reason: "skipped: guide data is unavailable." },
];

describe("ChecksPanel", () => {
  it("is collapsible and reports revisions, all states and their reasons", () => {
    const { container } = render(<ChecksPanel checks={checks} revisions={3} />);
    const details = container.querySelector("details");
    expect(details.open).toBe(false);
    expect(screen.getByText("Revisions: 3")).toBeTruthy();
    fireEvent.click(container.querySelector("summary"));
    expect(details.open).toBe(true);
    for (const state of ["PASS", "FAIL", "SKIPPED"]) {
      expect(screen.getByText(state).querySelector("svg")).toBeTruthy();
    }
    for (const check of checks) expect(screen.getByText(check.reason)).toBeTruthy();
    fireEvent.click(container.querySelector("summary"));
    expect(details.open).toBe(false);
  });

  it("recognizes skipped reasons regardless of case rather than calling them passed", () => {
    render(<ChecksPanel checks={[{ ...checks[0], reason: "SKIPPED: no costs." }]} />);
    expect(screen.getByText("SKIPPED")).toBeTruthy();
    expect(screen.queryByText("PASS")).toBeNull();
  });

  it("handles an empty check list", () => {
    render(<ChecksPanel />);
    expect(screen.getByText("Revisions: 0")).toBeTruthy();
    expect(screen.getByText("No checks were reported.")).toBeTruthy();
  });
});

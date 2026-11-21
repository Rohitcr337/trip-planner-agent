import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ProgressSteps from "../components/ProgressSteps.jsx";

const step = (name) => ({ name, message: `${name} completed`, elapsed_seconds: 0.25 });

it("shows pending steps, the active step, and completed elapsed times", () => {
  const { container } = render(<ProgressSteps steps={[step("intake")]} status="planning" />);
  expect(screen.getByText("Done · 0.3s")).toBeTruthy();
  expect(screen.getAllByText("Pending")).toHaveLength(3);
  expect(container.querySelector('[aria-current="step"]').textContent).toContain("Travel guides");
  expect(container.querySelector('[aria-live="polite"]').textContent).toBe("intake completed");
});

it("does not claim a revision will happen after check; repeated checks have round labels", () => {
  const base = ["intake", "retrieve", "fetch", "draft", "check"].map(step);
  const { rerender } = render(<ProgressSteps steps={base} status="planning" />);
  expect(screen.getByText("Finalizing the plan")).toBeTruthy();
  rerender(<ProgressSteps steps={[...base, step("revise"), step("check")]} status="complete" />);
  expect(screen.getByText("Plan checks (round 2)")).toBeTruthy();
  expect(screen.getByText("Finished")).toBeTruthy();
  expect(screen.queryByText("Pending")).toBeNull();
});

it("renders the failure message and an error state", () => {
  render(<ProgressSteps status="error" message="Planning failed. Please retry." />);
  expect(screen.getByText("Error")).toBeTruthy();
  expect(screen.getAllByText("Planning failed. Please retry.").length).toBeGreaterThan(0);
});

it("renders all initial steps as pending", () => {
  render(<ProgressSteps />);
  expect(screen.getAllByText("Pending")).toHaveLength(5);
});

import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import ProgressSteps from "../components/ProgressSteps.jsx";

const step = (name) => ({ name, message: `${name} completed`, elapsed_seconds: 0.25 });

it("shows only reported steps and their elapsed times without predicting upcoming steps", () => {
  const { container } = render(<ProgressSteps steps={[step("intake")]} status="planning" />);
  expect(screen.getByText("Done · 0.3s")).toBeTruthy();
  expect(screen.getByText("Trip details")).toBeTruthy();
  expect(screen.queryByText("Travel guides")).toBeNull();
  expect(screen.queryByText("Pending")).toBeNull();
  expect(screen.getByText("Planning in progress")).toBeTruthy();
  expect(container.querySelector('[aria-live="polite"]').textContent).toBe("intake completed");
});

it("labels place lookup, revisions and repeated checks from the events actually seen", () => {
  const steps = ["intake", "retrieve", "fetch", "draft", "locate", "check", "revise", "locate", "check"].map(step);
  render(<ProgressSteps steps={steps} status="complete" />);
  expect(screen.getByText("Place locations")).toBeTruthy();
  expect(screen.getByText("Place locations (round 2)")).toBeTruthy();
  expect(screen.getByText("Plan checks (round 2)")).toBeTruthy();
  expect(screen.getByText("Draft revision")).toBeTruthy();
  expect(screen.getByText("Finished")).toBeTruthy();
  expect(screen.queryByText("Planning in progress")).toBeNull();
});

it("renders a failure message without inventing a failed node", () => {
  render(<ProgressSteps status="error" message="Planning failed. Please retry." />);
  expect(screen.getByText("Error")).toBeTruthy();
  expect(screen.getAllByText("Planning failed. Please retry.").length).toBeGreaterThan(0);
  expect(screen.queryByText("Trip details")).toBeNull();
});

it("does not populate initial steps before any event", () => {
  const { container } = render(<ProgressSteps />);
  expect(container.querySelectorAll("ol li")).toHaveLength(0);
});

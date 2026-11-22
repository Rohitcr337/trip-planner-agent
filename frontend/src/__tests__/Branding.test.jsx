import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import Header from "../components/Header.jsx";
import { fetchOptions } from "../api.js";

vi.mock("../api.js", () => ({ fetchOptions: vi.fn(), streamPlan: vi.fn() }));

afterEach(() => window.history.pushState({}, "", "/"));

describe("branding", () => {
  it("shows the Cairn name next to a three-stone mark that links home", () => {
    render(<Header />);
    const link = screen.getByRole("link", { name: "Cairn" });
    expect(link.getAttribute("href")).toBe("/");
    const mark = link.querySelector("svg");
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(mark.querySelectorAll("rect")).toHaveLength(3);
  });

  it("shows the tagline, supporting line and footer on the planner page", () => {
    fetchOptions.mockReturnValue(new Promise(() => {}));
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "Trip plans, traced to their sources." })).toBeTruthy();
    expect(screen.getByText("Itineraries built from travel guides, checked against your budget and travel times.")).toBeTruthy();
    expect(screen.getByText("Costs are estimates. Check details before you book.")).toBeTruthy();
  });

  it("renders a not-found page for unknown paths", () => {
    window.history.pushState({}, "", "/missing-page");
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Plan a trip" }).getAttribute("href")).toBe("/");
    expect(document.title).toBe("Page not found · Cairn");
    expect(fetchOptions).not.toHaveBeenCalled();
  });
});

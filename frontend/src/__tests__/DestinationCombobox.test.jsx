import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import DestinationCombobox from "../components/DestinationCombobox.jsx";

const names = ["Jaipur", "Chennai", "Goa"];

function Harness({ onSelect = () => {} }) {
  const [value, setValue] = useState("");
  return (
    <>
      <label htmlFor="destination">Destination</label>
      <DestinationCombobox id="destination" names={names} value={value} onChange={(next) => { setValue(next); onSelect(next); }} />
    </>
  );
}

it("has no destination names or listbox before the field is used", () => {
  render(<Harness />);
  const input = screen.getByRole("combobox", { name: "Destination" });
  expect(input.getAttribute("placeholder")).toBe("Search a destination");
  expect(input.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("listbox")).toBeNull();
  for (const name of names) expect(screen.queryByText(name)).toBeNull();
});

it("supports keyboard navigation, selection and Escape", () => {
  const onSelect = vi.fn();
  render(<Harness onSelect={onSelect} />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "ArrowDown" });
  const active = document.getElementById(input.getAttribute("aria-activedescendant"));
  expect(active.textContent).toBe("Chennai");
  fireEvent.keyDown(input, { key: "Enter" });
  expect(input.value).toBe("Chennai");
  expect(onSelect).toHaveBeenLastCalledWith("Chennai");
  expect(input.getAttribute("aria-expanded")).toBe("false");
  fireEvent.keyDown(input, { key: "ArrowUp" });
  expect(screen.getByRole("listbox")).toBeTruthy();
  fireEvent.keyDown(input, { key: "Escape" });
  expect(screen.queryByRole("listbox")).toBeNull();
  expect(input.getAttribute("aria-activedescendant")).toBeNull();
});

it("starts ArrowUp at the last option and wraps through the list", () => {
  render(<Harness />);
  const input = screen.getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.keyDown(input, { key: "ArrowUp" });
  expect(document.getElementById(input.getAttribute("aria-activedescendant")).textContent).toBe("Goa");
  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(document.getElementById(input.getAttribute("aria-activedescendant")).textContent).toBe("Jaipur");
});

it("filters typed text and offers available options when nothing matches", () => {
  const onSelect = vi.fn();
  render(<Harness onSelect={onSelect} />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "chen" } });
  expect(screen.getAllByRole("option")).toHaveLength(1);
  fireEvent.change(input, { target: { value: "London" } });
  expect(screen.getByText("That destination isn't available yet")).toBeTruthy();
  expect(screen.getAllByRole("option")).toHaveLength(3);
  expect(onSelect).toHaveBeenLastCalledWith("");
  fireEvent.click(screen.getByRole("option", { name: "Goa" }));
  expect(input.value).toBe("Goa");
  expect(input.getAttribute("aria-expanded")).toBe("false");
});

it("clears a previous selection when the input becomes unsupported and closes on blur", () => {
  const onSelect = vi.fn();
  render(<Harness onSelect={onSelect} />);
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "jaipur" } });
  expect(onSelect).toHaveBeenLastCalledWith("Jaipur");
  fireEvent.change(input, { target: { value: "Jai" } });
  expect(onSelect).toHaveBeenLastCalledWith("");
  fireEvent.blur(input);
  expect(screen.queryByRole("listbox")).toBeNull();
});

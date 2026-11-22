import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MapView from "../components/MapView.jsx";

const map = vi.hoisted(() => ({ fitBounds: vi.fn(), setView: vi.fn(), attributionControl: { setPrefix: vi.fn() } }));
vi.mock("react-leaflet", () => ({
  MapContainer: ({ children, center }) => <div data-testid="map" data-center={JSON.stringify(center)}>{children}</div>,
  TileLayer: ({ attribution, url, eventHandlers }) => <button data-url={url} data-attribution={attribution} onClick={eventHandlers.tileerror}>Simulate tile error</button>,
  Marker: ({ title, position, icon }) => {
    // Leaflet creates marker titles once instead of updating them.
    const [initialTitle] = useState(title);
    return <button title={initialTitle} data-position={JSON.stringify(position)} data-pin={icon.options.html}>{initialTitle}</button>;
  },
  Popup: () => null,
  Polyline: ({ positions }) => <span data-testid="route" data-positions={JSON.stringify(positions)} />,
  useMap: () => map,
}));

const center = { lat: 26.9124, lon: 75.7873 };
const first = { name: "Amber Fort", area: "Amer", lat: null, lon: null };
const second = { name: "City Palace", area: "Old City", lat: 26.925, lon: 75.823 };
const draft = { city: "Jaipur", days: [{ day: 1, stops: [first, { ...second, lat: null, lon: null }] }] };
beforeEach(() => vi.clearAllMocks());

describe("MapView", () => {
  it("uses the backend city centre, shows the map note and provides a place-list fallback without coordinates", () => {
    render(<MapView draft={draft} cityCenter={center} />);
    expect(screen.getByText("Map pins appear when place lookup is enabled.")).toBeTruthy();
    expect(map.setView).toHaveBeenCalledWith([center.lat, center.lon], 12, { animate: false });
    expect(map.fitBounds).not.toHaveBeenCalled();
    expect(screen.getByRole("list", { name: "Places for day 1" }).textContent).toContain("Amber Fort");
    expect(screen.getByText("Simulate tile error").getAttribute("data-attribution")).toContain("OpenStreetMap");
    expect(screen.queryByTitle(/Day 1, stop/)).toBeNull();
  });

  it("numbers real pins by their day-card position and fits the map to them", () => {
    render(<MapView draft={{ ...draft, days: [{ day: 1, stops: [first, second] }] }} cityCenter={center} />);
    const pin = screen.getByTitle("Day 1, stop 2: City Palace");
    expect(pin.getAttribute("data-position")).toBe(JSON.stringify([second.lat, second.lon]));
    expect(pin.getAttribute("data-pin")).toContain(">2</span>");
    expect(screen.queryByTitle("Day 1, stop 1: Amber Fort")).toBeNull();
    expect(screen.queryByText("Map pins appear when place lookup is enabled.")).toBeNull();
    expect(map.fitBounds).toHaveBeenCalledWith([[second.lat, second.lon]], { padding: [32, 32], maxZoom: 15, animate: false });
  });

  it("switches days and only connects adjacent located stops", () => {
    const located = { ...first, lat: 26.985, lon: 75.851 };
    const days = [{ day: 1, stops: [located, second] }, { day: 2, stops: [located, first, second] }];
    render(<MapView draft={{ ...draft, days }} cityCenter={center} />);
    expect(screen.getAllByTestId("route")).toHaveLength(1);
    expect(screen.getByText("Lines show stop order, not road routes.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Day 2" }));
    expect(screen.getByTitle("Day 2, stop 3: City Palace")).toBeTruthy();
    expect(screen.queryByTestId("route")).toBeNull();
    expect(screen.getByRole("list", { name: "Places for day 2" })).toBeTruthy();
  });

  it.each([
    { lat: null, lon: 75 }, { lat: 26, lon: undefined },
    { lat: "26", lon: 75 }, { lat: 91, lon: 75 }, { lat: 26, lon: 181 },
  ])("never creates a pin from invalid or missing coordinates %j", (point) => {
    render(<MapView draft={{ ...draft, days: [{ day: 1, stops: [{ ...first, ...point }] }] }} cityCenter={center} />);
    expect(screen.queryByTitle(/stop 1:/)).toBeNull();
    expect(map.fitBounds).not.toHaveBeenCalled();
  });

  it("shows a useful list when tiles fail and handles an empty draft", () => {
    const { rerender } = render(<MapView draft={draft} cityCenter={center} />);
    fireEvent.click(screen.getByText("Simulate tile error"));
    expect(screen.getByRole("status").textContent).toContain("Use the place list below");
    expect(screen.getByRole("list", { name: "Places for day 1" })).toBeTruthy();
    rerender(<MapView draft={null} cityCenter={center} />);
    expect(screen.getByText("No stops were included for this day.")).toBeTruthy();
  });
});

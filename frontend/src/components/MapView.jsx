import { useEffect, useMemo, useState } from "react";
import { divIcon } from "leaflet";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import { Info, MapPin } from "lucide-react";

function hasCoordinates(stop) {
  return Number.isFinite(stop.lat) && Number.isFinite(stop.lon)
    && Math.abs(stop.lat) <= 90 && Math.abs(stop.lon) <= 180;
}

function MapViewport({ points, center }) {
  const map = useMap();
  useEffect(() => {
    map.attributionControl.setPrefix(false);
    if (points.length) {
      map.fitBounds(points, { padding: [32, 32], maxZoom: 15, animate: false });
    } else {
      map.setView(center, 12, { animate: false });
    }
  }, [map, points, center]);
  return null;
}

export default function MapView({ draft, cityCenter }) {
  const days = draft?.days ?? [];
  const [selectedDay, setSelectedDay] = useState(days[0]?.day);
  const [tileError, setTileError] = useState(false);
  const day = days.find((item) => item.day === selectedDay) ?? days[0];
  const stops = day?.stops;
  const points = useMemo(() => (stops ?? []).filter(hasCoordinates).map((stop) => [stop.lat, stop.lon]), [stops]);
  const center = useMemo(() => [cityCenter.lat, cityCenter.lon], [cityCenter.lat, cityCenter.lon]);
  const anyLocated = days.some((item) => item.stops.some(hasCoordinates));

  return (
    <section aria-labelledby="map-heading" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
      <h3 id="map-heading" className="flex items-center gap-2 text-h3"><MapPin aria-hidden="true" className="size-6 text-primary" />Your places</h3>
      {days.length > 1 && (
        <div role="group" aria-label="Map day" className="mt-4 flex flex-wrap gap-2">
          {days.map((item) => (
            <button
              key={item.day}
              type="button"
              aria-pressed={day.day === item.day}
              onClick={() => setSelectedDay(item.day)}
              className={`inline-flex min-h-11 items-center rounded-control border px-4 text-small font-semibold transition-colors duration-(--duration-press) ease-standard ${day.day === item.day ? "border-primary bg-primary-soft text-primary" : "border-border-strong bg-surface text-text hover:bg-surface-muted"}`}
            >
              Day {item.day}
            </button>
          ))}
        </div>
      )}
      <div role="region" aria-label={day ? `Map for day ${day.day}` : "Destination map"} className="cairn-map relative z-0 mt-4 overflow-hidden rounded-control border border-border-strong">
        <MapContainer
          center={center}
          zoom={12}
          scrollWheelZoom={false}
          zoomAnimation={false}
          fadeAnimation={false}
          markerZoomAnimation={false}
          className="h-80 w-full sm:h-96"
        >
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution={'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}
            eventHandlers={{ tileerror: () => setTileError(true) }}
          />
          <MapViewport points={points} center={center} />
          {(stops ?? []).map((stop, index) => hasCoordinates(stop) && (
            <Marker
              key={`${day.day}-${index}`}
              position={[stop.lat, stop.lon]}
              icon={divIcon({ className: "cairn-numbered-marker", html: `<span class="cairn-map-pin">${index + 1}</span>`, iconSize: [44, 44], iconAnchor: [22, 22] })}
              title={`Day ${day.day}, stop ${index + 1}: ${stop.name}`}
              alt={`Day ${day.day}, stop ${index + 1}: ${stop.name}`}
            >
              <Popup>
                <p className="text-small font-semibold">{index + 1}. {stop.name}</p>
                <p className="text-small text-text-muted">{stop.area}</p>
              </Popup>
            </Marker>
          ))}
          {(stops ?? []).map((stop, index) => index > 0 && hasCoordinates(stop) && hasCoordinates(stops[index - 1]) && (
            <Polyline key={`leg-${index}`} positions={[[stops[index - 1].lat, stops[index - 1].lon], [stop.lat, stop.lon]]} pathOptions={{ className: "cairn-map-route", dashArray: "6 6", weight: 3 }} />
          ))}
        </MapContainer>
      </div>
      {!anyLocated && (
        <p className="mt-3 flex items-start gap-2 text-small text-text-muted"><Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />Map pins appear when place lookup is enabled.</p>
      )}
      {points.length > 1 && <p className="mt-3 text-small text-text-muted">Lines show stop order, not road routes.</p>}
      {tileError && <p role="status" className="mt-3 flex items-start gap-2 text-small text-warning"><Info aria-hidden="true" className="mt-0.5 size-4 shrink-0" />Map tiles could not be loaded. Use the place list below.</p>}
      <h4 className="mt-5 text-small font-semibold">{day ? `Day ${day.day} place list` : "Place list"}</h4>
      {stops?.length ? (
        <ol className="mt-3 space-y-3" aria-label={`Places for day ${day.day}`}>
          {stops.map((stop, index) => (
            <li key={index} className="flex items-start gap-3 text-small">
              <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-pill bg-primary-soft text-caption font-semibold text-primary">{index + 1}</span>
              <div className="min-w-0"><p className="break-words font-semibold">{stop.name}</p><p className="break-words text-text-muted">{stop.area}{!hasCoordinates(stop) && " · Location unavailable"}</p></div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-2 text-small text-text-muted">No stops were included for this day.</p>
      )}
    </section>
  );
}

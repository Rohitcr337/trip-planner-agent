import { useEffect, useState } from "react";
import { deleteTrip, fetchOptions, fetchTrip, listTrips } from "../api.js";
import { formatInr } from "../format.js";
import { useAuth } from "./AuthProvider.jsx";
import CostSummary from "./CostSummary.jsx";
import MapView from "./MapView.jsx";
import ChecksPanel from "./ChecksPanel.jsx";
import ItineraryTimeline from "./ItineraryTimeline.jsx";

function approvedDate(value) {
  if (!value) return "Approval date unavailable";
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(new Date(value));
}

function tripEstimate(trip) {
  const breakdown = trip.cost_breakdown || {};
  return breakdown.complete === true && Number.isFinite(breakdown.estimate_inr)
    ? formatInr(breakdown.estimate_inr)
    : "Estimate unavailable";
}

function TripCard({ trip, onOpen, onDelete }) {
  return (
    <article className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
      <h2 className="text-h3"><a href={`#/trips/${trip.id}`} onClick={(event) => { event.preventDefault(); onOpen(trip.id); }} className="text-primary underline underline-offset-2">{trip.title}</a></h2>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-small text-text-muted">
        <div><dt className="inline">Approved </dt><dd className="inline">{approvedDate(trip.approved_at)}</dd></div>
        <div><dt className="inline">Estimate </dt><dd className="inline">{tripEstimate(trip)} against {formatInr(trip.request?.budget || 0)}</dd></div>
        <div><dt className="inline">Days </dt><dd className="inline">{trip.request?.days ?? trip.draft?.days?.length ?? 0}</dd></div>
      </dl>
      <button type="button" onClick={() => onDelete(trip)} className="mt-4 min-h-11 rounded-control border border-border-strong px-4 text-small font-semibold text-text hover:bg-surface-muted">Delete</button>
    </article>
  );
}

function DeleteDialog({ trip, onCancel, onConfirm, busy, error }) {
  useEffect(() => {
    if (!trip) return undefined;
    const onKey = (event) => { if (event.key === "Escape" && !busy) onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [trip, busy, onCancel]);
  if (!trip) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <section role="alertdialog" aria-modal="true" aria-labelledby="delete-trip-heading" className="w-full max-w-prose rounded-card bg-surface p-6 shadow-2">
        <h2 id="delete-trip-heading" className="text-h3">Delete this trip?</h2>
        <p className="mt-2 text-small text-text-muted">{trip.title} will be permanently removed from your saved trips.</p>
        {error && <p role="alert" className="mt-3 text-small text-danger">{error}</p>}
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" disabled={busy} onClick={onCancel} className="min-h-11 rounded-control border border-border-strong px-4 text-small font-semibold disabled:opacity-50">Cancel</button>
          <button type="button" disabled={busy} onClick={onConfirm} className="min-h-11 rounded-control bg-danger px-4 text-small font-semibold text-on-primary disabled:opacity-50">{busy ? "Deleting…" : "Delete trip"}</button>
        </div>
      </section>
    </div>
  );
}

export default function SavedTrips({ tripId, navigate }) {
  const { user, openSignIn } = useAuth();
  const [trips, setTrips] = useState([]);
  const [trip, setTrip] = useState(null);
  const [center, setCenter] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  async function load() {
    setLoading(true); setError("");
    const response = tripId ? await fetchTrip(tripId) : await listTrips();
    if (!response.ok) { setError(response.message || "Saved trips could not be loaded. Please retry."); setLoading(false); return; }
    if (tripId) {
      setTrip(response.data);
      const optionsResult = await fetchOptions();
      const city = response.data?.request?.destination;
      setCenter(optionsResult.ok ? optionsResult.options.destinations.find((item) => item.name.toLowerCase() === String(city).toLowerCase()) || null : null);
    } else {
      const rows = Array.isArray(response.data) ? response.data : response.data?.trips || [];
      setTrips([...rows].sort((a, b) => new Date(b.created_at) - new Date(a.created_at) || Number(b.id) - Number(a.id)));
    }
    setLoading(false);
  }

  useEffect(() => {
    if (user) load();
    else { setLoading(false); setError(""); }
  }, [user, tripId]);

  async function confirmDelete() {
    if (!deleting) return;
    setDeleteBusy(true); setDeleteError("");
    const response = await deleteTrip(deleting.id);
    setDeleteBusy(false);
    if (!response.ok) { setDeleteError(response.message || "The trip could not be deleted. Please retry."); return; }
    if (tripId) navigate("#/trips");
    else setTrips((current) => current.filter((item) => item.id !== deleting.id));
    setDeleting(null);
  }

  return (
    <section className="mx-auto max-w-content py-8 lg:py-12">
      <a href="#/trips" onClick={(event) => { event.preventDefault(); navigate("#/trips"); }} className="text-small text-primary underline underline-offset-2">My trips</a>
      <h1 className="mt-3 text-display-phone text-text sm:text-display">{tripId ? trip?.title || "Saved trip" : "My trips"}</h1>
      {!user && <div className="mt-6 rounded-card bg-surface p-6 shadow-1"><p className="text-small">Sign in to view your saved trips.</p><button type="button" onClick={() => openSignIn()} className="mt-4 min-h-11 rounded-control bg-primary px-4 text-small font-semibold text-on-primary">Sign in</button></div>}
      {user && loading && <p role="status" aria-busy="true" className="mt-6 text-small text-text-muted">Loading saved trips…</p>}
      {user && !loading && error && <div className="mt-6 rounded-card bg-surface p-6"><p role="alert" className="text-small text-danger">{error}</p><button type="button" onClick={load} className="mt-4 min-h-11 rounded-control bg-primary px-4 text-small font-semibold text-on-primary">Retry</button></div>}
      {user && !loading && !error && !tripId && (trips.length ? <div className="mt-6 space-y-4">{trips.map((item) => <TripCard key={item.id} trip={item} onOpen={(id) => navigate(`#/trips/${id}`)} onDelete={(value) => { setDeleteError(""); setDeleting(value); }} />)}</div> : <p className="mt-6 rounded-card bg-surface p-6 text-small text-text-muted">No saved trips yet</p>)}
      {user && !loading && !error && tripId && trip && (
        <div className="mt-6 space-y-6">
          <p className="text-small text-text-muted">Approved {approvedDate(trip.approved_at)} · {trip.request?.days ?? trip.draft?.days?.length ?? 0} days</p>
          <CostSummary breakdown={trip.cost_breakdown} />
          {center ? <MapView draft={trip.draft} cityCenter={center} /> : <p role="status" className="rounded-card bg-surface p-4 text-small text-text-muted">Map location is unavailable for this destination.</p>}
          <ChecksPanel checks={trip.checks || []} revisions={0} />
          <ItineraryTimeline draft={trip.draft} costsAreEstimates={true} unresolved={[]} status="complete" />
          <button type="button" onClick={() => { setDeleteError(""); setDeleting(trip); }} className="min-h-11 rounded-control border border-danger px-4 text-small font-semibold text-danger">Delete trip</button>
        </div>
      )}
      <DeleteDialog trip={deleting} onCancel={() => setDeleting(null)} onConfirm={confirmDelete} busy={deleteBusy} error={deleteError} />
    </section>
  );
}

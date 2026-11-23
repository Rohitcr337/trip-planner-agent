import { useEffect, useRef, useState } from "react";
import { approveTrip, createTrip } from "../api.js";
import { useAuth } from "./AuthProvider.jsx";

const EMPTY = { status: "idle", tripId: null, message: "", error: "" };

export default function SavePlanActions({ request, result, formChanged = false }) {
  const { user, openSignIn } = useAuth();
  const [save, setSave] = useState(EMPTY);
  const operation = useRef(0);
  const busy = save.status === "saving" || save.status === "approving";

  useEffect(() => {
    operation.current += 1;
    setSave(EMPTY);
  }, [request, result]);

  useEffect(() => () => {
    operation.current += 1;
  }, []);

  useEffect(() => {
    if (!formChanged) return;
    operation.current += 1;
    setSave(EMPTY);
  }, [formChanged]);

  async function approveExisting(tripId, operationId) {
    setSave({ status: "approving", tripId, message: "Approving your trip…", error: "" });
    const approved = await approveTrip(tripId);
    if (operation.current !== operationId) return;
    if (!approved.ok) {
      setSave({ status: "error", tripId, message: "", error: approved.message || "Your trip could not be approved. Please retry." });
      return;
    }
    setSave({ status: "saved", tripId, message: "Your trip was approved and saved.", error: "" });
  }

  async function savePlan(authenticatedUser = user) {
    if (!authenticatedUser) {
      openSignIn((signedInUser) => savePlan(signedInUser));
      return;
    }
    if (busy || formChanged) return;
    const operationId = ++operation.current;
    if (save.tripId) {
      await approveExisting(save.tripId, operationId);
      return;
    }
    setSave({ status: "saving", tripId: null, message: "Saving your plan…", error: "" });
    const created = await createTrip(request, result);
    if (operation.current !== operationId) return;
    if (!created.ok || !created.data?.id) {
      setSave({ status: "error", tripId: null, message: "", error: created.message || "Your trip could not be saved. Please retry." });
      return;
    }
    await approveExisting(created.data.id, operationId);
  }

  if (result?.demo === true) {
    return <p className="rounded-card bg-surface-muted p-4 text-small text-text-muted">Sample plans can&apos;t be saved</p>;
  }

  const disabled = busy || formChanged;
  if (save.status === "saved" || save.status === "discarded") {
    return (
      <p role="status" className="rounded-card bg-surface p-4 text-small text-success">
        {save.message}
        {save.status === "saved" && <a className="ml-2 text-primary underline underline-offset-2" href="#/trips">View My trips</a>}
      </p>
    );
  }

  return (
    <section aria-label="Save your plan" className="rounded-card bg-surface p-4 shadow-1 sm:p-6">
      {save.message && <p role="status" className="mb-3 text-small text-text-muted">{save.message}</p>}
      {save.error && <p role="alert" className="mb-3 text-small text-danger">{save.error}</p>}
      {formChanged && <p className="mb-3 text-small text-warning">Update the plan before saving these form changes.</p>}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={disabled}
          onClick={() => savePlan()}
          className="inline-flex min-h-11 items-center justify-center rounded-control bg-primary px-4 text-small font-semibold text-on-primary hover:bg-primary-hover disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted"
        >
          {busy ? save.message : save.status === "error" ? "Retry" : "Approve and save"}
        </button>
        {save.status === "idle" && (
          <button
            type="button"
            disabled={disabled}
            onClick={() => setSave({ ...EMPTY, status: "discarded", message: "This plan was discarded." })}
            className="inline-flex min-h-11 items-center justify-center rounded-control border border-border-strong bg-surface px-4 text-small font-semibold text-text hover:bg-surface-muted disabled:cursor-not-allowed disabled:bg-surface-muted disabled:text-text-muted"
          >
            Discard
          </button>
        )}
      </div>
    </section>
  );
}

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL, fetchMe, fetchOptions, logoutAccount, MESSAGES, streamPlan } from "../api.js";
import { clearSession, getToken, SESSION_ENDED, SESSION_STORAGE_KEY, setSession } from "../auth.js";

const request = { destination: "Jaipur", days: 2, budget: 10000, interests: ["history"], style: "relaxed", start_date: null };

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function unauthorizedResponse() {
  return new Response(JSON.stringify({ detail: "Authentication required." }), {
    status: 401,
    headers: { "Content-Type": "application/json" },
  });
}

function expectSessionCleared() {
  expect(getToken()).toBeNull();
  expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
}

beforeEach(() => {
  clearSession("");
  sessionStorage.clear();
  localStorage.clear();
});

afterEach(() => {
  clearSession("");
  sessionStorage.clear();
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("session token", () => {
  it("keeps the token in session storage and drops it after a 401", async () => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const info = vi.spyOn(console, "info").mockImplementation(() => {});
    const debug = vi.spyOn(console, "debug").mockImplementation(() => {});
    setSession("secret-token");
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("secret-token");
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();

    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Authentication required." }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })));
    const result = await fetchMe();

    expect(result.sessionEnded).toBe(true);
    expect(result.message).toBe(SESSION_ENDED);
    expect(getToken()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer secret-token");
    for (const call of [...log.mock.calls, ...info.mock.calls, ...debug.mock.calls]) {
      expect(JSON.stringify(call)).not.toContain("secret-token");
    }
  });

  it("sends the session token as Authorization on a real planning stream", async () => {
    setSession("planner-token");
    const result = { draft: null, checks: [], revisions: 0, unresolved: [], demo: true };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      `event: result\ndata: ${JSON.stringify(result)}\n\n`,
      { headers: { "Content-Type": "text/event-stream" } },
    )));
    const onEvent = vi.fn();

    await expect(streamPlan(request, onEvent)).resolves.toMatchObject({ ok: true });
    expect(fetch).toHaveBeenCalledWith(`${API_URL}/plan`, expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({
        Authorization: "Bearer planner-token",
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      }),
      body: JSON.stringify(request),
    }));
    expect(onEvent).toHaveBeenCalledWith({ type: "result", data: result });
    expect(getToken()).toBe("planner-token");
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("planner-token");
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it("clears the session and reports a session-ended error when planning returns 401", async () => {
    setSession("rejected-plan-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(unauthorizedResponse()));
    const onEvent = vi.fn();

    await expect(streamPlan(request, onEvent)).resolves.toMatchObject({ ok: false, message: SESSION_ENDED });
    expect(fetch).toHaveBeenCalledWith(`${API_URL}/plan`, expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer rejected-plan-token" }),
    }));
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: "error", data: expect.objectContaining({ message: SESSION_ENDED }) });
    expectSessionCleared();
  });

  it("clears the session when fetching trip options returns 401", async () => {
    setSession("rejected-options-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(unauthorizedResponse()));

    await expect(fetchOptions()).resolves.toMatchObject({ ok: false, message: SESSION_ENDED });
    expect(fetch).toHaveBeenCalledWith(`${API_URL}/options`, expect.any(Object));
    expectSessionCleared();
  });

  it.each(["success", "network failure"])("clears the session after logout with %s", async (outcome) => {
    setSession("logout-token");
    const pending = deferred();
    vi.stubGlobal("fetch", vi.fn().mockReturnValueOnce(pending.promise));

    const loggingOut = logoutAccount();
    expect(fetch).toHaveBeenCalledWith(`${API_URL}/auth/logout`, expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({ Authorization: "Bearer logout-token" }),
    }));
    if (outcome === "network failure") {
      pending.reject(new TypeError("Failed to fetch"));
      await expect(loggingOut).resolves.toMatchObject({ ok: false, message: MESSAGES.unreachable });
    } else {
      pending.resolve(new Response(null, { status: 204 }));
      await expect(loggingOut).resolves.toMatchObject({ ok: true, status: 204 });
    }
    expectSessionCleared();
  });
});

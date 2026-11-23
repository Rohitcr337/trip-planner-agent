import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App.jsx";
import { fetchMe, fetchOptions, loginAccount, logoutAccount, registerAccount, streamPlan } from "../api.js";
import { clearSession, endSession, getToken, SESSION_ENDED, SESSION_STORAGE_KEY, setSession } from "../auth.js";

vi.mock("../api.js", () => ({
  fetchOptions: vi.fn(),
  streamPlan: vi.fn(),
  loginAccount: vi.fn(),
  registerAccount: vi.fn(),
  logoutAccount: vi.fn(),
  fetchMe: vi.fn(),
}));

const options = {
  cities: ["Jaipur"],
  destinations: [{ name: "Jaipur", lat: 26.9, lon: 75.8 }],
  styles: ["relaxed", "packed"],
  day_range: { min: 1, max: 7 },
  interest_suggestions: ["history"],
};

function dialog() {
  return screen.getByRole("dialog");
}

function deferred() {
  let resolve;
  const promise = new Promise((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

async function renderApp() {
  render(<App />);
  await screen.findByRole("combobox", { name: "Destination" });
}

beforeEach(() => {
  clearSession("");
  sessionStorage.clear();
  localStorage.clear();
  vi.resetAllMocks();
  fetchOptions.mockResolvedValue({ ok: true, options });
  logoutAccount.mockResolvedValue({ ok: true });
  fetchMe.mockResolvedValue({ ok: false, message: "" });
});

afterEach(() => {
  cleanup();
  clearSession("");
  sessionStorage.clear();
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("account dialog", () => {
  it("signs in, creates an account, and keeps errors from revealing whether an email exists", async () => {
    loginAccount.mockResolvedValueOnce({
      ok: false,
      status: 401,
      message: "No account for person@example.com",
    }).mockResolvedValueOnce({
      ok: false,
      status: 429,
      message: "Too many login attempts. Try again later.",
    });
    registerAccount.mockResolvedValueOnce({
      ok: false,
      status: 409,
      message: "person@example.com already exists",
    }).mockResolvedValueOnce({
      ok: true,
      data: { token: "kept-token", user: { id: 1, email: "person@example.com" } },
    });
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const info = vi.spyOn(console, "info").mockImplementation(() => {});
    const debug = vi.spyOn(console, "debug").mockImplementation(() => {});
    const localSet = vi.spyOn(Storage.prototype, "setItem");

    await renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    const signIn = dialog();
    expect(within(signIn).getByLabelText("Email")).toBeTruthy();
    expect(within(signIn).getByLabelText("Password")).toBeTruthy();
    expect(within(signIn).getByText("10 or more characters")).toBeTruthy();
    expect(within(signIn).getByLabelText("Password").getAttribute("type")).toBe("password");

    fireEvent.click(within(signIn).getByRole("button", { name: "Show password" }));
    expect(within(signIn).getByLabelText("Password").getAttribute("type")).toBe("text");
    fireEvent.click(within(signIn).getByRole("button", { name: "Hide password" }));

    fireEvent.change(within(signIn).getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(within(signIn).getByLabelText("Password"), { target: { value: "correct horse" } });
    fireEvent.click(within(signIn).getByRole("button", { name: "Sign in" }));
    expect((await within(signIn).findByRole("alert")).textContent).toBe("Incorrect email or password.");
    expect(within(signIn).getByRole("alert").textContent.toLowerCase()).not.toMatch(/exist|found|already/);

    fireEvent.click(within(signIn).getByRole("button", { name: "Sign in" }));
    expect((await within(signIn).findByRole("alert")).textContent).toBe("Too many attempts. Try again later.");

    fireEvent.click(within(signIn).getByRole("button", { name: "Create an account" }));
    fireEvent.click(within(dialog()).getByRole("button", { name: "Create account" }));
    expect((await within(dialog()).findByRole("alert")).textContent).toBe("Unable to register with those details.");
    expect(within(dialog()).getByRole("alert").textContent).not.toContain("person@example.com");

    fireEvent.click(within(dialog()).getByRole("button", { name: "Create account" }));
    expect(await screen.findByRole("button", { name: "person@example.com" })).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe("kept-token");
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(localSet.mock.calls.some((call) => call[0] === SESSION_STORAGE_KEY && localSet.mock.instances.some((storage) => storage === localStorage))).toBe(false);
    for (const call of [...log.mock.calls, ...info.mock.calls, ...debug.mock.calls]) {
      expect(JSON.stringify(call)).not.toContain("kept-token");
    }
    expect(streamPlan).not.toHaveBeenCalled();
  });

  it("traps focus and closes from the keyboard", async () => {
    await renderApp();
    const opener = screen.getByRole("button", { name: "Sign in" });
    act(() => opener.focus());
    fireEvent.click(opener);
    const signIn = dialog();
    const close = within(signIn).getByRole("button", { name: "Close" });
    act(() => close.focus());
    fireEvent.keyDown(signIn, { key: "Tab" });
    expect(document.activeElement).toBe(within(signIn).getByLabelText("Email"));
    fireEvent.keyDown(signIn, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(signIn, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it("focuses and navigates the account menu, then restores focus on Escape", async () => {
    setSession("kept-token");
    fetchMe.mockResolvedValue({ ok: true, data: { id: 1, email: "person@example.com" } });
    await renderApp();
    const account = await screen.findByRole("button", { name: "person@example.com" });
    act(() => account.focus());
    fireEvent.click(account);

    const menu = screen.getByRole("menu", { name: "Account" });
    const myTrips = within(menu).getByRole("menuitem", { name: "My trips" });
    const signOut = within(menu).getByRole("menuitem", { name: "Sign out" });
    expect(account.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(myTrips);
    fireEvent.keyDown(myTrips, { key: "ArrowDown" });
    expect(document.activeElement).toBe(signOut);
    fireEvent.keyDown(signOut, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(account.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(account);
    expect(logoutAccount).not.toHaveBeenCalled();
  });

  it.each([
    { mode: "sign in", request: loginAccount, submitLabel: "Sign in", pendingLabel: "Signing in..." },
    { mode: "create account", request: registerAccount, submitLabel: "Create account", pendingLabel: "Creating account..." },
  ])("ignores a successful $mode response after the dialog closes", async ({ mode, request, submitLabel, pendingLabel }) => {
    const pending = deferred();
    request.mockReturnValueOnce(pending.promise);
    await renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    if (mode === "create account") {
      fireEvent.click(within(dialog()).getByRole("button", { name: "Create an account" }));
    }
    fireEvent.change(within(dialog()).getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(within(dialog()).getByLabelText("Password"), { target: { value: "correct horse" } });
    fireEvent.click(within(dialog()).getByRole("button", { name: submitLabel }));
    expect(request).toHaveBeenCalledWith("person@example.com", "correct horse");
    expect(within(dialog()).getByRole("button", { name: pendingLabel }).disabled).toBe(true);

    fireEvent.click(within(dialog()).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    await act(async () => {
      pending.resolve({
        ok: true,
        data: { token: "late-token", user: { id: 1, email: "person@example.com" } },
      });
      await pending.promise;
    });

    expect(screen.getByRole("button", { name: "Sign in" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "person@example.com" })).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getToken()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(streamPlan).not.toHaveBeenCalled();
  });

  it("clears the token from storage on sign out", async () => {
    loginAccount.mockResolvedValue({
      ok: true,
      data: { token: "kept-token", user: { id: 1, email: "person@example.com" } },
    });
    await renderApp();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.change(within(dialog()).getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(within(dialog()).getByLabelText("Password"), { target: { value: "correct horse" } });
    fireEvent.click(within(dialog()).getByRole("button", { name: "Sign in" }));
    const account = await screen.findByRole("button", { name: "person@example.com" });
    fireEvent.click(account);
    expect(screen.getByRole("menuitem", { name: "My trips" })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    fireEvent.click(account);
    fireEvent.click(screen.getByRole("menuitem", { name: "Sign out" }));
    expect(await screen.findByRole("button", { name: "Sign in" })).toBeTruthy();
    expect(getToken()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(logoutAccount).toHaveBeenCalled();
  });

  it("shows the session ended message and clears a rejected token", async () => {
    setSession("stale-token");
    fetchMe.mockImplementation(async () => {
      endSession();
      return { ok: false, status: 401, sessionEnded: true, message: SESSION_ENDED };
    });
    await renderApp();
    const signIn = await screen.findByRole("dialog");
    expect(signIn.textContent).toContain(SESSION_ENDED);
    expect(getToken()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });
});

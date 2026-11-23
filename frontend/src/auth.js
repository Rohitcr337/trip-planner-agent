export const SESSION_STORAGE_KEY = "cairn.session";
export const SESSION_ENDED = "Your session ended. Please sign in again.";

let memoryToken;
const listeners = new Set();

function readStoredToken() {
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredToken(value) {
  try {
    if (value) sessionStorage.setItem(SESSION_STORAGE_KEY, value);
    else sessionStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // Keep the in-memory session when storage is blocked.
  }
}

function tokenValue() {
  if (memoryToken === undefined) memoryToken = readStoredToken();
  return memoryToken;
}

function emit(event) {
  for (const listener of listeners) listener(event);
}

export function getToken() {
  return tokenValue();
}

export function subscribeAuth(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function setSession(nextToken) {
  memoryToken = nextToken || null;
  writeStoredToken(memoryToken);
  emit({ type: "session" });
}

export function clearSession(message = "") {
  const hadToken = Boolean(tokenValue());
  memoryToken = null;
  writeStoredToken(null);
  emit({ type: "cleared", message: hadToken ? message : "" });
}

export function endSession() {
  if (!tokenValue()) return false;
  clearSession(SESSION_ENDED);
  return true;
}

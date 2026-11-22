export const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

export const MESSAGES = {
  dailyLimit: "Daily limit reached. The planner has used today's allowance; please try again tomorrow.",
  dropped: "The connection dropped before the plan finished. Please retry.",
  unreachable: `Could not reach the planner at ${API_URL}. Check that the backend is running, then retry.`,
  badResponse: "The planner sent a response that could not be read. Please retry.",
  optionsFailed: "Trip options could not be loaded. Please retry.",
};

const PLAN_EVENTS = new Set(["step", "result", "error"]);

function isAbort(error) {
  return error?.name === "AbortError";
}

function statusMessage(status, body) {
  if (status === 429) return MESSAGES.dailyLimit;
  if (status === 422 && Array.isArray(body?.detail)) {
    const details = body.detail.map((item) => item?.msg).filter(Boolean);
    if (details.length) return `Some trip details were not accepted: ${details.join("; ")}.`;
  }
  if (typeof body?.detail === "string" && body.detail) return body.detail;
  return `The planner is unavailable right now (HTTP ${status}). Please retry.`;
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function validOptions(data) {
  return (
    data &&
    Array.isArray(data.destinations) &&
    data.destinations.every((item) => typeof item?.name === "string" && item.name) &&
    Array.isArray(data.styles) &&
    Array.isArray(data.interest_suggestions) &&
    Number.isInteger(data.day_range?.min) &&
    Number.isInteger(data.day_range?.max)
  );
}

export async function fetchOptions({ signal } = {}) {
  try {
    const response = await fetch(`${API_URL}/options`, { signal });
    const data = await readJson(response);
    if (!response.ok) return { ok: false, message: statusMessage(response.status, data) };
    if (!validOptions(data)) return { ok: false, message: MESSAGES.optionsFailed };
    return { ok: true, options: data };
  } catch (error) {
    if (isAbort(error)) return { ok: false, aborted: true, message: "" };
    return { ok: false, message: MESSAGES.unreachable };
  }
}

function parseBlock(block) {
  let event = "message";
  const data = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { event, data: data.join("\n") } : null;
}

export function createEventParser() {
  let buffer = "";
  let pendingCR = false;
  return {
    push(chunk) {
      if (pendingCR && chunk.startsWith("\n")) chunk = chunk.slice(1);
      pendingCR = chunk.endsWith("\r");
      buffer += chunk.replace(/\r\n?/g, "\n");
      const events = [];
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const parsed = parseBlock(buffer.slice(0, boundary));
        if (parsed) events.push(parsed);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");
      }
      return events;
    },
  };
}

function safeDeliver(onEvent, event) {
  try {
    onEvent(event);
  } catch (error) {
    console.error("Plan event handler failed", error);
  }
}

export async function streamPlan(request, onEvent, { signal } = {}) {
  const fail = (message) => {
    safeDeliver(onEvent, { type: "error", data: { message } });
    return { ok: false, message };
  };

  let response;
  try {
    response = await fetch(`${API_URL}/plan`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (error) {
    if (isAbort(error)) return { ok: false, aborted: true };
    return fail(MESSAGES.unreachable);
  }

  if (!response.ok) return fail(statusMessage(response.status, await readJson(response)));
  if (!response.body) return fail(MESSAGES.badResponse);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = createEventParser();
  let finished = false;
  let gotResult = false;

  const handle = (raw) => {
    if (!PLAN_EVENTS.has(raw.event)) return;
    let data;
    try {
      data = JSON.parse(raw.data);
    } catch {
      finished = true;
      fail(MESSAGES.badResponse);
      return;
    }
    if (raw.event === "error") {
      finished = true;
      const message = typeof data?.message === "string" && data.message ? data.message : MESSAGES.dropped;
      safeDeliver(onEvent, { type: "error", data: { ...data, message } });
      return;
    }
    if (raw.event === "result") {
      finished = true;
      gotResult = true;
    }
    safeDeliver(onEvent, { type: raw.event, data });
  };

  try {
    while (!finished) {
      const { value, done } = await reader.read();
      if (done) {
        for (const raw of parser.push(decoder.decode())) if (!finished) handle(raw);
        break;
      }
      for (const raw of parser.push(decoder.decode(value, { stream: true }))) {
        if (finished) break;
        handle(raw);
      }
    }
  } catch (error) {
    if (isAbort(error)) return { ok: false, aborted: true };
    if (!finished) return fail(MESSAGES.dropped);
  } finally {
    if (finished) reader.cancel().catch(() => {});
  }

  if (!finished) return fail(MESSAGES.dropped);
  return { ok: gotResult };
}

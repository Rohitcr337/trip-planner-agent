// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { API_URL, createEventParser, fetchOptions, MESSAGES, streamPlan } from "../api.js";

const request = { destination: "Jaipur", days: 2, budget: 10000, interests: ["history"], style: "relaxed", start_date: null };
const options = { cities: ["Jaipur", "Chennai", "Goa"], destinations: [{ name: "Jaipur", lat: 26.9, lon: 75.8 }, { name: "Chennai", lat: 13.1, lon: 80.3 }, { name: "Goa", lat: 15.5, lon: 73.8 }], styles: ["relaxed", "packed"], day_range: { min: 1, max: 7 }, interest_suggestions: ["history", "food"] };
const step = { name: "intake", message: "Trip details validated.", elapsed_seconds: 0.2 };
const result = { draft: null, checks: [], revisions: 0, unresolved: [], costs_are_estimates: true, demo: true };

function responseFromChunks(chunks) {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === "string" ? encoder.encode(chunk) : chunk);
      controller.close();
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
}

function mockFetch(response) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));
}

afterEach(() => vi.unstubAllGlobals());

describe("SSE parser", () => {
  it("keeps an event split across chunks until its blank line", () => {
    const parser = createEventParser();
    expect(parser.push('event: step\ndata: {"name":"in')).toEqual([]);
    expect(parser.push('take"}\n')).toEqual([]);
    expect(parser.push("\n")).toEqual([{ event: "step", data: '{"name":"intake"}' }]);
  });

  it("handles comments, multiple data lines and CRLF split between chunks", () => {
    const parser = createEventParser();
    expect(parser.push(': ping\r\nevent: step\r')).toEqual([]);
    expect(parser.push('\ndata: {\r\ndata: "name": "intake"\r\ndata: }\r')).toEqual([]);
    expect(parser.push("\n\r\n")).toEqual([{ event: "step", data: '{\n"name": "intake"\n}' }]);
  });
});

describe("streamPlan", () => {
  it("POSTs the real request shape and reads step and result events", async () => {
    const body = `event: step\ndata: ${JSON.stringify(step)}\n\nevent: result\ndata: ${JSON.stringify(result)}\n\n`;
    mockFetch(responseFromChunks([body.slice(0, 40), body.slice(40, 100), body.slice(100)]));
    const onEvent = vi.fn();
    await expect(streamPlan(request, onEvent)).resolves.toEqual({ ok: true });
    expect(fetch).toHaveBeenCalledWith(`${API_URL}/plan`, expect.objectContaining({ method: "POST", body: JSON.stringify(request) }));
    expect(onEvent.mock.calls.map(([event]) => event)).toEqual([{ type: "step", data: step }, { type: "result", data: result }]);
  });

  it("keeps split multi-byte text intact", async () => {
    const data = { ...step, message: "Café passages retrieved." };
    const bytes = new TextEncoder().encode(`event: step\ndata: ${JSON.stringify(data)}\n\nevent: result\ndata: ${JSON.stringify(result)}\n\n`);
    const splitAt = bytes.indexOf(0xc3) + 1;
    mockFetch(responseFromChunks([bytes.slice(0, splitAt), bytes.slice(splitAt)]));
    const onEvent = vi.fn();
    await streamPlan(request, onEvent);
    expect(onEvent).toHaveBeenCalledWith({ type: "step", data });
  });

  it("reports a friendly daily limit message for HTTP 429", async () => {
    mockFetch(new Response(JSON.stringify({ detail: "Daily model call limit reached. Try again tomorrow." }), { status: 429 }));
    const onEvent = vi.fn();
    await streamPlan(request, onEvent);
    expect(onEvent).toHaveBeenCalledWith({ type: "error", data: { message: MESSAGES.dailyLimit } });
    expect(MESSAGES.dailyLimit).toMatch(/daily limit reached/i);
  });

  it("reports a stream ending without a final result", async () => {
    mockFetch(responseFromChunks([`event: step\ndata: ${JSON.stringify(step)}\n\n`]));
    const onEvent = vi.fn();
    await expect(streamPlan(request, onEvent)).resolves.toMatchObject({ ok: false });
    expect(onEvent).toHaveBeenLastCalledWith({ type: "error", data: { message: MESSAGES.dropped } });
  });

  it("reports a broken reader without rejecting", async () => {
    mockFetch(new Response(new ReadableStream({ start(controller) { controller.error(new Error("closed")); } })));
    const onEvent = vi.fn();
    await expect(streamPlan(request, onEvent)).resolves.toMatchObject({ ok: false });
    expect(onEvent).toHaveBeenCalledWith({ type: "error", data: { message: MESSAGES.dropped } });
  });

  it("reports an error event and does not add a dropped-connection message", async () => {
    mockFetch(responseFromChunks(['event: error\ndata: {"message":"Planning failed. Please retry."}\n\n']));
    const onEvent = vi.fn();
    await expect(streamPlan(request, onEvent)).resolves.toEqual({ ok: false });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: "error", data: { message: "Planning failed. Please retry." } });
  });

  it("reports malformed JSON instead of throwing", async () => {
    mockFetch(responseFromChunks(['event: result\ndata: {broken}\n\n']));
    const onEvent = vi.fn();
    await expect(streamPlan(request, onEvent)).resolves.toMatchObject({ ok: false });
    expect(onEvent).toHaveBeenCalledWith({ type: "error", data: { message: MESSAGES.badResponse } });
  });

  it("reports validation errors and other HTTP failures", async () => {
    mockFetch(new Response(JSON.stringify({ detail: [{ msg: "days must be <= 7" }] }), { status: 422 }));
    const onEvent = vi.fn();
    await streamPlan(request, onEvent);
    expect(onEvent.mock.calls[0][0].data.message).toContain("days must be <= 7");
    mockFetch(new Response("unavailable", { status: 503 }));
    await streamPlan(request, onEvent);
    expect(onEvent.mock.calls[1][0].data.message).toContain("HTTP 503");
  });

  it("handles a network failure and silently handles cancellation", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const onEvent = vi.fn();
    await expect(streamPlan(request, onEvent)).resolves.toMatchObject({ ok: false });
    expect(onEvent).toHaveBeenCalledWith({ type: "error", data: { message: MESSAGES.unreachable } });
    fetch.mockRejectedValue(new DOMException("Aborted", "AbortError"));
    onEvent.mockClear();
    await expect(streamPlan(request, onEvent)).resolves.toEqual({ ok: false, aborted: true });
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("does not reject if a consumer's event handler throws", async () => {
    mockFetch(responseFromChunks([`event: result\ndata: ${JSON.stringify(result)}\n\n`]));
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    await expect(streamPlan(request, () => { throw new Error("consumer"); })).resolves.toEqual({ ok: true });
    spy.mockRestore();
  });
});

describe("fetchOptions", () => {
  it("loads the backend option fields", async () => {
    mockFetch(new Response(JSON.stringify(options)));
    await expect(fetchOptions()).resolves.toEqual({ ok: true, options });
    expect(fetch).toHaveBeenCalledWith(`${API_URL}/options`, { signal: undefined });
  });

  it("returns an error for invalid options and never rejects on a network failure", async () => {
    mockFetch(new Response("{}"));
    await expect(fetchOptions()).resolves.toEqual({ ok: false, message: MESSAGES.optionsFailed });
    mockFetch(new Response(JSON.stringify({ ...options, destinations: [{ lat: 1, lon: 2 }] })));
    await expect(fetchOptions()).resolves.toEqual({ ok: false, message: MESSAGES.optionsFailed });
    fetch.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(fetchOptions()).resolves.toEqual({ ok: false, message: MESSAGES.unreachable });
  });
});

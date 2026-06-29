import { describe, it, expect, vi, afterEach } from "vitest";
import { fetchEvents } from "../src/api";

afterEach(() => vi.restoreAllMocks());

describe("fetchEvents", () => {
  it("calls the events endpoint with bearer token and returns json", async () => {
    const json = { deviceId: "raspi-01", count: 1, events: [{ ts: "t1" }] };
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => json });
    const out = await fetchEvents("https://api.example", "TOKEN", "raspi-01", 10);
    expect(out).toEqual(json);
    const [url, opts] = global.fetch.mock.calls[0];
    expect(url).toContain("/events?deviceId=raspi-01&limit=10");
    expect(opts.headers.Authorization).toBe("Bearer TOKEN");
  });

  it("throws on non-ok response", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    await expect(fetchEvents("https://api.example", "T")).rejects.toThrow("401");
  });
});

import { describe, it, expect } from "vitest";
import { toSeries } from "../src/series";

describe("toSeries", () => {
  it("sorts oldest-first and maps features", () => {
    const events = [
      { ts: "2026-06-29T12:05:00Z", features: { mag_peak: 3.2, mag_rms: 1.0, tilt_deg: 45 }, label: "impact", severity: "high" },
      { ts: "2026-06-29T12:00:00Z", features: { mag_peak: 1.0, mag_rms: 0.0, tilt_deg: 0 }, label: "normal", severity: "low" },
    ];
    const s = toSeries(events);
    expect(s.map((x) => x.ts)).toEqual(["2026-06-29T12:00:00Z", "2026-06-29T12:05:00Z"]);
    expect(s[1].mag_peak).toBe(3.2);
    expect(s[0].label).toBe("normal");
  });

  it("handles missing features", () => {
    const s = toSeries([{ ts: "t1", label: "x", severity: "low" }]);
    expect(s[0].mag_peak).toBeNull();
  });

  it("does not mutate the input array", () => {
    const events = [{ ts: "b" }, { ts: "a" }];
    toSeries(events);
    expect(events.map((e) => e.ts)).toEqual(["b", "a"]);
  });
});

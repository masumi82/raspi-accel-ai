export function toSeries(events) {
  return [...events]
    .sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
    .map((e) => ({
      ts: e.ts,
      mag_peak: e.features?.mag_peak ?? null,
      mag_rms: e.features?.mag_rms ?? null,
      tilt_deg: e.features?.tilt_deg ?? null,
      label: e.label,
      severity: e.severity,
    }));
}

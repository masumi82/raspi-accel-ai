const SEV_COLOR = { low: "#2e7d32", medium: "#ed6c02", high: "#d32f2f" };

export default function EventsTable({ events }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 16 }}>
      <thead>
        <tr>
          <th style={{ textAlign: "left" }}>時刻</th>
          <th style={{ textAlign: "left" }}>種別</th>
          <th style={{ textAlign: "left" }}>深刻度</th>
          <th style={{ textAlign: "left" }}>説明</th>
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.ts} style={{ borderTop: "1px solid #ddd" }}>
            <td>{e.ts}</td>
            <td>{e.label}</td>
            <td style={{ color: SEV_COLOR[e.severity] || "#333" }}>{e.severity}</td>
            <td>{e.explanation}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

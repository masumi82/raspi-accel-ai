import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts";

export default function EventsChart({ series }) {
  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <LineChart data={series}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="ts" hide />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="mag_peak" stroke="#8884d8" dot={false} />
          <Line type="monotone" dataKey="mag_rms" stroke="#82ca9d" dot={false} />
          <Line type="monotone" dataKey="tilt_deg" stroke="#ffc658" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

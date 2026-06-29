import { useEffect, useState } from "react";
import { config } from "../config";
import { fetchEvents } from "../api";
import { toSeries } from "../series";
import EventsChart from "./EventsChart";
import EventsTable from "./EventsTable";

export default function EventsView({ token }) {
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    fetchEvents(config.apiUrl, token, config.deviceId, 100)
      .then((d) => active && setEvents(d.events || []))
      .catch((e) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  if (loading) return <p>読み込み中…</p>;
  if (error) return <p>取得エラー: {error}</p>;
  if (events.length === 0) return <p>イベントがありません。</p>;

  return (
    <section>
      <EventsChart series={toSeries(events)} />
      <EventsTable events={events} />
    </section>
  );
}

export async function fetchEvents(apiUrl, token, deviceId = "raspi-01", limit = 50) {
  const url = `${apiUrl}/events?deviceId=${encodeURIComponent(deviceId)}&limit=${limit}`;
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }
  return res.json();
}

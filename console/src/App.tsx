import { useEffect, useState } from "react";

import { fetchPoints, writeAhu1Setpoint, type Point } from "./api";

const POLL_INTERVAL_MS = 2500;

const STATUS_STYLE: Record<Point["status"], { bg: string; fg: string; label: string }> = {
  ok: { bg: "#163327", fg: "#4caf7d", label: "OK" },
  fault: { bg: "#3a1a1a", fg: "#e0655f", label: "FAULT" },
  stale: { bg: "#332c16", fg: "#e8a33d", label: "STALE" },
};

function formatValue(point: Point): string {
  if (point.value === null) return "—";
  if (typeof point.value === "number") return point.value.toLocaleString();
  return point.value;
}

export default function App() {
  const [points, setPoints] = useState<Point[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [setpointInput, setSetpointInput] = useState("22.0");
  const [writing, setWriting] = useState(false);
  const [writeMessage, setWriteMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const next = await fetchPoints();
        if (cancelled) return;
        setPoints(next);
        setError(null);
        setLastUpdated(new Date());
      } catch {
        if (cancelled) return;
        setError("Can't reach the gateway at " + (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"));
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const okCount = points.filter((p) => p.status === "ok").length;
  const faultCount = points.filter((p) => p.status === "fault").length;

  async function handleWriteSetpoint(e: React.FormEvent) {
    e.preventDefault();
    const value = Number.parseFloat(setpointInput);
    if (Number.isNaN(value)) return;
    setWriting(true);
    setWriteMessage(null);
    try {
      await writeAhu1Setpoint(value);
      setWriteMessage(`Wrote ${value} °C`);
    } catch {
      setWriteMessage("Write failed");
    } finally {
      setWriting(false);
    }
  }

  return (
    <div className="shell">
      <header className="top">
        <div>
          <span className="eyebrow">BuildingOps Lab</span>
          <h1>Live Points</h1>
        </div>
        <div className="summary">
          <span className="count ok">{okCount} ok</span>
          {faultCount > 0 && <span className="count fault">{faultCount} fault</span>}
          <span className="updated">
            {lastUpdated ? `updated ${lastUpdated.toLocaleTimeString()}` : "connecting…"}
          </span>
        </div>
      </header>

      {error && <div className="banner">{error}</div>}

      <table>
        <thead>
          <tr>
            <th>Device</th>
            <th>Point</th>
            <th>Value</th>
            <th>Units</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {points.length === 0 && !error && (
            <tr>
              <td colSpan={5} className="empty">
                waiting for first poll…
              </td>
            </tr>
          )}
          {[...points]
            .sort((a, b) => a.id.localeCompare(b.id))
            .map((point) => {
              const style = STATUS_STYLE[point.status];
              return (
                <tr key={point.id}>
                  <td className="mono muted">{point.device}</td>
                  <td>{point.name}</td>
                  <td className="mono value">{formatValue(point)}</td>
                  <td className="muted">{point.units ?? "—"}</td>
                  <td>
                    <span className="chip" style={{ background: style.bg, color: style.fg }}>
                      {style.label}
                    </span>
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>

      <form className="setpoint-form" onSubmit={handleWriteSetpoint}>
        <label htmlFor="setpoint">AHU-1 SAT setpoint (°C)</label>
        <input
          id="setpoint"
          type="number"
          step="0.5"
          value={setpointInput}
          onChange={(e) => setSetpointInput(e.target.value)}
        />
        <button type="submit" disabled={writing}>
          {writing ? "Writing…" : "Write to BACnet"}
        </button>
        {writeMessage && <span className="write-message">{writeMessage}</span>}
      </form>
    </div>
  );
}

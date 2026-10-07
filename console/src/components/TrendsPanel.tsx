import { useEffect, useState } from 'react';

import LineChart from '@/components/LineChart';
import { fetchHistory, fetchPoints, type HistorySample, type Point } from '@/lib/api';

const POLL_INTERVAL_MS = 3000;
const RANGE_OPTIONS = [
    { label: '15 min', minutes: 15 },
    { label: '1 hour', minutes: 60 },
    { label: '3 hours', minutes: 180 },
    { label: '24 hours', minutes: 1440 }
];

export default function TrendsPanel() {
    const [points, setPoints] = useState<Point[]>([]);
    const [pointId, setPointId] = useState<string | null>(null);
    const [minutes, setMinutes] = useState(60);
    const [samples, setSamples] = useState<HistorySample[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchPoints()
            .then((all) => {
                const numeric = all.filter((p) => typeof p.value === 'number');
                setPoints(numeric);
                setPointId((current) => current ?? numeric[0]?.id ?? null);
            })
            .catch(() => setError("Can't reach the gateway"));
    }, []);

    useEffect(() => {
        if (!pointId) return;
        let cancelled = false;
        async function poll() {
            try {
                const next = await fetchHistory(pointId as string, minutes);
                if (!cancelled) {
                    setSamples(next);
                    setError(null);
                }
            } catch {
                if (!cancelled) setError(`Can't load history for ${pointId}`);
            }
        }
        poll();
        const id = setInterval(poll, POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, [pointId, minutes]);

    const selected = points.find((p) => p.id === pointId);

    return (
        <div className="panel-section">
            <h2>Trends</h2>
            <div className="setpoint-form">
                <label htmlFor="trend-point">Point</label>
                <select
                    id="trend-point"
                    value={pointId ?? ''}
                    onChange={(e) => setPointId(e.target.value)}
                >
                    {points.map((p) => (
                        <option key={p.id} value={p.id}>
                            {p.device} · {p.name}
                        </option>
                    ))}
                </select>
                <label htmlFor="trend-range">Range</label>
                <select
                    id="trend-range"
                    value={minutes}
                    onChange={(e) => setMinutes(Number(e.target.value))}
                >
                    {RANGE_OPTIONS.map((r) => (
                        <option key={r.minutes} value={r.minutes}>
                            {r.label}
                        </option>
                    ))}
                </select>
            </div>

            {error && <div className="banner">{error}</div>}

            <div className="trend-chart-wrap">
                <LineChart samples={samples} units={selected?.units ?? null} />
            </div>

            <p className="muted" style={{ fontSize: '.8rem' }}>
                One point, one range, read straight from the supervisor's SQLite trend table (
                <code>GET /history/&#123;point_id&#125;</code>) — see{' '}
                <code>docs/alarm-engine-notes.md</code>.
            </p>
        </div>
    );
}

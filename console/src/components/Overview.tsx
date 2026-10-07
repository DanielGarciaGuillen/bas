import { useEffect, useState } from 'react';

import { fetchAlarms, fetchPoints, type Alarm, type Point } from '@/lib/api';
import { pointById } from '@/lib/points';

const POLL_INTERVAL_MS = 2500;

const CONDITION_TONE: Record<string, 'ok' | 'fault'> = {
    NORMAL: 'ok',
    ALARM: 'fault',
    TROUBLE: 'fault',
    SUPERVISORY: 'fault'
};

export default function Overview() {
    const [points, setPoints] = useState<Point[]>([]);
    const [alarms, setAlarms] = useState<Alarm[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function poll() {
            try {
                const [nextPoints, nextAlarms] = await Promise.all([fetchPoints(), fetchAlarms()]);
                if (!cancelled) {
                    setPoints(nextPoints);
                    setAlarms(nextAlarms);
                    setError(null);
                }
            } catch {
                if (!cancelled) setError("Can't reach the gateway");
            }
        }
        poll();
        const id = setInterval(poll, POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

    const occupancy = pointById(points, 'ahu-1.occupancy_mode')?.value ?? '—';
    const kw = pointById(points, 'meter-1.kw')?.value ?? '—';
    const fireCondition = String(pointById(points, 'fire-panel.condition')?.value ?? 'NORMAL');
    const doors = points.filter(
        (p) => p.device === 'access-control' && p.id !== 'access-control.last_event'
    );
    const activeAlarms = alarms.filter((a) => a.state !== 'cleared');
    const topPriority =
        activeAlarms.length > 0 ? Math.min(...activeAlarms.map((a) => a.priority)) : null;

    return (
        <div>
            {error && <div className="banner">{error}</div>}
            <div className="overview-grid">
                <div className="overview-tile">
                    <span className="overview-label">Occupancy Mode</span>
                    <span className="overview-value">{occupancy}</span>
                </div>
                <div className="overview-tile">
                    <span className="overview-label">Energy Now</span>
                    <span className="overview-value">
                        {kw} <span className="overview-units">kW</span>
                    </span>
                </div>
                <div className="overview-tile">
                    <span className="overview-label">Active Alarms</span>
                    <span
                        className="overview-value"
                        style={{ color: activeAlarms.length > 0 ? 'var(--fault)' : 'var(--ok)' }}
                    >
                        {activeAlarms.length}
                        {topPriority !== null && (
                            <span className="overview-units"> (top P{topPriority})</span>
                        )}
                    </span>
                </div>
                <div className="overview-tile">
                    <span className="overview-label">Fire Panel</span>
                    <span
                        className="chip"
                        style={{
                            background:
                                CONDITION_TONE[fireCondition] === 'fault'
                                    ? 'var(--fault-soft)'
                                    : 'var(--ok-soft)',
                            color:
                                CONDITION_TONE[fireCondition] === 'fault'
                                    ? 'var(--fault)'
                                    : 'var(--ok)'
                        }}
                    >
                        {fireCondition}
                    </span>
                </div>
            </div>

            <div className="panel-section">
                <h2>Doors</h2>
                <div className="overview-grid">
                    {doors.map((door) => (
                        <div className="overview-tile" key={door.id}>
                            <span className="overview-label">{door.name}</span>
                            <span
                                className="chip"
                                style={{
                                    background:
                                        door.value === 'NORMAL'
                                            ? 'var(--ok-soft)'
                                            : 'var(--fault-soft)',
                                    color: door.value === 'NORMAL' ? 'var(--ok)' : 'var(--fault)'
                                }}
                            >
                                {String(door.value)}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            <p className="muted" style={{ fontSize: '.8rem', marginTop: '1.25rem' }}>
                No VAV zones were built (a deliberate M2 simplification — see{' '}
                <code>docs/engineering-notes.md</code>), so there's no per-zone floor plan here.
                This status board surfaces the same building-level signals a real overview screen
                leads with: occupancy, energy, and anything that needs attention.
            </p>
        </div>
    );
}

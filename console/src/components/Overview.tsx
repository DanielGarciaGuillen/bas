import { fetchAlarms, fetchPoints, type Alarm, type Point } from '@/lib/api';
import { pointById, toneStyle, type Tone } from '@/lib/points';
import { usePolledResource } from '@/lib/usePolledResource';

const POLL_INTERVAL_MS = 2500;

interface OverviewData {
    points: Point[];
    alarms: Alarm[];
}

async function fetchOverview(): Promise<OverviewData> {
    const [points, alarms] = await Promise.all([fetchPoints(), fetchAlarms()]);
    return { points, alarms };
}

// Record<string, …> (not the fire panel's own condition union, which isn't exported as a
// type) is still unguarded in principle, but toneStyle()'s own 'neutral' fallback is the
// actual safety net — an unrecognized condition string now renders a neutral chip instead
// of throwing.
const CONDITION_TONE: Record<string, Tone> = {
    NORMAL: 'ok',
    ALARM: 'fault',
    TROUBLE: 'fault',
    SUPERVISORY: 'fault'
};

export default function Overview() {
    const { data, error } = usePolledResource<OverviewData>(
        fetchOverview,
        { points: [], alarms: [] },
        { intervalMs: POLL_INTERVAL_MS, errorMessage: "Can't reach the gateway" }
    );
    const { points, alarms } = data;

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
                            background: toneStyle(CONDITION_TONE[fireCondition]).bg,
                            color: toneStyle(CONDITION_TONE[fireCondition]).fg
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

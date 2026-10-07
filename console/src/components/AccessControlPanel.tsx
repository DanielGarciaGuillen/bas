import { useEffect, useState } from 'react';

import AccessControlControls from '@/components/AccessControlControls';
import {
    fetchAccessControlState,
    fetchAccessEvents,
    type AccessControlState,
    type AccessEvent
} from '@/lib/api';

const POLL_INTERVAL_MS = 2500;

const DOOR_STYLE: Record<string, { bg: string; fg: string }> = {
    normal: { bg: 'var(--ok-soft)', fg: 'var(--ok)' },
    forced: { bg: 'var(--fault-soft)', fg: 'var(--fault)' },
    held_open: { bg: 'var(--fault-soft)', fg: 'var(--fault)' }
};

const RESULT_STYLE: Record<string, { bg: string; fg: string }> = {
    granted: { bg: 'var(--ok-soft)', fg: 'var(--ok)' },
    denied_level: { bg: 'var(--fault-soft)', fg: 'var(--fault)' },
    denied_schedule: { bg: 'var(--fault-soft)', fg: 'var(--fault)' },
    forced: { bg: 'var(--fault-soft)', fg: 'var(--fault)' },
    held_open: { bg: 'var(--fault-soft)', fg: 'var(--fault)' }
};

function formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString();
}

export default function AccessControlPanel() {
    const [state, setState] = useState<AccessControlState | null>(null);
    const [events, setEvents] = useState<AccessEvent[]>([]);

    useEffect(() => {
        let cancelled = false;
        async function poll() {
            try {
                const [nextState, nextEvents] = await Promise.all([
                    fetchAccessControlState(),
                    fetchAccessEvents(15)
                ]);
                if (!cancelled) {
                    setState(nextState);
                    setEvents(nextEvents);
                }
            } catch {
                // panel stays on its last known state; no dedicated error banner here
            }
        }
        poll();
        const id = setInterval(poll, POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

    return (
        <div className="panel-section">
            <h2>Doors</h2>
            <div className="overview-grid">
                {(state?.doors ?? []).map((door) => {
                    const style = DOOR_STYLE[door.state];
                    return (
                        <div className="overview-tile" key={door.id}>
                            <span className="overview-label">{door.name}</span>
                            <span
                                className="chip"
                                style={{
                                    background: style.bg,
                                    color: style.fg,
                                    width: 'fit-content'
                                }}
                            >
                                {door.state.toUpperCase()}
                            </span>
                        </div>
                    );
                })}
            </div>

            <AccessControlControls />

            <h2 style={{ marginTop: '1.5rem' }}>Event Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Door</th>
                        <th>Result</th>
                        <th>Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {events.length === 0 && (
                        <tr>
                            <td colSpan={4} className="empty">
                                no events yet
                            </td>
                        </tr>
                    )}
                    {events.map((e, i) => {
                        const style = RESULT_STYLE[e.result];
                        const door = state?.doors.find((d) => d.id === e.door_id);
                        return (
                            <tr key={i}>
                                <td className="mono muted">{formatTime(e.timestamp)}</td>
                                <td>{door?.name ?? `Door ${e.door_id}`}</td>
                                <td>
                                    <span
                                        className="chip"
                                        style={{ background: style.bg, color: style.fg }}
                                    >
                                        {e.result}
                                    </span>
                                </td>
                                <td className="muted">{e.reason}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>

            <h2 style={{ marginTop: '1.5rem' }}>Cardholders</h2>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Access Level</th>
                        <th>Schedule</th>
                    </tr>
                </thead>
                <tbody>
                    {(state?.cardholders ?? []).map((c) => (
                        <tr key={c.id}>
                            <td>{c.name}</td>
                            <td className="mono">{c.access_level}</td>
                            <td className="muted">{c.schedule}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

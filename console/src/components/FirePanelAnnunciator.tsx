import { useEffect, useState } from 'react';

import FirePanelControls from '@/components/FirePanelControls';
import {
    acknowledgeFirePanel,
    fetchFirePanel,
    fetchFirePanelEvents,
    silenceFirePanel,
    resetFirePanel,
    type FirePanelEvent,
    type FirePanelState
} from '@/lib/api';

const POLL_INTERVAL_MS = 2500;

const CONDITION_STYLE: Record<FirePanelState['condition'], { bg: string; fg: string }> = {
    normal: { bg: 'var(--ok-soft)', fg: 'var(--ok)' },
    alarm: { bg: 'var(--fault-soft)', fg: 'var(--fault)' },
    trouble: { bg: 'var(--accent-soft)', fg: 'var(--accent)' },
    supervisory: { bg: 'var(--info-soft)', fg: 'var(--info)' }
};

function formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString();
}

export default function FirePanelAnnunciator() {
    const [panel, setPanel] = useState<FirePanelState | null>(null);
    const [events, setEvents] = useState<FirePanelEvent[]>([]);
    const [interlockActive, setInterlockActive] = useState(false);
    const [busy, setBusy] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function poll() {
            try {
                const [nextPanel, nextEvents] = await Promise.all([
                    fetchFirePanel(),
                    fetchFirePanelEvents(10)
                ]);
                if (cancelled) return;
                setPanel(nextPanel);
                setEvents(nextEvents);
                setInterlockActive(nextPanel.any_alarm);
            } catch {
                // handled below via the null-panel branch
            }
        }
        poll();
        const id = setInterval(poll, POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

    async function run(action: string, fn: () => Promise<void>) {
        setBusy(action);
        setMessage(null);
        try {
            await fn();
        } catch (err) {
            setMessage(err instanceof Error ? err.message : `${action} failed`);
        } finally {
            setBusy(null);
        }
    }

    if (!panel) {
        return (
            <div className="panel-section">
                <h2>Fire Panel</h2>
                <p className="muted">Connecting…</p>
            </div>
        );
    }

    const style = CONDITION_STYLE[panel.condition];

    return (
        <div className="panel-section">
            <h2>Fire Panel</h2>
            <div className="overview-grid" style={{ marginBottom: '1rem' }}>
                <div className="overview-tile">
                    <span className="overview-label">Panel Condition</span>
                    <span
                        className="chip"
                        style={{ background: style.bg, color: style.fg, width: 'fit-content' }}
                    >
                        {panel.condition.toUpperCase()}
                    </span>
                </div>
                <div className="overview-tile">
                    <span className="overview-label">Acknowledged</span>
                    <span className="overview-value">{panel.acknowledged ? 'Yes' : 'No'}</span>
                </div>
                <div className="overview-tile">
                    <span className="overview-label">Silenced</span>
                    <span className="overview-value">{panel.silenced ? 'Yes' : 'No'}</span>
                </div>
                <div className="overview-tile">
                    <span className="overview-label">AHU-1 Interlock</span>
                    <span
                        className="chip"
                        style={{
                            background: interlockActive ? 'var(--fault-soft)' : 'var(--ok-soft)',
                            color: interlockActive ? 'var(--fault)' : 'var(--ok)',
                            width: 'fit-content'
                        }}
                    >
                        {interlockActive ? 'FAN/DAMPER FORCED OFF' : 'inactive'}
                    </span>
                </div>
            </div>

            <div className="annunciator-zones">
                {panel.zones.map((zone) => {
                    const zoneStyle = CONDITION_STYLE[zone.condition];
                    return (
                        <div className="zone-led" key={zone.id}>
                            <span
                                className={
                                    zone.condition !== 'normal' ? 'led-dot led-pulse' : 'led-dot'
                                }
                                style={{ background: zoneStyle.fg }}
                            />
                            <div>
                                <div className="zone-led-name">{zone.name}</div>
                                <div className="zone-led-state" style={{ color: zoneStyle.fg }}>
                                    {zone.condition.toUpperCase()}
                                    {!zone.field_cleared &&
                                        zone.condition !== 'normal' &&
                                        ' · field active'}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="setpoint-form">
                <button
                    type="button"
                    disabled={busy !== null || panel.acknowledged}
                    onClick={() => run('Acknowledge', acknowledgeFirePanel)}
                >
                    {busy === 'Acknowledge' ? 'Acknowledging…' : 'Acknowledge'}
                </button>
                <button
                    type="button"
                    disabled={busy !== null || panel.silenced}
                    onClick={() => run('Silence', silenceFirePanel)}
                >
                    {busy === 'Silence' ? 'Silencing…' : 'Silence'}
                </button>
                <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => run('Reset', resetFirePanel)}
                >
                    {busy === 'Reset' ? 'Resetting…' : 'Reset Panel'}
                </button>
                {message && <span className="write-message">{message}</span>}
            </div>

            <FirePanelControls />

            <h2 style={{ marginTop: '1.5rem' }}>Event History</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Kind</th>
                        <th>Detail</th>
                    </tr>
                </thead>
                <tbody>
                    {events.length === 0 && (
                        <tr>
                            <td colSpan={3} className="empty">
                                no events yet
                            </td>
                        </tr>
                    )}
                    {events.map((e, i) => (
                        <tr key={i}>
                            <td className="mono muted">{formatTime(e.timestamp)}</td>
                            <td className="mono">{e.kind}</td>
                            <td>{e.detail}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

import { useState } from 'react';

import { ackAlarm, createWorkOrderFromAlarm, fetchAlarms, type Alarm } from '@/lib/api';
import { toneStyle, type Tone } from '@/lib/points';
import { usePolledResource } from '@/lib/usePolledResource';

const POLL_INTERVAL_MS = 2500;

const STATE_LABEL: Record<Alarm['state'], string> = {
    active_unacked: 'UNACKED',
    active_acked: 'ACKED',
    cleared: 'CLEARED'
};

const STATE_TONE: Record<Alarm['state'], Tone> = {
    active_unacked: 'fault',
    active_acked: 'accent',
    cleared: 'ok'
};

type SortKey = 'newest' | 'priority';

export default function AlarmsPanel() {
    // No errorMessage passed — the summary table above already surfaces
    // gateway-unreachable state, same as before this was extracted into a shared hook.
    const { data: alarms } = usePolledResource<Alarm[]>(fetchAlarms, [], {
        intervalMs: POLL_INTERVAL_MS
    });
    const [busyId, setBusyId] = useState<number | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [sortKey, setSortKey] = useState<SortKey>('newest');

    async function handleAck(alarm: Alarm) {
        setBusyId(alarm.id);
        try {
            await ackAlarm(alarm.id);
        } catch (err) {
            setMessage(err instanceof Error ? err.message : 'Ack failed');
        } finally {
            setBusyId(null);
        }
    }

    async function handleCreateWorkOrder(alarm: Alarm) {
        setBusyId(alarm.id);
        try {
            await createWorkOrderFromAlarm(alarm.id, {
                asset: alarm.key.split('.')[0],
                problem: alarm.message,
                priority: alarm.priority
            });
            setMessage(`Work order created from alarm #${alarm.id} — see Work Orders below`);
        } catch (err) {
            setMessage(err instanceof Error ? err.message : 'Create work order failed');
        } finally {
            setBusyId(null);
        }
    }

    const sorted = [...alarms].sort((a, b) =>
        sortKey === 'priority' ? a.priority - b.priority || b.id - a.id : b.id - a.id
    );

    return (
        <div className="panel-section">
            <h2>Alarms</h2>
            {sorted.length === 0 ? (
                <p className="muted" style={{ fontSize: '.86rem' }}>
                    No alarms raised yet.
                </p>
            ) : (
                <table>
                    <thead>
                        <tr>
                            <th>
                                <button
                                    type="button"
                                    className="th-sort"
                                    onClick={() =>
                                        setSortKey((k) =>
                                            k === 'priority' ? 'newest' : 'priority'
                                        )
                                    }
                                >
                                    Priority{sortKey === 'priority' ? ' ▲' : ''}
                                </button>
                            </th>
                            <th>Message</th>
                            <th>State</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sorted.map((alarm) => (
                            <tr key={alarm.id}>
                                <td className="mono">P{alarm.priority}</td>
                                <td>{alarm.message}</td>
                                <td>
                                    <span
                                        className="chip"
                                        style={{
                                            background: toneStyle(STATE_TONE[alarm.state]).bg,
                                            color: toneStyle(STATE_TONE[alarm.state]).fg
                                        }}
                                    >
                                        {STATE_LABEL[alarm.state]}
                                    </span>
                                </td>
                                <td>
                                    {alarm.state === 'active_unacked' && (
                                        <button
                                            type="button"
                                            disabled={busyId === alarm.id}
                                            onClick={() => handleAck(alarm)}
                                        >
                                            Ack
                                        </button>
                                    )}{' '}
                                    {alarm.state !== 'cleared' && (
                                        <button
                                            type="button"
                                            disabled={busyId === alarm.id}
                                            onClick={() => handleCreateWorkOrder(alarm)}
                                        >
                                            Work Order
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
            {message && <p className="write-message">{message}</p>}
        </div>
    );
}

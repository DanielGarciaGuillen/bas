import { useEffect, useState } from 'react';

import { ackAlarm, createWorkOrderFromAlarm, fetchAlarms, type Alarm } from '@/lib/api';

const STATE_LABEL: Record<Alarm['state'], string> = {
    active_unacked: 'UNACKED',
    active_acked: 'ACKED',
    cleared: 'CLEARED'
};

export default function AlarmsPanel() {
    const [alarms, setAlarms] = useState<Alarm[]>([]);
    const [busyId, setBusyId] = useState<number | null>(null);
    const [message, setMessage] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function poll() {
            try {
                const next = await fetchAlarms();
                if (!cancelled) setAlarms(next);
            } catch {
                // the summary table above already surfaces gateway-unreachable state
            }
        }
        poll();
        const id = setInterval(poll, 2500);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

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

    const sorted = [...alarms].sort((a, b) => b.id - a.id);

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
                            <th>Priority</th>
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
                                            background:
                                                alarm.state === 'cleared'
                                                    ? 'var(--ok-soft)'
                                                    : alarm.state === 'active_acked'
                                                      ? 'var(--accent-soft)'
                                                      : 'var(--fault-soft)',
                                            color:
                                                alarm.state === 'cleared'
                                                    ? 'var(--ok)'
                                                    : alarm.state === 'active_acked'
                                                      ? 'var(--accent)'
                                                      : 'var(--fault)'
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

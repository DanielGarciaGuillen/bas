import { useEffect, useState } from 'react';

import { fetchWorkOrders, setWorkOrderStatus, type WorkOrder } from '@/lib/api';

export default function WorkOrdersPanel() {
    const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
    const [busyId, setBusyId] = useState<number | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function poll() {
            try {
                const next = await fetchWorkOrders();
                if (!cancelled) setWorkOrders(next);
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

    async function handleStatusChange(wo: WorkOrder, status: WorkOrder['status']) {
        setBusyId(wo.id);
        try {
            await setWorkOrderStatus(wo.id, status);
        } finally {
            setBusyId(null);
        }
    }

    const sorted = [...workOrders].sort((a, b) => b.id - a.id);

    return (
        <div className="panel-section">
            <h2>Work Orders</h2>
            <table>
                <thead>
                    <tr>
                        <th>Asset</th>
                        <th>Problem</th>
                        <th>Priority</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((wo) => (
                        <tr key={wo.id}>
                            <td className="mono muted">{wo.asset}</td>
                            <td>{wo.problem}</td>
                            <td className="mono">P{wo.priority}</td>
                            <td>
                                <select
                                    aria-label={`Status for work order ${wo.id}: ${wo.problem}`}
                                    value={wo.status}
                                    disabled={busyId === wo.id}
                                    onChange={(e) =>
                                        handleStatusChange(
                                            wo,
                                            e.target.value as WorkOrder['status']
                                        )
                                    }
                                >
                                    <option value="open">Open</option>
                                    <option value="in_progress">In Progress</option>
                                    <option value="done">Done</option>
                                </select>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

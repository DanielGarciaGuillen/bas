import { fetchPoints, type Point } from '@/lib/api';
import { formatValue, protocolFor } from '@/lib/points';
import { usePolledResource } from '@/lib/usePolledResource';

const POLL_INTERVAL_MS = 2500;

const STATUS_STYLE: Record<Point['status'], { bg: string; fg: string; label: string }> = {
    ok: { bg: 'var(--ok-soft)', fg: 'var(--ok)', label: 'OK' },
    fault: { bg: 'var(--fault-soft)', fg: 'var(--fault)', label: 'FAULT' },
    stale: { bg: 'var(--accent-soft)', fg: 'var(--accent)', label: 'STALE' }
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export default function Points() {
    const {
        data: points,
        error,
        updatedAt
    } = usePolledResource<Point[]>(fetchPoints, [], {
        intervalMs: POLL_INTERVAL_MS,
        errorMessage: `Can't reach the gateway at ${API_BASE_URL}`
    });

    const okCount = points.filter((p) => p.status === 'ok').length;
    const faultCount = points.filter((p) => p.status === 'fault').length;

    return (
        <>
            <div className="summary">
                <span className="count ok">{okCount} ok</span>
                {faultCount > 0 && <span className="count fault">{faultCount} fault</span>}
                <span className="updated">
                    {updatedAt ? `updated ${updatedAt.toLocaleTimeString()}` : 'connecting…'}
                </span>
            </div>

            {error && <div className="banner">{error}</div>}

            <table>
                <thead>
                    <tr>
                        <th>Device</th>
                        <th>Point</th>
                        <th>Protocol</th>
                        <th>Value</th>
                        <th>Units</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {points.length === 0 && !error && (
                        <tr>
                            <td colSpan={6} className="empty">
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
                                    <td className="muted">{protocolFor(point.device)}</td>
                                    <td className="mono value">{formatValue(point)}</td>
                                    <td className="muted">{point.units ?? '—'}</td>
                                    <td>
                                        <span
                                            className="chip"
                                            style={{ background: style.bg, color: style.fg }}
                                        >
                                            {style.label}
                                        </span>
                                    </td>
                                </tr>
                            );
                        })}
                </tbody>
            </table>
        </>
    );
}

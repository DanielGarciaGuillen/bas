// Points come from whatever the gateway happens to be polling (Modbus today, BACnet
// too) but always arrive in this one normalized shape. See gateway/app/state.py.
export interface Point {
    id: string;
    device: string;
    name: string;
    value: number | string | null;
    units: string | null;
    status: 'ok' | 'fault' | 'stale';
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function fetchPoints(): Promise<Point[]> {
    const res = await fetch(`${API_BASE_URL}/points`);
    if (!res.ok) throw new Error(`GET /points failed: ${res.status}`);
    return res.json();
}

export async function writeAhu1Setpoint(value: number): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/ahu-1/setpoint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value })
    });
    if (!res.ok) throw new Error(`POST /ahu-1/setpoint failed: ${res.status}`);
}

async function postFirePanel(path: string, body?: unknown): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/fire-panel${path}`, {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined
    });
    if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `POST /fire-panel${path} failed: ${res.status}`);
    }
}

export function triggerFireZone(zoneId: number, condition: 'alarm' | 'trouble' | 'supervisory') {
    return postFirePanel(`/zones/${zoneId}/trigger`, { condition });
}

export function clearFireZone(zoneId: number) {
    return postFirePanel(`/zones/${zoneId}/clear`);
}

export function resetFirePanel() {
    return postFirePanel('/reset');
}

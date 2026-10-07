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

async function postJson(path: string, body?: unknown): Promise<void> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined
    });
    if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `POST ${path} failed: ${res.status}`);
    }
}

export function triggerFireZone(zoneId: number, condition: 'alarm' | 'trouble' | 'supervisory') {
    return postJson(`/fire-panel/zones/${zoneId}/trigger`, { condition });
}

export function clearFireZone(zoneId: number) {
    return postJson(`/fire-panel/zones/${zoneId}/clear`);
}

export function resetFirePanel() {
    return postJson('/fire-panel/reset');
}

export interface Cardholder {
    id: number;
    name: string;
    access_level: number;
    schedule: 'always' | 'business_hours';
}

export async function fetchCardholders(): Promise<Cardholder[]> {
    const res = await fetch(`${API_BASE_URL}/access-control/cardholders`);
    if (!res.ok) throw new Error(`GET /access-control/cardholders failed: ${res.status}`);
    const data = await res.json();
    return data.cardholders;
}

export function badgeDoor(doorId: number, cardholderId: number) {
    return postJson(`/access-control/doors/${doorId}/badge`, { cardholder_id: cardholderId });
}

export function forceDoor(doorId: number) {
    return postJson(`/access-control/doors/${doorId}/force`);
}

export function holdOpenDoor(doorId: number) {
    return postJson(`/access-control/doors/${doorId}/hold-open`);
}

export function clearDoor(doorId: number) {
    return postJson(`/access-control/doors/${doorId}/clear`);
}

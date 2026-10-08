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

export function writeAhu1Setpoint(value: number): Promise<void> {
    return postJson('/ahu-1/setpoint', { value });
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

export function acknowledgeFirePanel() {
    return postJson('/fire-panel/acknowledge');
}

export function silenceFirePanel() {
    return postJson('/fire-panel/silence');
}

export interface FirePanelZone {
    id: number;
    name: string;
    condition: 'normal' | 'alarm' | 'trouble' | 'supervisory';
    field_cleared: boolean;
}

export interface FirePanelState {
    condition: 'normal' | 'alarm' | 'trouble' | 'supervisory';
    any_alarm: boolean;
    acknowledged: boolean;
    silenced: boolean;
    zones: FirePanelZone[];
}

export async function fetchFirePanel(): Promise<FirePanelState> {
    const res = await fetch(`${API_BASE_URL}/fire-panel/panel`);
    if (!res.ok) throw new Error(`GET /fire-panel/panel failed: ${res.status}`);
    return res.json();
}

export interface FirePanelEvent {
    kind: 'trigger' | 'clear' | 'acknowledge' | 'silence' | 'reset';
    zone_id: number | null;
    detail: string;
    timestamp: string;
}

export async function fetchFirePanelEvents(limit = 20): Promise<FirePanelEvent[]> {
    const res = await fetch(`${API_BASE_URL}/fire-panel/events?limit=${limit}`);
    if (!res.ok) throw new Error(`GET /fire-panel/events failed: ${res.status}`);
    return res.json();
}

export interface Cardholder {
    id: number;
    name: string;
    access_level: number;
    schedule: 'always' | 'business_hours';
}

export interface Door {
    id: number;
    name: string;
    required_level: number;
    state: 'normal' | 'forced' | 'held_open';
}

export interface AccessControlState {
    any_alarm: boolean;
    doors: Door[];
    cardholders: Cardholder[];
}

export async function fetchAccessControlState(): Promise<AccessControlState> {
    const res = await fetch(`${API_BASE_URL}/access-control/cardholders`);
    if (!res.ok) throw new Error(`GET /access-control/cardholders failed: ${res.status}`);
    return res.json();
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

export interface AccessEvent {
    door_id: number;
    cardholder_id: number | null;
    result: 'granted' | 'denied_level' | 'denied_schedule' | 'forced' | 'held_open';
    reason: string;
    timestamp: string;
}

export async function fetchAccessEvents(limit = 20): Promise<AccessEvent[]> {
    const res = await fetch(`${API_BASE_URL}/access-control/events?limit=${limit}`);
    if (!res.ok) throw new Error(`GET /access-control/events failed: ${res.status}`);
    return res.json();
}

export interface Alarm {
    id: number;
    key: string;
    message: string;
    priority: number;
    state: 'active_unacked' | 'active_acked' | 'cleared';
    created_at: string;
    acked_at: string | null;
    cleared_at: string | null;
}

export async function fetchAlarms(): Promise<Alarm[]> {
    const res = await fetch(`${API_BASE_URL}/alarms`);
    if (!res.ok) throw new Error(`GET /alarms failed: ${res.status}`);
    return res.json();
}

export function ackAlarm(alarmId: number) {
    return postJson(`/alarms/${alarmId}/ack`);
}

export function createWorkOrderFromAlarm(
    alarmId: number,
    body: { asset: string; problem: string; priority?: number }
) {
    return postJson(`/alarms/${alarmId}/work-order`, body);
}

export interface WorkOrder {
    id: number;
    asset: string;
    problem: string;
    priority: number;
    status: 'open' | 'in_progress' | 'done';
    notes: string;
    created_at: string;
    source_alarm_id: number | null;
}

export async function fetchWorkOrders(): Promise<WorkOrder[]> {
    const res = await fetch(`${API_BASE_URL}/work-orders`);
    if (!res.ok) throw new Error(`GET /work-orders failed: ${res.status}`);
    return res.json();
}

async function patchJson(path: string, body: unknown): Promise<void> {
    const res = await fetch(`${API_BASE_URL}${path}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `PATCH ${path} failed: ${res.status}`);
    }
}

export function setWorkOrderStatus(workOrderId: number, status: 'open' | 'in_progress' | 'done') {
    return patchJson(`/work-orders/${workOrderId}`, { status });
}

export interface HistorySample {
    value: number;
    timestamp: string;
}

export async function fetchHistory(
    pointId: string,
    minutes: number,
    limit = 2000
): Promise<HistorySample[]> {
    const res = await fetch(
        `${API_BASE_URL}/history/${encodeURIComponent(pointId)}?minutes=${minutes}&limit=${limit}`
    );
    if (!res.ok) throw new Error(`GET /history/${pointId} failed: ${res.status}`);
    return res.json();
}

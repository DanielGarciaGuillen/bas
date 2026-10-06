import type { Point } from './api';

// Device id prefix -> which protocol module (in the Learn tab) explains this point.
const PROTOCOL_BY_DEVICE: Record<string, string> = {
    'meter-1': 'Modbus TCP',
    'ahu-1': 'BACnet/IP',
    'fire-panel': 'REST'
};

export function protocolFor(device: string): string {
    return PROTOCOL_BY_DEVICE[device] ?? '—';
}

export function formatValue(point: Point): string {
    if (point.value === null) return '—';
    if (typeof point.value === 'number') return point.value.toLocaleString();
    return point.value;
}

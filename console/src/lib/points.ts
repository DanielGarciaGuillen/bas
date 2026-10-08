import type { Point } from './api';

// Device id prefix -> which protocol module (in the Notes tab) explains this point.
const PROTOCOL_BY_DEVICE: Record<string, string> = {
    'meter-1': 'Modbus TCP',
    'ahu-1': 'BACnet/IP',
    'fire-panel': 'REST',
    'access-control': 'REST'
};

export function protocolFor(device: string): string {
    return PROTOCOL_BY_DEVICE[device] ?? '—';
}

export function formatValue(point: Point): string {
    if (point.value === null) return '—';
    if (typeof point.value === 'number') return point.value.toLocaleString();
    return point.value;
}

export function pointById(points: Point[], id: string): Point | undefined {
    return points.find((p) => p.id === id);
}

export function numericValue(points: Point[], id: string): number | null {
    const point = pointById(points, id);
    return typeof point?.value === 'number' ? point.value : null;
}

// Semantic tones shared by every status/condition chip in the console. Each component
// keeps its own small, locally-typed string -> Tone map (what "FORCED" or "ALARM" means
// is domain-specific); this is just the one place the five tones become real CSS values,
// so an unrecognized backend string gets `neutral` instead of `undefined.bg` — the
// no-tone-mapped-to-this-value case used to read a color off an unguarded `Record<string,
// …>` lookup and throw mid-render.
export type Tone = 'ok' | 'fault' | 'accent' | 'info' | 'neutral';

const TONE_STYLE: Record<Tone, { bg: string; fg: string }> = {
    ok: { bg: 'var(--ok-soft)', fg: 'var(--ok)' },
    fault: { bg: 'var(--fault-soft)', fg: 'var(--fault)' },
    accent: { bg: 'var(--accent-soft)', fg: 'var(--accent)' },
    info: { bg: 'var(--info-soft)', fg: 'var(--info)' },
    neutral: { bg: 'var(--panel)', fg: 'var(--muted)' }
};

export function toneStyle(tone: Tone | undefined): { bg: string; fg: string } {
    return TONE_STYLE[tone ?? 'neutral'];
}

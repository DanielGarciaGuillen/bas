import { useState } from 'react';

import AhuGraphic from '@/components/AhuGraphic';
import { fetchPoints, writeAhu1Setpoint, type Point } from '@/lib/api';
import { numericValue } from '@/lib/points';
import { usePolledResource } from '@/lib/usePolledResource';

const POLL_INTERVAL_MS = 2500;

export default function AhuPanel() {
    const { data: points, error } = usePolledResource<Point[]>(fetchPoints, [], {
        intervalMs: POLL_INTERVAL_MS,
        errorMessage: "Can't reach the gateway"
    });
    // null = not yet edited by the operator (or just confirmed after a write) — in that
    // state the field displays the live polled setpoint, derived at render, rather than
    // a hardcoded default. Submitting an untouched form used to silently revert the real
    // device to '22.0' regardless of what it was actually set to.
    const [setpointOverride, setSetpointOverride] = useState<string | null>(null);
    const [writing, setWriting] = useState(false);
    const [writeMessage, setWriteMessage] = useState<string | null>(null);

    const liveSetpoint = numericValue(points, 'ahu-1.sat_setpoint');
    const setpointInput =
        setpointOverride ?? (liveSetpoint !== null ? liveSetpoint.toString() : '');

    async function handleWriteSetpoint(e: React.FormEvent) {
        e.preventDefault();
        const value = Number.parseFloat(setpointInput);
        if (Number.isNaN(value)) return;
        setWriting(true);
        setWriteMessage(null);
        try {
            await writeAhu1Setpoint(value);
            setWriteMessage(`Wrote ${value} °C`);
            setSetpointOverride(null);
        } catch {
            setWriteMessage('Write failed');
        } finally {
            setWriting(false);
        }
    }

    return (
        <div className="panel-section">
            <h2>AHU-1</h2>
            {error && <div className="banner">{error}</div>}
            <AhuGraphic points={points} />
            <form className="setpoint-form" onSubmit={handleWriteSetpoint}>
                <label htmlFor="setpoint">SAT setpoint (°C)</label>
                <input
                    id="setpoint"
                    type="number"
                    step="0.5"
                    value={setpointInput}
                    onChange={(e) => setSetpointOverride(e.target.value)}
                />
                <button type="submit" disabled={writing}>
                    {writing ? 'Writing…' : 'Write to BACnet'}
                </button>
                {writeMessage && <span className="write-message">{writeMessage}</span>}
            </form>
            <p className="muted" style={{ fontSize: '.8rem', marginTop: '.5rem' }}>
                Only the SAT setpoint is exposed here — the same single write path proven in M2/M3.
                Static pressure setpoint is polled but not yet writable from the console.
            </p>
        </div>
    );
}

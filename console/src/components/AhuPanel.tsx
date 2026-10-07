import { useEffect, useState } from 'react';

import AhuGraphic from '@/components/AhuGraphic';
import { fetchPoints, writeAhu1Setpoint, type Point } from '@/lib/api';

const POLL_INTERVAL_MS = 2500;

export default function AhuPanel() {
    const [points, setPoints] = useState<Point[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [setpointInput, setSetpointInput] = useState('22.0');
    const [writing, setWriting] = useState(false);
    const [writeMessage, setWriteMessage] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        async function poll() {
            try {
                const next = await fetchPoints();
                if (!cancelled) {
                    setPoints(next);
                    setError(null);
                }
            } catch {
                if (!cancelled) setError("Can't reach the gateway");
            }
        }
        poll();
        const id = setInterval(poll, POLL_INTERVAL_MS);
        return () => {
            cancelled = true;
            clearInterval(id);
        };
    }, []);

    async function handleWriteSetpoint(e: React.FormEvent) {
        e.preventDefault();
        const value = Number.parseFloat(setpointInput);
        if (Number.isNaN(value)) return;
        setWriting(true);
        setWriteMessage(null);
        try {
            await writeAhu1Setpoint(value);
            setWriteMessage(`Wrote ${value} °C`);
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
                    onChange={(e) => setSetpointInput(e.target.value)}
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

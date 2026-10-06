import { useState } from 'react';

import { clearFireZone, resetFirePanel, triggerFireZone } from '@/lib/api';

// Zone 4 is the one wired to AHU-1 (duct smoke detector) — the one whose alarm actually
// drives the interlock, so it's the one worth a one-click demo button.
const DEMO_ZONE_ID = 4;

export default function FirePanelControls() {
    const [busy, setBusy] = useState<'trigger' | 'reset' | null>(null);
    const [message, setMessage] = useState<string | null>(null);

    async function handleTrigger() {
        setBusy('trigger');
        setMessage(null);
        try {
            await triggerFireZone(DEMO_ZONE_ID, 'alarm');
            setMessage('Zone 4 ALARM — watch the AHU-1 fan/damper go to OFF above');
        } catch (err) {
            setMessage(err instanceof Error ? err.message : 'Trigger failed');
        } finally {
            setBusy(null);
        }
    }

    async function handleClearAndReset() {
        setBusy('reset');
        setMessage(null);
        try {
            await clearFireZone(DEMO_ZONE_ID);
            await resetFirePanel();
            setMessage('Panel reset — AHU-1 control returns to the schedule');
        } catch (err) {
            setMessage(err instanceof Error ? err.message : 'Reset failed');
        } finally {
            setBusy(null);
        }
    }

    return (
        <div className="setpoint-form">
            <span className="form-heading">Fire panel demo</span>
            <button type="button" onClick={handleTrigger} disabled={busy !== null}>
                {busy === 'trigger' ? 'Triggering…' : 'Trigger Zone 4 Alarm'}
            </button>
            <button type="button" onClick={handleClearAndReset} disabled={busy !== null}>
                {busy === 'reset' ? 'Resetting…' : 'Clear & Reset Panel'}
            </button>
            {message && <span className="write-message">{message}</span>}
        </div>
    );
}

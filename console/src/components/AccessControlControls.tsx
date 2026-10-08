import { useState } from 'react';

import { badgeDoor, clearDoor, forceDoor, holdOpenDoor, type Cardholder } from '@/lib/api';

// Server Room is the one with an interesting mix of outcomes to demo: some cardholders
// are granted, some denied by level, and (depending on the real wall-clock time) some
// denied by schedule — see docs/access-control-notes.md.
const DEMO_DOOR_ID = 2;

interface AccessControlControlsProps {
    cardholders: Cardholder[];
}

export default function AccessControlControls({ cardholders }: AccessControlControlsProps) {
    // null = no explicit operator selection yet; derive the default (first cardholder)
    // at render instead of seeding it via a setState-in-effect once the list arrives.
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [busy, setBusy] = useState<string | null>(null);
    const [message, setMessage] = useState<string | null>(null);

    const cardholderId = selectedId ?? cardholders[0]?.id ?? null;

    async function run(action: string, fn: () => Promise<void>) {
        setBusy(action);
        setMessage(null);
        try {
            await fn();
            setMessage(`${action} sent — check Server Room above`);
        } catch (err) {
            setMessage(err instanceof Error ? err.message : `${action} failed`);
        } finally {
            setBusy(null);
        }
    }

    return (
        <div className="setpoint-form">
            <span className="form-heading">Access control demo (Server Room)</span>
            <select
                value={cardholderId ?? ''}
                onChange={(e) => setSelectedId(Number(e.target.value))}
            >
                {cardholders.map((c) => (
                    <option key={c.id} value={c.id}>
                        {c.name} (L{c.access_level}, {c.schedule})
                    </option>
                ))}
            </select>
            <button
                type="button"
                disabled={busy !== null || cardholderId === null}
                onClick={() => run('Badge', () => badgeDoor(DEMO_DOOR_ID, cardholderId as number))}
            >
                {busy === 'Badge' ? 'Badging…' : 'Badge In'}
            </button>
            <button
                type="button"
                disabled={busy !== null}
                onClick={() => run('Force', () => forceDoor(DEMO_DOOR_ID))}
            >
                Force Door
            </button>
            <button
                type="button"
                disabled={busy !== null}
                onClick={() => run('Hold-open', () => holdOpenDoor(DEMO_DOOR_ID))}
            >
                Hold Open
            </button>
            <button
                type="button"
                disabled={busy !== null}
                onClick={() => run('Clear', () => clearDoor(DEMO_DOOR_ID))}
            >
                Clear
            </button>
            {message && <span className="write-message">{message}</span>}
        </div>
    );
}

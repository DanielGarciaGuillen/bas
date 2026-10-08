import AccessControlControls from '@/components/AccessControlControls';
import {
    fetchAccessControlState,
    fetchAccessEvents,
    type AccessControlState,
    type AccessEvent,
    type Door
} from '@/lib/api';
import { toneStyle, type Tone } from '@/lib/points';
import { usePolledResource } from '@/lib/usePolledResource';

const POLL_INTERVAL_MS = 2500;

interface AccessData {
    state: AccessControlState | null;
    events: AccessEvent[];
}

async function fetchAccessData(): Promise<AccessData> {
    const [state, events] = await Promise.all([fetchAccessControlState(), fetchAccessEvents(15)]);
    return { state, events };
}

// Record<Door['state'], Tone> (not Record<string, …>) so TS enforces every real door
// state is mapped — an unmapped value used to read `.bg` off `undefined` and throw
// mid-render; toneStyle()'s own fallback is the second safety net.
const DOOR_TONE: Record<Door['state'], Tone> = {
    normal: 'ok',
    forced: 'fault',
    held_open: 'fault'
};

const RESULT_TONE: Record<AccessEvent['result'], Tone> = {
    granted: 'ok',
    denied_level: 'fault',
    denied_schedule: 'fault',
    forced: 'fault',
    held_open: 'fault'
};

function formatTime(iso: string): string {
    return new Date(iso).toLocaleTimeString();
}

export default function AccessControlPanel() {
    // No errorMessage — panel stays on its last known state with no dedicated error
    // banner, same as before this was extracted into a shared hook.
    const { data } = usePolledResource<AccessData>(
        fetchAccessData,
        { state: null, events: [] },
        { intervalMs: POLL_INTERVAL_MS }
    );
    const { state, events } = data;

    return (
        <div className="panel-section">
            <h2>Doors</h2>
            <div className="overview-grid">
                {(state?.doors ?? []).map((door) => {
                    const style = toneStyle(DOOR_TONE[door.state]);
                    return (
                        <div className="overview-tile" key={door.id}>
                            <span className="overview-label">{door.name}</span>
                            <span
                                className="chip"
                                style={{
                                    background: style.bg,
                                    color: style.fg,
                                    width: 'fit-content'
                                }}
                            >
                                {door.state.toUpperCase()}
                            </span>
                        </div>
                    );
                })}
            </div>

            <AccessControlControls cardholders={state?.cardholders ?? []} />

            <h2 style={{ marginTop: '1.5rem' }}>Event Log</h2>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Door</th>
                        <th>Result</th>
                        <th>Reason</th>
                    </tr>
                </thead>
                <tbody>
                    {events.length === 0 && (
                        <tr>
                            <td colSpan={4} className="empty">
                                no events yet
                            </td>
                        </tr>
                    )}
                    {events.map((e, i) => {
                        const style = toneStyle(RESULT_TONE[e.result]);
                        const door = state?.doors.find((d) => d.id === e.door_id);
                        return (
                            <tr key={i}>
                                <td className="mono muted">{formatTime(e.timestamp)}</td>
                                <td>{door?.name ?? `Door ${e.door_id}`}</td>
                                <td>
                                    <span
                                        className="chip"
                                        style={{ background: style.bg, color: style.fg }}
                                    >
                                        {e.result}
                                    </span>
                                </td>
                                <td className="muted">{e.reason}</td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>

            <h2 style={{ marginTop: '1.5rem' }}>Cardholders</h2>
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Access Level</th>
                        <th>Schedule</th>
                    </tr>
                </thead>
                <tbody>
                    {(state?.cardholders ?? []).map((c) => (
                        <tr key={c.id}>
                            <td>{c.name}</td>
                            <td className="mono">{c.access_level}</td>
                            <td className="muted">{c.schedule}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

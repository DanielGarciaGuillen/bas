interface Box {
    id: string;
    x: number;
    y: number;
    w: number;
    h: number;
    lines: [string, string];
}

const BOXES: Box[] = [
    {
        id: 'bacnet',
        x: 20,
        y: 14,
        w: 190,
        h: 52,
        lines: ['BACnet/IP: AHU-1', '13 points, real PI loops']
    },
    {
        id: 'modbus',
        x: 20,
        y: 82,
        w: 190,
        h: 52,
        lines: ['Modbus TCP meter', 'kW register · :502']
    },
    {
        id: 'fire',
        x: 20,
        y: 150,
        w: 190,
        h: 52,
        lines: ['Fire alarm panel', 'REST · drives AHU-1 interlock']
    },
    {
        id: 'access',
        x: 20,
        y: 218,
        w: 190,
        h: 52,
        lines: ['Access control', '3 doors, 6 cardholders · REST']
    }
];

// Every sim in BOXES has shipped (the project is M0-M10 complete) — this used to carry
// a `live` set deciding solid-vs-dashed per box, but every entry was always live, so the
// branching was dead weight. One style, same visual result.
function BoxEl({ box }: { box: Box }) {
    return (
        <g>
            <rect
                x={box.x}
                y={box.y}
                width={box.w}
                height={box.h}
                rx={8}
                fill="var(--ok-soft)"
                stroke="var(--ok)"
                strokeWidth={2}
            />
            <text x={box.x + 14} y={box.y + 22} fill="var(--text)" fontWeight={600} fontSize={13}>
                {box.lines[0]}
            </text>
            <text x={box.x + 14} y={box.y + 40} fill="var(--muted)" fontSize={11}>
                {box.lines[1]}
            </text>
        </g>
    );
}

export default function ArchitectureDiagram() {
    return (
        <svg
            viewBox="0 0 980 300"
            role="img"
            aria-label="BuildingOps Lab architecture"
            style={{ width: '100%' }}
        >
            {BOXES.map((b) => (
                <BoxEl key={b.id} box={b} />
            ))}

            <g stroke="var(--line)" strokeWidth={1.5} fill="none">
                <path d="M210 40 H 420 V 128" stroke="var(--ok)" />
                <path d="M210 108 H 420 V 128" stroke="var(--ok)" />
                <path d="M210 176 H 420 V 128" stroke="var(--ok)" />
                <path d="M210 244 H 420 V 128" stroke="var(--ok)" />
            </g>

            <rect
                x={420}
                y={90}
                width={210}
                height={76}
                rx={10}
                fill="var(--ok-soft)"
                stroke="var(--ok)"
                strokeWidth={2}
            />
            <text
                x={525}
                y={120}
                fill="var(--text)"
                fontWeight={700}
                fontSize={14}
                textAnchor="middle"
            >
                Gateway
            </text>
            <text x={525} y={138} fill="var(--muted)" fontSize={11} textAnchor="middle">
                normalize · tag · alarm
            </text>
            <text x={525} y={153} fill="var(--muted)" fontSize={11} textAnchor="middle">
                FastAPI · :8000
            </text>

            <path d="M630 128 H 760" stroke="var(--ok)" strokeWidth={1.5} fill="none" />

            <rect
                x={760}
                y={90}
                width={200}
                height={76}
                rx={10}
                fill="var(--ok-soft)"
                stroke="var(--ok)"
                strokeWidth={2}
            />
            <text
                x={860}
                y={120}
                fill="var(--text)"
                fontWeight={700}
                fontSize={14}
                textAnchor="middle"
            >
                Console (you are here)
            </text>
            <text x={860} y={138} fill="var(--muted)" fontSize={11} textAnchor="middle">
                React + TS · :5173
            </text>
            <text x={860} y={153} fill="var(--muted)" fontSize={11} textAnchor="middle">
                live points + this tab
            </text>

            <text x={490} y={285} fill="var(--muted)" fontSize={11} textAnchor="middle">
                bas_net · 10.10.0.0/24, one Docker bridge network standing in for several real VLANs
            </text>
        </svg>
    );
}

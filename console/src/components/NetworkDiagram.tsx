interface VlanBox {
    x: number;
    label: string;
    subnet: string;
    link: 'solid' | 'restricted' | 'isolated';
    device?: string;
}

const VLANS: VlanBox[] = [
    { x: 70, label: 'IT / Corporate', subnet: '10.10.1.0/24', link: 'solid' },
    { x: 250, label: 'Management', subnet: '10.10.99.0/24', link: 'solid' },
    {
        x: 430,
        label: 'BAS',
        subnet: '10.10.10.0/24',
        link: 'restricted',
        device: 'AHU-1 / VAV + gateway'
    },
    {
        x: 610,
        label: 'Security',
        subnet: '10.10.20.0/24',
        link: 'restricted',
        device: 'Cameras / access panels'
    },
    {
        x: 790,
        label: 'Fire Alarm',
        subnet: '10.10.30.0/24',
        link: 'isolated',
        device: 'Fire alarm panel'
    }
];

const LINK_CLASS: Record<VlanBox['link'], string> = {
    solid: 'net-link',
    restricted: 'net-link net-link-restricted',
    isolated: 'net-link net-link-isolated'
};

const LINK_LABEL: Record<VlanBox['link'], string> = {
    solid: '',
    restricted: 'restricted',
    isolated: 'isolated'
};

const FIREWALL_X = 430;
const ROW_INTERNET = 25;
const ROW_FIREWALL = 95;
const ROW_VLAN = 190;
const ROW_DEVICE = 270;

export default function NetworkDiagram() {
    return (
        <div className="net-diagram-wrap">
            <svg
                viewBox="0 0 900 310"
                role="img"
                aria-label="Network VLAN diagram"
                className="net-diagram"
            >
                <line
                    x1={90}
                    y1={ROW_INTERNET}
                    x2={FIREWALL_X}
                    y2={ROW_FIREWALL}
                    className="net-link"
                />
                <rect x={20} y={ROW_INTERNET - 15} width="140" height="30" className="net-box" />
                <text x={90} y={ROW_INTERNET + 5} textAnchor="middle" className="net-label-strong">
                    Internet
                </text>

                <rect
                    x={FIREWALL_X - 70}
                    y={ROW_FIREWALL - 15}
                    width="140"
                    height="30"
                    className="net-box net-box-fw"
                />
                <text
                    x={FIREWALL_X}
                    y={ROW_FIREWALL + 5}
                    textAnchor="middle"
                    className="net-label-strong"
                >
                    Firewall / Router
                </text>

                {VLANS.map((v) => (
                    <line
                        key={`link-${v.label}`}
                        x1={FIREWALL_X}
                        y1={ROW_FIREWALL + 15}
                        x2={v.x}
                        y2={ROW_VLAN - 20}
                        className={LINK_CLASS[v.link]}
                    />
                ))}

                {VLANS.map((v) => (
                    <g key={v.label}>
                        <rect
                            x={v.x - 75}
                            y={ROW_VLAN - 18}
                            width="150"
                            height="40"
                            className="net-box"
                        />
                        <text
                            x={v.x}
                            y={ROW_VLAN - 2}
                            textAnchor="middle"
                            className="net-label-strong"
                        >
                            {v.label}
                        </text>
                        <text
                            x={v.x}
                            y={ROW_VLAN + 14}
                            textAnchor="middle"
                            className="net-label-mono"
                        >
                            {v.subnet}
                        </text>
                        {LINK_LABEL[v.link] && (
                            <text
                                x={(FIREWALL_X + v.x) / 2}
                                y={(ROW_FIREWALL + ROW_VLAN) / 2 - 2}
                                textAnchor="middle"
                                className="net-link-label"
                            >
                                {LINK_LABEL[v.link]}
                            </text>
                        )}
                        {v.device && (
                            <>
                                <line
                                    x1={v.x}
                                    y1={ROW_VLAN + 22}
                                    x2={v.x}
                                    y2={ROW_DEVICE - 15}
                                    className="net-link"
                                />
                                <rect
                                    x={v.x - 85}
                                    y={ROW_DEVICE - 15}
                                    width="170"
                                    height="30"
                                    className="net-box net-box-device"
                                />
                                <text
                                    x={v.x}
                                    y={ROW_DEVICE + 5}
                                    textAnchor="middle"
                                    className="net-label"
                                >
                                    {v.device}
                                </text>
                            </>
                        )}
                    </g>
                ))}
            </svg>
        </div>
    );
}

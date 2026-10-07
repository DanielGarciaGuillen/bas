import NetworkDiagram from '@/components/NetworkDiagram';

const VLANS = [
    {
        vlan: 'IT / Corporate',
        purpose: 'Office workstations, email, general LAN, internet access',
        subnet: '10.10.1.0/24'
    },
    {
        vlan: 'BAS',
        purpose: 'BACnet/IP field controllers (AHU, VAVs) + the supervisor/gateway',
        subnet: '10.10.10.0/24'
    },
    {
        vlan: 'Security',
        purpose: 'Cameras, access control panels and card readers',
        subnet: '10.10.20.0/24'
    },
    {
        vlan: 'Fire Alarm',
        purpose: 'Panel monitoring/annunciation — kept separate from every other VLAN',
        subnet: '10.10.30.0/24'
    },
    { vlan: 'Management', purpose: 'Switch/AP/UPS out-of-band management', subnet: '10.10.99.0/24' }
];

const PORTS = [
    {
        protocol: 'BACnet/IP',
        port: 'UDP 47808',
        notes: 'Broadcast-heavy — see the BBMD note below'
    },
    {
        protocol: 'Modbus TCP',
        port: '502',
        notes: 'Unencrypted, unauthenticated by design — never expose beyond the BAS VLAN'
    },
    {
        protocol: 'HTTPS',
        port: '443',
        notes: 'Gateway API / console, and vendor cloud dashboards where used'
    },
    {
        protocol: 'MQTT',
        port: '1883 / 8883 (TLS)',
        notes: 'Stretch goal only — see PLAN.md’s stretch list'
    },
    { protocol: 'SSH', port: '22', notes: 'Management VLAN only, key-based auth' }
];

const FIREWALL_RULES = [
    {
        from: 'BAS',
        to: 'Supervisor/gateway (BAS VLAN)',
        allowed: 'BACnet/IP, HTTPS to the gateway’s API'
    },
    {
        from: 'BAS',
        to: 'Anywhere else',
        allowed: 'Denied — no internet egress from field controllers'
    },
    {
        from: 'Security',
        to: 'NVR / access control server (Security VLAN)',
        allowed: 'RTSP/ONVIF, the access panel’s own protocol'
    },
    {
        from: 'Security',
        to: 'Anywhere else',
        allowed: 'Denied — cameras and readers never need outbound internet'
    },
    {
        from: 'Fire Alarm',
        to: 'Monitoring/annunciation workstation only',
        allowed: 'Vendor-specific monitoring protocol'
    },
    { from: 'Fire Alarm', to: 'Every other VLAN', allowed: 'Denied — fully isolated' },
    { from: 'Management', to: 'BAS / Security / Fire infrastructure', allowed: 'SSH, HTTPS' },
    { from: 'IT / Corporate', to: 'Internet', allowed: 'Allowed (normal corporate egress)' },
    {
        from: 'IT / Corporate',
        to: 'BAS / Security / Fire / Management',
        allowed: 'Denied, except through a jump host with MFA'
    }
];

export default function NetworkPage() {
    return (
        <div className="panel-section">
            <h2>Network Design</h2>
            <p className="muted" style={{ fontSize: '.86rem', maxWidth: '68ch' }}>
                The lab itself runs on one flat Docker network (<code>bas_net</code>,{' '}
                <code>10.10.0.0/24</code>) for simplicity. This page renders the realistic
                multi-VLAN design a real small office building would use instead — see{' '}
                <code>docs/network-design.md</code>.
            </p>

            <NetworkDiagram />

            <h2 style={{ marginTop: '1.5rem' }}>VLAN Plan</h2>
            <table>
                <thead>
                    <tr>
                        <th>VLAN</th>
                        <th>Purpose</th>
                        <th>Subnet</th>
                    </tr>
                </thead>
                <tbody>
                    {VLANS.map((v) => (
                        <tr key={v.vlan}>
                            <td>{v.vlan}</td>
                            <td className="muted">{v.purpose}</td>
                            <td className="mono">{v.subnet}</td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <h2 style={{ marginTop: '1.5rem' }}>IP Addressing</h2>
            <ul className="net-notes">
                <li>
                    <b>Static:</b> BAS field controllers, security panels/cameras, the fire alarm
                    monitoring interface, and all management interfaces — a controller's address
                    can't drift out from under the supervisor polling it.
                </li>
                <li>
                    <b>DHCP:</b> IT/Corporate workstations and laptops only — the one VLAN where
                    devices actually come and go.
                </li>
                <li>
                    Default gateway per VLAN is the subnet's <code>.1</code> address; field devices
                    get addresses from <code>.10</code> upward.
                </li>
            </ul>

            <h2 style={{ marginTop: '1.5rem' }}>Ports &amp; Protocols</h2>
            <table>
                <thead>
                    <tr>
                        <th>Protocol</th>
                        <th>Port</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    {PORTS.map((p) => (
                        <tr key={p.protocol}>
                            <td className="mono">{p.protocol}</td>
                            <td className="mono">{p.port}</td>
                            <td className="muted">{p.notes}</td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <h2 style={{ marginTop: '1.5rem' }}>Firewall Rules (Least Privilege)</h2>
            <table>
                <thead>
                    <tr>
                        <th>From</th>
                        <th>To</th>
                        <th>Allowed</th>
                    </tr>
                </thead>
                <tbody>
                    {FIREWALL_RULES.map((r, i) => (
                        <tr key={i}>
                            <td>{r.from}</td>
                            <td className="muted">{r.to}</td>
                            <td className="muted">{r.allowed}</td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <h2 style={{ marginTop: '1.5rem' }}>Notes</h2>
            <ul className="net-notes">
                <li>
                    <b>BACnet broadcast behavior and BBMDs:</b> BACnet/IP devices find each other
                    with broadcast frames (<code>Who-Is</code>/<code>I-Am</code>), and broadcasts
                    don't cross a routed subnet boundary by default. A real building with BAS
                    controllers split across more than one IP subnet needs a <b>BBMD</b> (BACnet
                    Broadcast Management Device) on each subnet to forward broadcasts between them.
                    This lab's <code>bas_net</code> is one flat subnet, so no BBMD is needed here.
                </li>
                <li>
                    <b>PoE for cameras and readers:</b> security cameras and card readers are
                    normally powered over the same Ethernet run (802.3af/at/bt) from PoE switches on
                    the Security VLAN — one cable per device instead of separate low-voltage power
                    wiring.
                </li>
                <li>
                    <b>Basic OT security hygiene:</b> change every controller/panel's default
                    password before commissioning; keep BAS/Security/Fire off the general IT LAN
                    entirely; remote access into any OT VLAN only through a VPN terminating at a
                    jump host, never a port-forward straight to a controller; firmware updates from
                    the vendor's verified source only.
                </li>
            </ul>
        </div>
    );
}

import type { ReactNode } from 'react';

import ArchitectureDiagram from './ArchitectureDiagram';
import { ConceptCard, FieldNote, FlashCard } from './components';

export interface Module {
    id: string;
    navLabel: string;
    status: 'done' | 'next' | 'locked';
    heading: string;
    tag: string;
    body: ReactNode;
}

export const MODULES: Module[] = [
    {
        id: 'overview',
        navLabel: 'Overview',
        status: 'done',
        heading: 'The lab, as wired today',
        tag: 'solid + color = container is running real code',
        body: (
            <>
                <p>
                    Six containers, one Docker network (<code>bas_net</code>,{' '}
                    <code>10.10.0.0/24</code>). Field-side boxes feed the gateway over whatever
                    protocol they natively speak; this console only ever talks to the gateway's REST
                    API, never to a protocol directly.
                </p>
                <ArchitectureDiagram />
                <div className="concept-grid">
                    <ConceptCard title="Live now">
                        Modbus meter (read-only) and BACnet AHU-1 (read + write), both feeding this
                        exact page you're looking at.
                    </ConceptCard>
                    <ConceptCard title="Up next">
                        Fire alarm panel + interlock — the fan-shutdown sequence the M3 commandable
                        points were built to support.
                    </ConceptCard>
                    <ConceptCard title="Why one network">
                        A real site segments IT / BAS / security / fire onto separate VLANs (see{' '}
                        <code>docs/network-design.md</code>). The lab flattens that to one Docker
                        bridge for simplicity — a simplification worth explaining, not hiding.
                    </ConceptCard>
                </div>
            </>
        )
    },
    {
        id: 'm0',
        navLabel: 'M0 · Foundations',
        status: 'done',
        heading: 'M0 · Foundations',
        tag: 'repo skeleton, Docker Compose, docs stubs',
        body: (
            <>
                <p>
                    Before any protocol code, the shape of the system: simulators, a gateway, a
                    console, wired by Compose on their own network — mirroring how a real site
                    separates field controllers from the supervisory server from the operator's
                    screen.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="Concept">
                        A BAS project is a small distributed system, not an app. The gateway plays
                        the role of the <b>supervisory device</b> (a JACE, a Niagara station, a
                        vendor head-end) — the only thing that speaks every protocol.
                    </ConceptCard>
                    <ConceptCard title="Why it matters">
                        Interviewers for controls/BAS roles probe this constantly: field protocol
                        vs. supervisory layer vs. operator UI are three different jobs with three
                        different failure modes.
                    </ConceptCard>
                </div>
                <FlashCard
                    q={
                        <>
                            Why would a building have both field protocols <em>and</em> a web front
                            end?
                        </>
                    }
                    a="Field protocols (BACnet, Modbus) are what controllers natively speak — lightweight, deterministic, built for a control network, not a browser. The web front end needs a translation layer — the gateway — that normalizes different protocols into one point model."
                />
            </>
        )
    },
    {
        id: 'm1',
        navLabel: 'M1 · Modbus meter',
        status: 'done',
        heading: 'M1 · Modbus energy meter',
        tag: 'easiest protocol first — proves device → gateway → API',
        body: (
            <>
                <p>
                    Modbus TCP has no concept of a "named point" on the wire — just a function code,
                    a starting address, and a count.{' '}
                    <b>Register 0 means whatever the register map says it means</b>, and nothing
                    more.
                </p>
                <div className="table-wrap">
                    <table className="regmap">
                        <thead>
                            <tr>
                                <th>Register</th>
                                <th>Function</th>
                                <th>Addr</th>
                                <th>Scale</th>
                                <th>Units</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>kW total</td>
                                <td className="mono">Read Input Registers (0x04)</td>
                                <td className="mono">0</td>
                                <td className="mono">÷10</td>
                                <td>kW</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <pre>
                    <code>
                        <span className="tok-com"># gateway/app/modbus_meter.py</span>
                        {'\n'}
                        <span className="tok-kw">def</span> decode_kw(raw_register: int) -&gt;
                        float:{'\n'}
                        {'    '}
                        <span className="tok-str">
                            """Register is kW x10 — docs/modbus-register-map.md."""
                        </span>
                        {'\n    '}
                        <span className="tok-kw">return</span> raw_register / 10.0
                    </code>
                </pre>
                <FieldNote title="the library trap">
                    <p>
                        <code>pip install pymodbus</code> grabs 3.15.x by default — a release that
                        replaced the simple, decade-stable read-write datastore with a new
                        config-driven model that can't mutate a plain device's values at runtime.
                        Pinned to <b>pymodbus 3.8.6</b> instead.
                    </p>
                </FieldNote>
                <FlashCard
                    q="How would the gateway know register 0 means kW and not, say, voltage?"
                    a="It wouldn't, unless told. The register map is out-of-band knowledge the polling code is written against. Unlike BACnet, Modbus has no self-describing object model."
                />
            </>
        )
    },
    {
        id: 'm2',
        navLabel: 'M2 · BACnet AHU-1',
        status: 'done',
        heading: 'M2 · BACnet AHU-1',
        tag: 'self-describing points, read and write',
        body: (
            <>
                <p>
                    Where Modbus gave each register a number and nothing else, BACnet gives every
                    point an <b>object type and instance</b> — the device describes itself on the
                    wire. The setpoint write you can try on the Live tab is this module, live.
                </p>
                <div className="table-wrap">
                    <table className="regmap">
                        <thead>
                            <tr>
                                <th>Object</th>
                                <th>Type</th>
                                <th>Name on the wire</th>
                                <th>Writable</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>SAT Setpoint</td>
                                <td className="mono">Analog Value, 1</td>
                                <td className="mono">AHU1-SAT-SP</td>
                                <td>yes</td>
                            </tr>
                            <tr>
                                <td>Supply Air Temp</td>
                                <td className="mono">Analog Input, 1</td>
                                <td className="mono">AHU1-SAT</td>
                                <td>no</td>
                            </tr>
                            <tr>
                                <td>Fan Status</td>
                                <td className="mono">Binary Input, 1</td>
                                <td className="mono">AHU1-FAN-STATUS</td>
                                <td>no</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <FieldNote title="BAC0 vs. bacpypes3">
                    <p>
                        BAC0 wraps bacpypes3 for <em>scanning</em> other people's devices. This
                        project needs to <em>be</em> a device — bacpypes3's own territory:{' '}
                        <code>NormalApplication</code> plus <code>bacpypes3.local.*</code> object
                        classes.
                    </p>
                </FieldNote>
                <FieldNote title="commandable objects">
                    <p>
                        A plain <code>AnalogValueObject</code> doesn't accept network writes — it
                        needs the <code>Commandable</code> mixin, which adds BACnet's{' '}
                        <b>priority array</b>: 16 ranked write slots so an operator override, a
                        schedule, and a safety interlock can all hold an opinion on the same point
                        without permanently clobbering each other.
                    </p>
                </FieldNote>
                <FlashCard
                    q="What's the practical difference between how BACnet and Modbus expose a point?"
                    a="Modbus is anonymous numbered registers — meaning lives entirely in out-of-band documentation. BACnet objects carry their own type, name, units, and status as part of the protocol, which is also why BACnet supports device/object discovery (Who-Is/I-Am) that Modbus has no equivalent for."
                />
            </>
        )
    },
    {
        id: 'm3',
        navLabel: 'M3 · Sequence of operation',
        status: 'done',
        heading: 'M3 · AHU-1 sequence of operation',
        tag: 'a real PI loop, an economizer, and a schedule — not a lag anymore',
        body: (
            <>
                <p>
                    M2's setpoint write already moved AHU-1's simulated supply air temp, but only
                    through a crude lag. M3 replaces that with the controller's actual firmware
                    logic — which is also why this lives in <code>sims/bacnet_devices/</code>, not
                    the gateway: a sequence of operation runs <em>on the field controller</em>, the
                    same way it would on a real AHU. The gateway only ever reads values and writes
                    setpoints, exactly like it did before.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="Split-range control">
                        One signed PI output (negative = cool, positive = heat) splits into two
                        valve commands, so the loop structurally can't call for heating and cooling
                        at once.
                    </ConceptCard>
                    <ConceptCard title="Economizer">
                        Free outside-air cooling — but only when the loop is actually calling for
                        cooling and the outside air is usefully colder than return air.
                    </ConceptCard>
                    <ConceptCard title="Two PI loops">
                        SAT tracks the setpoint via the valves; duct static pressure tracks its own
                        setpoint via fan speed, on a simple quadratic fan curve.
                    </ConceptCard>
                </div>

                <FieldNote title="integral windup, misdiagnosed twice">
                    <p>
                        First pass clamped the controller's integral term directly to the output
                        range (±100). With a small <code>ki</code> (0.01), that capped the
                        integral's <em>contribution</em> at 1.0 — nowhere near enough to ever close
                        a steady error. The loop stabilized exactly 4°C off setpoint and stayed
                        there. Fix: clamp the integral to <code>±(output_range / ki)</code>, the
                        textbook anti-windup bound.
                    </p>
                </FieldNote>

                <FieldNote title="a textbook limit cycle">
                    <p>
                        Even after that fix, a cooling scenario still wouldn't settle. Cause: the
                        economizer's OA damper snapped instantly between 20% and 90% every tick,
                        swinging the mixed-air temperature so hard each way that the SAT loop
                        oscillated forever — a real bang-bang limit cycle, invisible to a
                        per-function unit test and only visible by simulating hundreds of ticks end
                        to end. Fix: give every actuator a bounded slew rate (
                        <code>ramp_toward</code>) — which is also just how real actuators behave.
                    </p>
                </FieldNote>

                <FieldNote title="two deployment bugs the unit tests couldn't see">
                    <p>
                        <code>control.py</code> was a new file; the Dockerfile only copied{' '}
                        <code>main.py</code> — built fine, crashed instantly on start with{' '}
                        <code>ModuleNotFoundError</code>. Separately, a cold{' '}
                        <code>docker compose up</code> let the gateway's first BACnet read race
                        AHU-1 still starting, and it hung forever with no timeout instead of
                        raising. Neither was visible from pytest running on the host — both only
                        showed up by actually cold-starting the real containers.
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why would a control loop that converges fine in testing oscillate forever in the field?"
                    a="Usually a loop updating faster than the physical actuator it's commanding can actually move — a damper or valve told to jump straight to a new position every cycle, with no slew-rate limit modeling how long real hardware takes to get there, can turn a stable-looking control law into a bang-bang oscillator once it meets real (or realistically simulated) hardware."
                />
            </>
        )
    },
    {
        id: 'console',
        navLabel: 'Console (this page)',
        status: 'done',
        heading: "This console, and why it's also this tutorial",
        tag: "the UI only ever talks to the gateway's API",
        body: (
            <>
                <p>
                    The Live tab fetches <code>GET /points</code> every 2.5 seconds and never
                    touches BACnet or Modbus directly — that's the entire point of the gateway's
                    normalized point model. A real BAS web client (a Niagara station's UI, a vendor
                    SCADA client) works the same way: it talks to the supervisory layer's own API,
                    which already did the protocol work.
                </p>
                <FieldNote title="a real CORS wrinkle">
                    <p>
                        This console (<code>:5173</code>) and the gateway (<code>:8000</code>) are
                        different origins even on the same machine — the browser blocks the fetch
                        unless the gateway sends CORS headers. Caught by actually loading the page
                        in a browser, not by trusting that a passing <code>curl</code> check meant
                        the UI would work.
                    </p>
                </FieldNote>
                <FlashCard
                    q="Why would a BAS web client never speak BACnet directly from the browser?"
                    a="BACnet/IP is UDP-broadcast-heavy with no browser-native transport. More fundamentally, the supervisory layer exists specifically to separate protocol-speaking from presentation — the browser only ever needs HTTP/WebSocket to one normalized API."
                />
            </>
        )
    },
    {
        id: 'later',
        navLabel: 'M4 – M10 · Rest of the build',
        status: 'next',
        heading: 'M4 – M10 · Everything after that',
        tag: 'one line each, so the shape of the build stays visible',
        body: (
            <div className="teaser-list">
                <div className="teaser">
                    <span className="t-id">M4</span>
                    <div>
                        <h3>Fire alarm panel + interlock</h3>
                        <p>
                            NORMAL / ALARM / TROUBLE / SUPERVISORY, and the fan-shutdown interlock
                            tying life-safety into HVAC.
                        </p>
                    </div>
                </div>
                <div className="teaser">
                    <span className="t-id">M5</span>
                    <div>
                        <h3>Access control</h3>
                        <p>Door events, forced/held alarms, access levels and schedules.</p>
                    </div>
                </div>
                <div className="teaser">
                    <span className="t-id">M6</span>
                    <div>
                        <h3>Alarm engine, history, work orders</h3>
                        <p>
                            Alarm lifecycle, trend history, and CMMS-lite work orders — the gateway
                            becomes operational, not just a pipe.
                        </p>
                    </div>
                </div>
                <div className="teaser">
                    <span className="t-id">M7+</span>
                    <div>
                        <h3>The full operator console</h3>
                        <p>
                            Floor plan, AHU graphic, alarms, trends, fire annunciator, and the
                            network page — grown from this same page.
                        </p>
                    </div>
                </div>
            </div>
        )
    }
];

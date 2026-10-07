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
                        Modbus meter, BACnet AHU-1 with a real sequence of operation, a fire panel
                        whose alarm can shut the AHU down, access control with per-door,
                        per-cardholder decisions, an alarm engine with trend history and work
                        orders, and a nine-tab console (Overview, AHU-1, Fire Panel, Access, Alarms,
                        Trends, Points, Network, Notes) — try the demo buttons on the Fire Panel and
                        Access tabs.
                    </ConceptCard>
                    <ConceptCard title="Up next">
                        The final write-up — README polish, a demo video script, and the
                        resume-ready project summary.
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
                        Field protocol, supervisory layer, and operator UI are three different jobs
                        with three different failure modes — keeping them separate services makes
                        each one easy to reason about on its own.
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
        heading: "This console, and why it's also where these notes live",
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
        id: 'm4',
        navLabel: 'M4 · Fire alarm interlock',
        status: 'done',
        heading: 'M4 · Fire alarm panel + AHU-1 interlock',
        tag: 'a REST panel, and a BACnet priority override from outside the controller',
        body: (
            <>
                <p>
                    The fire panel sim speaks plain REST — on purpose. A real fire alarm panel
                    doesn't speak BACnet or Modbus to the BAS; monitoring/annunciation is its own
                    system, kept deliberately separate. The gateway polls it the same <em>shape</em>{' '}
                    it polls BACnet and Modbus, just over HTTP.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="Acknowledge / silence / reset">
                        A new condition clears any old acknowledge/silence. Reset is rejected (HTTP
                        409, naming the zone) until every active zone's field device has itself
                        cleared — matching real practice.
                    </ConceptCard>
                    <ConceptCard title="The interlock">
                        Any zone in ALARM makes the gateway write AHU-1's fan command and OA damper
                        at BACnet priority 1 — one level above the schedule's priority 16.
                    </ConceptCard>
                    <ConceptCard title="Relinquish, don't restore">
                        Clearing the interlock means withdrawing the priority-1 entry, not writing a
                        value back. The schedule regains control automatically — nothing needs to
                        remember what it was doing.
                    </ConceptCard>
                </div>

                <FieldNote title="verified before writing any interlock code">
                    <p>
                        Before touching <code>gateway/app/bacnet_ahu.py</code>, a throwaway
                        client/server script confirmed directly: does a priority-1{' '}
                        <code>WriteProperty</code> really survive the schedule's ongoing priority-16
                        writes? It does. Does relinquishing need a value, or something else? It
                        needs <code>primitivedata.Null(())</code> — a bare Python <code>None</code>{' '}
                        doesn't cast. Checked against the real objects before it mattered, not
                        assumed from the spec.
                    </p>
                </FieldNote>

                <FieldNote title="the same shared-mutable-default bug, in a new disguise">
                    <p>
                        <code>Panel()</code>'s default zones were built from a module-level list —
                        reused by <em>reference</em>, not copied. One test's <code>trigger()</code>{' '}
                        secretly mutated a <code>Zone</code> every other <code>Panel()</code> in the
                        same process was sharing, so tests passed alone and failed together. Same
                        root cause as a mutable default argument, one level removed.
                    </p>
                </FieldNote>

                <FieldNote title="a known gap, left alone on purpose">
                    <p>
                        The interlock forces the fan/damper off, but AHU-1's own PI loops don't know
                        the fire panel exists — they keep computing valve positions as if the fan
                        were still running. Fixing that would mean teaching the AHU's sequence about
                        the fire panel, exactly the boundary this design was built to avoid
                        crossing. Documented, not silently fixed — see{' '}
                        <code>docs/sequences-of-operation.md</code> §7.
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why implement a fire-to-HVAC interlock as an override from outside the AHU controller, instead of adding fire-alarm logic to the AHU's own sequence?"
                    a="Separation of concerns and failure isolation — a controller's sequence shouldn't need to know about every system that might override it (fire, a manual command, demand response). BACnet's priority array exists precisely so independent systems can each assert control at an appropriate priority without any of them needing to know about the others."
                />
            </>
        )
    },
    {
        id: 'm5',
        navLabel: 'M5 · Access control',
        status: 'done',
        heading: 'M5 · Access control',
        tag: 'a third instance of the same REST boundary fire alarm already established',
        body: (
            <>
                <p>
                    Same deliberate boundary as the fire panel: access control is its own system,
                    speaks REST rather than a field protocol, and the gateway polls it the same
                    shape as everything else. By this milestone that wasn't a new decision — just
                    applying one already made twice.
                </p>
                <div className="table-wrap">
                    <table className="regmap">
                        <thead>
                            <tr>
                                <th>Door</th>
                                <th>Required level</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Main Entrance</td>
                                <td className="mono">1</td>
                            </tr>
                            <tr>
                                <td>Server Room</td>
                                <td className="mono">2</td>
                            </tr>
                            <tr>
                                <td>Mechanical Room</td>
                                <td className="mono">3</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                <p style={{ fontSize: '.86rem', color: 'var(--muted)', marginTop: '-.4rem' }}>
                    Six cardholders span every outcome worth demoing — a facilities manager with
                    blanket access, 24/7 security with mid-tier access, a night cleaner capped at
                    the front door, and day-shift staff who lose access the moment the clock passes
                    6pm. See <code>docs/access-control-notes.md</code>.
                </p>

                <div className="concept-grid">
                    <ConceptCard title="No simulated clock here">
                        AHU-1 runs an accelerated "sim day" because it has an autonomous loop worth
                        watching. Access control is purely event-driven — a badge attempt either
                        happens or it doesn't — so "business hours" just checks the real wall-clock
                        time.
                    </ConceptCard>
                    <ConceptCard title="Five event results">
                        <code>granted</code>, <code>denied_level</code>,{' '}
                        <code>denied_schedule</code>, <code>forced</code>, <code>held_open</code> —
                        the last two raise an alarm point the gateway surfaces but (unlike fire)
                        doesn't yet act on.
                    </ConceptCard>
                </div>

                <FieldNote title="caught before it had the chance to bite">
                    <p>
                        <code>AccessControlSystem</code>'s zones are built fresh in{' '}
                        <code>__post_init__</code> rather than reused from a module-level default
                        list — written that way from the start this time, because M4's fire panel
                        had already paid for the shared-mutable-default lesson. The test suite
                        passed on the first run as a result.
                    </p>
                </FieldNote>

                <FieldNote title="the second instance, not the first">
                    <p>
                        The fire panel's demo-proxy endpoints in <code>gateway/app/main.py</code>{' '}
                        were one-off functions; adding access control's gave a second,
                        near-identical set — exactly the point where generalizing (one{' '}
                        <code>_proxy()</code> helper, one <code>postJson()</code> on the console
                        side) stops being premature and starts being the obvious move.
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why check a cardholder's schedule against the real clock instead of giving access control the same accelerated sim-time AHU-1 uses?"
                    a="Time acceleration exists to make an autonomous loop watchable in a demo. Access control has no loop — it only evaluates a rule at the moment a badge event happens — so there's nothing to accelerate and no reason to fake the clock a human reading the demo would find confusing."
                />
            </>
        )
    },
    {
        id: 'm6',
        navLabel: 'M6 · Alarms & work orders',
        status: 'done',
        heading: 'M6 · Alarm engine, history, work orders',
        tag: 'the gateway stops being a pipe and starts being operational',
        body: (
            <>
                <p>
                    Up to M5 the gateway only ever reflected what the field systems reported. M6
                    gives it its own logic layer: a rules engine that turns raw point state into
                    alarms with a real lifecycle, a SQLite trend store, and a CMMS-lite work order
                    queue an operator can create straight from an alarm.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="Four rules, one engine">
                        Fire condition ≠ normal (P1), a door forced or held open (P2), a fan
                        command/status mismatch (P2), and a sustained SAT deviation beyond a
                        deadband (P3) — all evaluated against the same point snapshot every
                        supervisor tick.
                    </ConceptCard>
                    <ConceptCard title="A real lifecycle, not a boolean">
                        <code>active_unacked → active_acked → cleared</code>. An operator
                        acknowledging an alarm doesn't make the underlying condition go away — it
                        just records that a human has seen it, same as a real annunciator panel.
                    </ConceptCard>
                    <ConceptCard title="Work orders as the alarm's exhaust">
                        An alarm is a symptom; a work order is the action taken about it. Creating
                        one from an alarm carries the asset and problem text forward so the link
                        back to "why does this work order exist" is never lost.
                    </ConceptCard>
                </div>

                <FieldNote title="the SAT-deviation rule needs two conditions, not one">
                    <p>
                        A single bad sample shouldn't page anyone — thermal systems have lag, and
                        the AHU-1 PI loop (M3) is expected to overshoot briefly during a setpoint
                        step. The rule only raises once the measured SAT has been outside a 2°C
                        deadband continuously for 30 seconds, tracked per-point with a "deviation
                        since" timestamp that resets the instant the point comes back inside the
                        deadband — so a loop that's merely still converging never fires a false
                        alarm.
                    </p>
                </FieldNote>

                <FieldNote title="an alarm that correctly never fired">
                    <p>
                        Live-testing the SAT rule by writing an aggressive setpoint step, the alarm
                        never raised. Not a bug: the M3 PI loop converged back inside the 2°C
                        deadband before the 30-second delay elapsed, which is exactly what a
                        well-tuned loop recovering from a legitimate setpoint change should do.
                        Trusting the 12-case unit suite (deadband-only, delay-only, timer-reset-on-
                        recovery, etc.) over a single live anecdote is what made it possible to tell
                        "no alarm" apart from "broken alarm" with confidence.
                    </p>
                </FieldNote>

                <FieldNote title="clearing an alarm doesn't delete it">
                    <p>
                        Each alarm key (e.g. <code>fire-panel.condition</code>) can only have one
                        <em> active</em> instance at a time, but a cleared alarm stays in history as
                        its own row — if the same condition re-raises later, it opens as a brand new
                        alarm <code>id</code> rather than resurrecting the old one. That's what lets
                        the alarm list double as an audit trail instead of just "current state."
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why does acknowledging an alarm not clear it?"
                    a="Ack and clear answer two different questions. Ack means a human has seen the alarm — it stops it from paging again, but the underlying condition (a zone still in alarm, a door still forced) hasn't changed. Clear means the engine re-evaluated the point and the condition is genuinely gone. Collapsing them would let someone silence an alarm and have the UI claim the problem is resolved when it isn't."
                />
            </>
        )
    },
    {
        id: 'm7',
        navLabel: 'M7 · Console shell',
        status: 'done',
        heading: 'M7 · Console shell, Overview, AHU-1 graphic',
        tag: 'one page becomes four tabs, each owning its own poll loop',
        body: (
            <>
                <p>
                    Through M6 this was one page plus Notes. M7 splits it into a real shell —
                    Overview, AHU-1, Operations, and this Notes tab — each with its own poll loop,
                    so a tab nobody has open isn't still hitting the gateway in the background.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="Overview, not a floor plan">
                        PLAN.md's Overview is an SVG floor plan colored by per-zone temperature. No
                        VAV zones exist (M2 simplified AHU-1 to one device, no VAV-101..104) —
                        there's no zone data to color a floor plan with. Overview shows the
                        building-level signals that do exist instead: occupancy, energy, alarm
                        count, fire condition, door status.
                    </ConceptCard>
                    <ConceptCard title="The schematic reads real point IDs">
                        <code>AhuGraphic.tsx</code> looks up every value by the same point id the
                        gateway's <code>/points</code> endpoint returns (
                        <code>ahu-1.oa_damper</code>, <code>ahu-1.fan_speed</code>, …) — it can't
                        quietly drift from what's actually polled the way a mock-data component
                        could.
                    </ConceptCard>
                    <ConceptCard title="Fan animation keys off status, not speed">
                        A real fan is either running or it isn't; speed only matters if it's
                        running. Driving the spin off the binary <code>fan_status</code> point means
                        the fire interlock (M4) visibly stops the graphic the instant status goes
                        inactive, not just the setpoint.
                    </ConceptCard>
                </div>

                <FieldNote title="an invisible fan blade that wasn't a bug">
                    <p>
                        A screenshot of the spinning fan occasionally rendered the blades as
                        entirely invisible instead of motion-blurred — a CSS-animation /
                        screenshot-timing interaction, not a rendering defect. Freezing the
                        animation before capturing showed the blades exactly as coded: correctly
                        colored, correctly centered. A live browser never hits this — only a single
                        frozen frame caught at the wrong instant can.
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why not fake four VAV zones just to build the floor plan PLAN.md describes?"
                    a="Because the floor plan's whole point is to show real per-zone temperature vs setpoint — data this lab never produces, since M2 deliberately scoped AHU-1 down to one device with no VAVs. Inventing zone numbers to fill a graphic would be decoration, not a simulation of anything. Overview shows what's actually live instead, and the simplification is written down rather than hidden."
                />
            </>
        )
    },
    {
        id: 'm8',
        navLabel: 'M8 · Console depth',
        status: 'done',
        heading: 'M8 · Alarms console, fire annunciator, access log, trends',
        tag: 'one flat Operations page becomes five dedicated views',
        body: (
            <>
                <p>
                    M7 built the shell; M8 gives each system the dedicated view PLAN.md describes
                    instead of one shared Operations page: a sortable alarms table, a real fire
                    panel annunciator, an access control event log, and a trend chart.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="A second event log, same shape as the first">
                        The fire panel never had an event history the way access control's{' '}
                        <code>access.py</code> always did. Adding{' '}
                        <code>Panel.events: list[PanelEvent]</code> copied that exact shape —
                        recognizing a second instance of a pattern beats inventing a new one.
                    </ConceptCard>
                    <ConceptCard title="Acknowledged/silenced aren't points">
                        The point model represents sensor/measured state. Whether an operator has
                        acknowledged the panel is panel UI state, not a point — so{' '}
                        <code>GET /fire-panel/panel</code> proxies the sim's full state directly
                        instead of forcing two booleans into the point shape.
                    </ConceptCard>
                    <ConceptCard title="A hand-rolled chart, not a library">
                        One series, a filled area, min/max labels, an emphasized last point — a few
                        dozen lines of SVG with no new dependency. A charting library earns its
                        place once there's a real need for multi-series overlays or zoom; nothing
                        here needs that yet.
                    </ConceptCard>
                </div>

                <FieldNote title="a bug only a real browser caught">
                    <p>
                        The gateway's <code>GET /history/&#123;point_id&#125;</code> returns each
                        sample as <code>&#123;value, timestamp&#125;</code>, but the console's type
                        was written against a guessed field name, <code>recorded_at</code>. Every
                        Python and console unit test passed — none of them touch the real JSON
                        crossing the wire — and the trend chart silently rendered as a flat{' '}
                        <code>NaN</code> path. Only opening the Trends tab in an actual browser and
                        reading the console surfaced it. Typing a fetch response isn't the same
                        claim as verifying it.
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why keep Work Orders on the Alarms tab instead of giving it the separate page PLAN.md describes?"
                    a="A work order's only real action right now is a status dropdown — there's no detail view substantial enough to earn its own page yet. Work orders are also created from alarms often enough that keeping them on one tab keeps that cause-and-effect visible without a tab switch. A dedicated page is the obvious next step once work orders grow real detail (notes, history, assignment)."
                />
            </>
        )
    },
    {
        id: 'm9',
        navLabel: 'M9 · Network page',
        status: 'done',
        heading: 'M9 · Network design page',
        tag: 'the one page documenting a system this lab never simulates',
        body: (
            <>
                <p>
                    Every other milestone simulates a real system. This one documents one that was
                    never going to be — the lab runs on a single flat Docker bridge on purpose, but
                    a real building's VLAN segmentation is exactly the Network+ knowledge this
                    project exists to show. <code>docs/network-design.md</code> was filled in with
                    real subnets, ports, and firewall rules instead of left as the TODO stub from
                    M0, and this page renders it directly.
                </p>
                <div className="concept-grid">
                    <ConceptCard title="Restricted vs. isolated">
                        BAS and Security each need one narrow path out (to the gateway, to the NVR)
                        — a firewall rule can name it precisely. Fire alarm monitoring in a real
                        building is often its own dedicated circuit, not a path through the data
                        network at all — a different kind of boundary, drawn with a different line
                        style in the diagram.
                    </ConceptCard>
                    <ConceptCard title="Static where it can't drift">
                        Field controllers, panels, and cameras run static IPs — a controller's
                        address can't drift out from under the supervisor polling it. DHCP is for
                        the one VLAN where devices actually come and go: IT/Corporate.
                    </ConceptCard>
                    <ConceptCard title="No new diagramming library">
                        Same call as the Trends chart (M8): five boxes and a few lines don't justify
                        a dependency. <code>NetworkDiagram.tsx</code> is dependency-free SVG, styled
                        through the same design tokens as the rest of the console.
                    </ConceptCard>
                </div>

                <FieldNote title="filling in the TODOs instead of leaving them">
                    <p>
                        PLAN.md originally suggested leaving the VLAN table as a draft for later. By
                        M9, every other doc in the repo had already been written out in full — a
                        half-finished network doc would have been the one inconsistent page. Filled
                        in with realistic, clearly-labeled values instead, the same way every prior
                        milestone's docs were.
                    </p>
                </FieldNote>

                <FlashCard
                    q="Why does a BACnet network need a BBMD when it spans more than one IP subnet?"
                    a="BACnet/IP devices discover each other with broadcast frames (Who-Is/I-Am), and IP broadcasts don't cross a routed subnet boundary — a router simply won't forward them. A BBMD (BACnet Broadcast Management Device) sits on each subnet and re-sends broadcasts it receives to the other BBMDs it's registered with, so devices on different subnets can still find each other. This lab's bas_net is one flat subnet, so it never needed one — but a real building with controllers split across multiple mechanical-room subnets does."
                />
            </>
        )
    },
    {
        id: 'later',
        navLabel: 'M10 · Final write-up',
        status: 'next',
        heading: 'M10 · Everything after that',
        tag: 'one line, so the shape of the build stays visible',
        body: (
            <div className="teaser-list">
                <div className="teaser">
                    <span className="t-id">M10</span>
                    <div>
                        <h3>Final write-up</h3>
                        <p>
                            README polish, a demo video script, and the resume-ready project
                            summary.
                        </p>
                    </div>
                </div>
            </div>
        )
    }
];

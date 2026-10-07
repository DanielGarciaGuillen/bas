# LinkedIn Post Draft

Short draft for announcing the project. Edit the tone to match how Daniel actually talks
before posting — this is a starting point, not a final copy.

---

Built a small building automation system this month — mostly to prove to myself (and
anyone hiring) that I can actually work with the protocols and systems this field runs on,
not just read about them.

**BuildingOps Lab** is a simulated small office building: an HVAC unit speaking real
BACnet/IP with a PI-loop sequence of operation, an energy meter over Modbus TCP, a fire
alarm panel whose alarm genuinely shuts the AHU's fan down through a BACnet priority
override, and an access control system with door/cardholder logic. A gateway normalizes
all four into one point model, runs an alarm engine with history and work orders, and a
React console ties it together — nine tabs, live values, real writes back to the
simulated BACnet device.

Everything's simulated (no real equipment, obviously), but the protocols, the control
logic, and the interlock are real — same BACnet priority-array mechanism a Siemens or JCI
controller uses on an actual job, same reason a fire alarm panel shuts HVAC down.

I'm moving from 7 years of React/React Native work into building automation, fire alarm,
and low-voltage systems in Ottawa–Gatineau (currently working through CompTIA Network+ and
the CFAA Fire Alarm Technician program), and this was the project to prove the two halves
connect: the software background and the controls domain.

Repo + full writeup: [link]

#buildingautomation #bacnet #hvac #firealarm #reactjs #networkplus

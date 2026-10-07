# Demo Video Script (2–3 minutes)

A shot list for a screen-recorded walkthrough — not a script to read verbatim, a sequence
to follow while narrating naturally. Each beat names what's on screen and the one sentence
worth saying over it.

## Setup (before recording)

```
docker compose up --build modbus-meter bacnet-devices fire-panel access-control gateway console
```

Wait for `http://localhost:5173` to load with live values (should be well under 30s).

## Shot list

**1. Overview (10s)**
Land on the Overview tab. *"This is BuildingOps Lab — a simulated small office building:
HVAC, an energy meter, a fire alarm panel, and access control, talking real industrial
protocols, normalized by a gateway, and surfaced through this console."*

**2. AHU-1 (25s)**
Click AHU-1. Point out the live schematic — OA damper, coils, the spinning fan, SAT vs.
setpoint. Change the setpoint field and submit. *"That write goes out over real BACnet/IP
to a simulated AHU-1 device — same protocol a Siemens or JCI controller speaks on site."*
Watch the SAT value drift toward the new setpoint over the next few seconds (the PI loop
is real, not scripted).

**3. Fire Panel — the money shot (35s)**
Click Fire Panel. Click "Trigger Zone 4 Alarm". Narrate the chain live:
- The zone LED goes red, panel condition flips to ALARM
- Switch to AHU-1: the fan stops, OA damper closes to 0% — *"the fire alarm just took
  AHU-1 offline via a real BACnet priority override, exactly how a fire-alarm-to-HVAC
  interlock works on a real job"*
- Back on Fire Panel: click Acknowledge, then Silence
- Click "Clear & Reset Panel" — note the panel refuses to reset if a zone is still live;
  this demo clears the field first, so reset succeeds
- Back on AHU-1: the fan resumes — control returns to the normal schedule automatically

**4. Access Control (20s)**
Click Access. Badge in as a cardholder who's denied (wrong level or wrong schedule),
then one who's granted. Click "Force Door". Point at the event log updating live and the
door tile turning red. *"Forced and held-open doors raise a real alarm — same engine as
the fire panel."*

**5. Alarms + Work Orders (20s)**
Click Alarms. Point at the alarm from the door force, sort by priority. Click "Work Order"
on it. Scroll to Work Orders below — the new one appears, linked back to the alarm, next
to the two seeded preventive-maintenance items (filter change, annual fire inspection).

**6. Trends (15s)**
Click Trends. Switch the point selector to the energy meter. *"Every numeric point gets
written to a SQLite trend table every few seconds — pick any point, any range."*

**7. Network (15s)**
Click Network. *"The lab itself runs on one flat Docker network for simplicity, but this
page documents the real multi-VLAN design a building like this would actually use —
BAS, security, and fire alarm traffic segmented and firewalled from each other."*

**8. Close (10s)**
Click Notes. *"Every milestone's engineering notes — what broke, what I simplified and
why, written down as I built it — live right here in the app, and in docs/ in the repo."*

## Recording notes

- 1280×800 browser window reads cleanly at 1080p without cropping any tab's content.
- Pause ~2s after each click before narrating — gives the poll loop (2.5s) time to catch
  up so the screen recording shows the *result*, not the stale state.
- The whole loop (trigger → interlock → ack → silence → reset) takes about 15 real
  seconds end to end; no need to speed up or cut.

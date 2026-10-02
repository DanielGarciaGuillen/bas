# Modbus Register Map — Energy Meter

## M1 (current)

| Register | Function code | Address | Type | Scale | Units | Description |
|---|---|---|---|---|---|---|
| kW total | Read Input Registers (0x04) | 0 | uint16 | x10 | kW | Instantaneous total real power. `register / 10 = kW` |

## Planned (not yet implemented)

Voltage, current, power factor, and cumulative kWh were scoped in the original brief but
cut for M1 to keep the first end-to-end pipeline (device → gateway → API) as simple as
possible to build and verify. Adding them back is just more registers in the same pattern:

| Register | Function code | Scale | Units |
|---|---|---|---|
| Voltage (L-N avg) | Read Input Registers (0x04) | x10 | V |
| Current (avg) | Read Input Registers (0x04) | x100 | A |
| Power factor | Read Input Registers (0x04) | x1000 | — |
| kWh total | Read Holding Registers (0x03) | none (uint32 across 2 registers) | kWh |

## Implementation notes

- Simulator: `sims/modbus_meter/main.py`. Gateway decode: `gateway/app/main.py` (`decode_kw`).
- Library: **pymodbus 3.8.6**, pinned deliberately. The current release line (3.15.x at
  time of writing) replaced the classic `ModbusSlaveContext`/`ModbusSequentialDataBlock`
  API with a new `SimData`/`SimDevice` model built for a different (config-driven
  simulator) use case, and its `ModbusServerContext.async_setValues` doesn't support
  mutating a plain device context at runtime. 3.8.6 is the last broadly-documented release
  with the simple, stable, imperative datastore API this project needs.
- Addressing quirk: `ModbusSlaveContext.getValues`/`setValues` always add 1 to the
  requested address before indexing into the underlying data block (this appears to assume
  1-based "40001-style" addressing). A data block therefore needs one extra slot beyond
  the highest address it serves, or reads at the top of the range raise an
  `IllegalAddress` exception. See `build_context()` in the simulator.

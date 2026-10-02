# Modbus Register Map — Energy Meter

_Status: stub — to be filled in during M1 once `sims/modbus_meter` is implemented._

| Register | Type | Address | Scale | Units | Description |
|---|---|---|---|---|---|
| kW (total) | Input | TODO | TODO | kW | Instantaneous total real power |
| kWh (total) | Holding | TODO | TODO | kWh | Cumulative energy |
| Voltage (L-N avg) | Input | TODO | TODO | V | |
| Current (avg) | Input | TODO | TODO | A | |
| Power factor | Input | TODO | TODO | — | |

Notes:
- TODO: document the function codes used (Read Holding Registers `0x03`, Read Input
  Registers `0x04`), byte order, and any scaling factors applied.

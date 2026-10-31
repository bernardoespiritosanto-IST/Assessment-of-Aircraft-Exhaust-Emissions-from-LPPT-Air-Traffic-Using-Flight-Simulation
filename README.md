# PMS vs CDA Approach Emissions at LPPT — Source Code

Source code for the MSc dissertation (Instituto Superior Técnico, Universidade de Lisboa) comparing the environmental footprint of Point Merge System (PMS) and Continuous Descent Approach (CDA) arrivals at Lisbon Humberto Delgado Airport (LPPT).

## Scripts

| File | Description |
|---|---|
| `opensky_traffic_extraction.py` | Extracts historical arrival traffic from the OpenSky Network, computes kinematic state vectors, estimates performance and emissions with OpenAP, and merges IEM ASOS weather data (temperature, wind). |
| `xplane_bffm2_emissions.py` | Processes the 1.0 Hz X-Plane 11 telemetry, isolates the approach below 15,000 ft and applies the Boeing Fuel Flow Method 2 (BFFM2) with ICAO EEDB data for the CFM LEAP-1A26 to compute CO2, H2O, SOx, NOx, CO and HC emissions. |

## Engine data

ICAO Engine Emissions Databank (Issue 32), CFM LEAP-1A26/26E1 (UID 20CM089) and LEAP-1A26CJ (UID 20CM091):

| | Idle (7%) | Approach (30%) | Climb-Out (85%) | Take-Off (100%) |
|---|---|---|---|---|
| Fuel flow (kg/s) | 0.091 | 0.244 | 0.710 | 0.861 |
| EI HC (g/kg) | 0.29 | 0.04 | 0.02 | 0.02 |
| EI CO (g/kg) | 21.63 | 2.65 | 0.26 | 0.24 |
| EI NOx (g/kg) | 4.61 | 8.75 | 13.38 | 30.80 |

## Requirements

Python 3, NumPy, pandas, matplotlib, traffic, OpenAP (see the imports at the top of each script).

## Notes

The OpenSky script needs your own OpenSky Network credentials; the password in the code is masked.

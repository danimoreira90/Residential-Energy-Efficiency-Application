"""Solar PV sizing, irradiance modeling, and payback simulation.

Sprint 3 adds:
- irradiance.py — NASA POWER API client; produces TMY data for pvlib.
- sizing.py     — pvlib ModelChain → estimated kWp and monthly generation.
- payback.py    — Year-by-year ROI with Lei 14.300 Fio B schedule baked in.
- catalog.py    — Common Brazilian panel/inverter defaults for sizing math.
"""

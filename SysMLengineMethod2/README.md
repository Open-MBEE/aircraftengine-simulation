# SysML engine — FPB method 2 (metadata binding)

The whole design-point cycle of [main.py](../main.py) as one SysML v2
**Functional Process Block**, executed by a Service Binding Manager (SBM)
using fpb-demo's binding approach 2: `@ServiceBinding` / `@ParameterBinding`
annotations in the model name the Python function (`main.run_cycle`) and
its keyword arguments.

## Run

From the repository root (so `main` imports):

```
python -m SysMLengineMethod2.sbm list
python -m SysMLengineMethod2.sbm invoke AircraftEngineCycleFPB::cruise
python -m SysMLengineMethod2.sbm invoke AircraftEngineCycleFPB::hotDayCruise
python -m SysMLengineMethod2.sbm invoke AircraftEngineCycleFPB::highPressureRatioCruise
python -m SysMLengineMethod2.sbm invoke AircraftEngineCycleFPB::cruise --set alt_ft=35000 --set Ma0=0.8
python -m SysMLengineMethod2.sbm invoke AircraftEngineCycleFPB::cruise --set verbose=true
```

`cruise` reproduces `python main.py` (F = 16.83 kN, TSFC = 27.50 g/(kN·s)).

## Dashboards

Both run every simulation through the SBM (method 2) and read their inputs,
model values and outputs from the model. Start from the repository root:

```
python SysMLengineMethod2/cycle_dashboard/server.py   # all stations  -> http://localhost:5002
python SysMLengineMethod2/dashboard/server.py         # station 1     -> http://localhost:5001
```

The all-stations dashboard exposes only the user-modifiable inputs of
`CycleService` (the design point and the optional `T0` override; run
controls such as `verbose` are hidden and refused by the server) and shows
performance plus every station's values, each with its change vs the model.

## Layout

- [model/EngineCycleFPB.sysml](model/EngineCycleFPB.sysml) — `CycleService`,
  the FPB: all 16 `run_cycle()` design parameters as `in` parameters with
  main.py's defaults, an optional `T0 : Real[0..1]` (→ `T0_override`;
  unbound means standard atmosphere), `verbose` (default `false`), and 11
  `out` parameters (thrust breakdown, TSFC, efficiencies, flows, Tt4). Three
  usages: `cruise`, `hotDayCruise` (ISA + 15 K), `highPressureRatioCruise`.
- [model/Station1FPB.sysml](model/Station1FPB.sysml) — station 1 only
  (captured stream tube): `CapturedStreamTube`, bound to
  `main.captured_stream_tube(rho0, u0, Do)` → `A1`, `dotm1`, with usage
  `cruiseStation1` (design-point station-0 values). Run with
  `python -m SysMLengineMethod2.sbm invoke AircraftEngineStation1FPB::cruiseStation1`.
- [model/FPBCore.sysml](model/FPBCore.sysml) — FPB library (base action def
  and the binding metadata defs), copied from fpb-demo.
- [sbm/](sbm/) — copy of fpb-demo's mock SBM, extended with `--model-dir`
  and optional (`[0..1]`) parameters that may stay unbound.

The native, station-by-station model remains in
[../model/EngineCycle.sysml](../model/EngineCycle.sysml) (not executed).

## Limitations

- The cycle is one black-box service; the individual stations are not
  separate FPBs.
- The SBM uses fpb-demo's regex mini-parser, not a real SysML v2 parser;
  usage values must be literals.

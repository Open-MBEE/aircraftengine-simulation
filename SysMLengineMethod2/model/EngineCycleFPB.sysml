package AircraftEngineCycleFPB {
	doc /* Executable counterpart to EngineCycle.sysml: the whole design-point
	     * cycle as a single Functional Process Block (see FPBCore.sysml),
	     * realized by main.run_cycle() and bound through model metadata
	     * (fpb-demo binding approach 2). A Service Binding Manager reads the
	     * @ServiceBinding / @ParameterBinding annotations, collects the
	     * parameter values from a usage, calls run_cycle() and reads the out
	     * parameters back from the dict it returns.
	     *
	     * Every run_cycle() argument is exposed as an in parameter, with
	     * main.py's default as the parameter default, so a usage only
	     * redefines what it changes. A parameter without @ParameterBinding
	     * is passed under its own name; only T0 is renamed.
	     *
	     * The station-by-station structure stays in ../../model/EngineCycle.sysml
	     * as native, non-executed documentation; this package treats the
	     * cycle as one black-box service.
	     *
	     * Run from the repository root (so 'main' imports), e.g.:
	     *   python -m SysMLengineMethod2.sbm invoke AircraftEngineCycleFPB::hotDayCruise
	     */

	private import ScalarValues::*;
	private import FPBCore::*;

	action def CycleService :> FunctionalProcessBlock {
		@ServiceBinding {
			lang = "python";
			module = "main";
			function = "run_cycle";
		}

		// flight condition
		in alt_ft : Real = 40e3;        // cruise altitude, ft
		in Ma0 : Real = 0.85;           // cruise Mach number

		// geometry
		in Do : Real = 0.75;            // compressor face outer diameter, m
		in Di : Real = 0.05;            // inlet cone diameter, m
		in AR : Real = 2.25;            // compressor area contraction A2/A3

		// compressor
		in OPR : Real = 25;             // overall pressure ratio pt3/pt2
		in eta_comp : Real = 0.88;      // isentropic efficiency
		in mu_bypass : Real = 0.3;      // bypass fraction of compressor exit flow
		in mu_cool : Real = 0.01;       // turbine cooling fraction of inlet flow
		in mu_bleed : Real = 0.005;     // cabin bleed fraction of inlet flow

		// combustor
		in eta_comb : Real = 0.95;      // combustion efficiency
		in FAR : Real = 0.02;           // fuel-air ratio of the core stream
		in k_aer : Real = 10.0;         // aerodynamic (cold) pressure loss parameter
		in k_th : Real = 0.5;           // fundamental (hot) pressure loss parameter

		// turbine and shaft
		in eta_turb : Real = 0.86;      // isentropic efficiency
		in eta_shaft : Real = 0.98;     // mechanical efficiency of the shaft

		// optional free-stream static temperature, K; left unbound, the
		// standard atmosphere at alt_ft applies
		in T0 : Real[0..1] {
			@ParameterBinding { pythonName = "T0_override"; }
		}

		// print main.py's station-by-station report while running
		in verbose : Boolean = false;

		// every value run_cycle() returns, station by station (SI units:
		// K, Pa, kg/m^3, m/s, m^2, kg/s, W, N)

		// station 0 : free stream
		out T0_used : Real {            // static temperature actually used, K
			@ParameterBinding { pythonName = "T0"; }   // 'T0' is taken by the input
		}
		out p0 : Real;
		out rho0 : Real;
		out u0 : Real;
		out Tt0 : Real;
		out pt0 : Real;

		// station 1 : captured stream tube
		out A1 : Real;
		out dotm1 : Real;               // captured air mass flow

		// station 2 : compressor face
		out A2 : Real;
		out T2 : Real;
		out p2 : Real;
		out Ma2 : Real;
		out Tt2 : Real;
		out pt2 : Real;

		// station 3 : compressor exit
		out A3 : Real;
		out T3 : Real;
		out p3 : Real;
		out Ma3 : Real;
		out Tt3 : Real;
		out pt3 : Real;
		out Wcomp : Real;               // compressor power

		// station 4 : combustor exit
		out A4 : Real;
		out T4 : Real;
		out p4 : Real;
		out Ma4 : Real;
		out Tt4 : Real;                 // turbine inlet total temperature
		out pt4 : Real;
		out dotmf : Real;               // fuel flow

		// station 5 : turbine exit
		out Tt5 : Real;
		out pt5 : Real;
		out Wshaft : Real;              // shaft power

		// station 7 : core nozzle throat
		out A7 : Real;
		out T7 : Real;
		out p7 : Real;
		out u7 : Real;

		// station 9 : core nozzle exit
		out A9 : Real;
		out T9 : Real;
		out p9 : Real;
		out u9 : Real;

		// station 3b : bypass nozzle exit
		out A9b : Real;
		out T9b : Real;
		out u9b : Real;
		out dotm_byp : Real;            // bypass mass flow

		// performance
		out F : Real;                   // net thrust
		out F_core : Real;              // gross thrust, core
		out F_byp : Real;               // gross thrust, bypass
		out F_ram : Real;               // ram drag
		out TSFC : Real;                // thrust specific fuel consumption, g/(kN s)
		out eta_th : Real;              // thermal efficiency
		out eta_p : Real;               // propulsive efficiency
		out eta_o : Real;               // overall efficiency
	}

	// the main.py design point, every parameter at its default
	action cruise : CycleService { }

	action hotDayCruise : CycleService {
		in :>> T0 = 231.65;             // ISA + 15 K at 40,000 ft
	}

	action highPressureRatioCruise : CycleService {
		in :>> OPR = 35;
		in :>> FAR = 0.022;
	}
}

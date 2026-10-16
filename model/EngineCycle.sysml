package AircraftEngineCycle {
	doc /* SysML v2 counterpart to main.py: a design-point cycle deck for a
	     * single-shaft jet engine with bleed air, turbine cooling and a
	     * bypass stream. Station numbering, symbols and the order of
	     * computation follow main.py exactly (SAE ARP 755A; stations 6 and 8
	     * are skipped on purpose). Each station is its own 'calc def' (a
	     * pure, closed-form mapping from inputs to outputs) or, where
	     * main.py has a visible iteration of its own (station 7), an
	     * 'action def' with a loop.
	     *
	     * Conventions:
	     *  - GasProperties stands in for pygasturb's Gas and Atmosphere
	     *    classes: signatures only, no polynomial/Newton-solver bodies,
	     *    since this model documents the cycle's data flow, not the gas
	     *    correlations themselves (see pygasturb/gas.py,
	     *    pygasturb/atmosphere.py).
	     *  - A GasProperties calc with exactly one 'out' is invoked directly
	     *    as a function, e.g. 'Enthalpy( T0 )'. One with several 'out's
	     *    is bound as a named nested usage and read back by name, e.g.
	     *    'calc s : StaticFromTotal { ... } ... s.T'.
	     *  - '**0.5' stands in for sqrt, so no built-in beyond arithmetic is
	     *    assumed.
	     *  - Station 7's 'while' loop and the choke-check 'assert' are
	     *    stylized to show main.py's one explicit, visible iteration and
	     *    its guard; every other iteration (Newton solves inside
	     *    GasProperties) stays hidden, exactly as it is opaque to
	     *    main.py.
	     *
	     * Illustrative: nothing executes the station calcs or EngineCycle.
	     * The one exception is CycleService at the end of the package, a
	     * Functional Process Block (see FPBCore.sysml) bound to
	     * main.run_cycle() through model metadata, which a Service Binding
	     * Manager can invoke.
	     */

	private import ScalarValues::*;
	private import FPBCore::*;

	attribute pi : Real = 3.14159265358979323846;

	// ====================================================================
	// Design parameters -- literal values taken directly from main.py
	// ====================================================================
	part def DesignPoint {
		// flight condition
		attribute alt_ft : Real = 40e3;     // cruise altitude in ft
		attribute Ma0 : Real = 0.85;        // cruise Mach number

		// geometry
		attribute Do : Real = 0.75;         // compressor face outer diameter, m
		attribute Di : Real = 0.05;         // inlet cone diameter, m
		attribute AR : Real = 2.25;         // compressor area contraction A2/A3

		// compressor
		attribute OPR : Real = 25;          // overall pressure ratio pt3/pt2
		attribute eta_comp : Real = 0.88;   // isentropic efficiency
		attribute mu_bypass : Real = 0.3;   // bypass fraction of compressor exit flow
		attribute mu_cool : Real = 0.01;    // turbine cooling fraction of inlet flow
		attribute mu_bleed : Real = 0.005;  // cabin bleed fraction of inlet flow

		// combustor
		attribute eta_comb : Real = 0.95;   // combustion efficiency
		attribute FAR : Real = 0.02;        // fuel-air ratio of the core stream
		attribute k_aer : Real = 10.0;      // aerodynamic (cold) pressure loss parameter
		attribute k_th : Real = 0.5;        // fundamental (hot) pressure loss parameter

		// turbine and shaft
		attribute eta_turb : Real = 0.86;   // isentropic efficiency
		attribute eta_shaft : Real = 0.98;  // mechanical efficiency of the shaft
	}

	// ====================================================================
	// Gas property model -- stands in for pygasturb.Gas / pygasturb.Atmosphere
	// ====================================================================
	package GasProperties {

		attribute Hu : Real = 42.8e6;   // lower heating value of kerosene, J/kg

		calc def StandardAtmosphere {           // Atmosphere.atm
			in altitude_m : Real;
			out T : Real;
			out p : Real;
			out rho : Real;
		}

		calc def SpeedOfSound {                 // Gas.c
			in T : Real;
			in FAR : Real = 0.0;
			out c : Real;
		}

		calc def Enthalpy {                     // Gas.h
			in T : Real;
			in FAR : Real = 0.0;
			out h : Real;
		}

		calc def TemperatureFromEnthalpy {       // Gas.T (inverse of Enthalpy)
			in h : Real;
			in FAR : Real = 0.0;
			out T : Real;
		}

		calc def Gamma {                        // Gas.gamma
			in T : Real;
			in FAR : Real = 0.0;
			out gamma : Real;
		}

		calc def GasConstant {                  // Gas.R
			in FAR : Real = 0.0;
			out R : Real;
		}

		calc def Density {                      // Gas.rho
			in T : Real;
			in p : Real;
			in FAR : Real = 0.0;
			out rho : Real;
		}

		calc def IsentropicPressure {           // Gas.isenp
			in T0 : Real;
			in p0 : Real;
			in T1 : Real;
			in FAR : Real = 0.0;
			out p1 : Real;
		}

		calc def IsentropicTemperature {        // Gas.isenT
			in T0 : Real;
			in p0 : Real;
			in p1 : Real;
			in FAR : Real = 0.0;
			out T1 : Real;
		}

		calc def Compress {                     // Gas.compress -- isentropic contraction, A2 <= A1
			in T1 : Real;
			in p1 : Real;
			in u1 : Real;
			in A1 : Real;
			in A2 : Real;
			in FAR : Real = 0.0;
			out T2 : Real;
			out p2 : Real;
			out u2 : Real;
		}

		calc def Compressor {                   // Gas.compressor -- pressure-ratio compression
			in T1 : Real;
			in p1 : Real;
			in PR : Real;
			in eta : Real = 1.0;
			in FAR : Real = 0.0;
			out T2 : Real;
			out p2 : Real;
			out w : Real;
		}

		calc def StaticFromTotal {              // Gas.static_from_total
			in Tt : Real;
			in pt : Real;
			in dotm : Real;
			in A : Real;
			in FAR : Real = 0.0;
			out T : Real;
			out p : Real;
			out u : Real;
			out Ma : Real;
		}
	}

	private import GasProperties::*;

	// ====================================================================
	// station 0 : free stream
	// ====================================================================
	calc def Station0_FreeStream {
		in alt_ft : Real;
		in Ma0 : Real;

		calc state : StandardAtmosphere {
			in :>> altitude_m = alt_ft * 0.3048;
		}
		out T0 : Real = state.T;
		out p0 : Real = state.p;
		out rho0 : Real = state.rho;

		out u0 : Real = Ma0 * SpeedOfSound( T0 );
		out h0 : Real = Enthalpy( T0 );
		out ht0 : Real = h0 + 0.5 * u0**2;
		out Tt0 : Real = TemperatureFromEnthalpy( ht0 );
		out pt0 : Real = IsentropicPressure( T0, p0, Tt0 );
	}

	// ====================================================================
	// station 1 : captured stream tube
	// ====================================================================
	calc def Station1_CapturedStreamTube {
		in rho0 : Real;
		in u0 : Real;
		in Do : Real;

		out A1 : Real = 0.25 * pi * Do**2;
		out dotm1 : Real = rho0 * u0 * A1;
	}

	// ====================================================================
	// station 2 : compressor face
	// ====================================================================
	calc def Station2_CompressorFace {
		in T0 : Real;
		in p0 : Real;
		in u0 : Real;
		in A1 : Real;
		in Di : Real;
		in Tt0 : Real;
		in ht0 : Real;
		in pt0 : Real;

		out A2 : Real = A1 - 0.25 * pi * Di**2;

		calc contraction : Compress {
			in :>> T1 = T0;
			in :>> p1 = p0;
			in :>> u1 = u0;
			in :>> A1 = A1;
			in :>> A2 = A2;
		}
		out T2 : Real = contraction.T2;
		out p2 : Real = contraction.p2;
		out u2 : Real = contraction.u2;
		out Ma2 : Real = u2 / SpeedOfSound( T2 );

		// inlet is adiabatic and lossless: total state is preserved
		out Tt2 : Real = Tt0;
		out ht2 : Real = ht0;
		out pt2 : Real = pt0;
	}

	// ====================================================================
	// station 3 : compressor exit
	// ====================================================================
	calc def Station3_CompressorExit {
		in Tt2 : Real;
		in pt2 : Real;
		in ht2 : Real;
		in OPR : Real;
		in eta_comp : Real;
		in dotm1 : Real;
		in mu_cool : Real;
		in mu_bleed : Real;
		in mu_bypass : Real;
		in A2 : Real;
		in AR : Real;

		calc comp : Compressor {
			in :>> T1 = Tt2;
			in :>> p1 = pt2;
			in :>> PR = OPR;
			in :>> eta = eta_comp;
		}
		out Tt3 : Real = comp.T2;
		out pt3 : Real = comp.p2;
		out ht3 : Real = Enthalpy( Tt3 );

		// bleed and cooling air are extracted halfway through the compression
		out ht3c : Real = ht2 + 0.5 * comp.w;

		out dotm_cool : Real = mu_cool * dotm1;
		out dotm_bleed : Real = mu_bleed * dotm1;
		out dotm3 : Real = dotm1 - dotm_cool - dotm_bleed;
		out Wcomp : Real = ( dotm1 + dotm3 ) * 0.5 * comp.w;

		out A3 : Real = A2 / AR;
		calc s : StaticFromTotal {
			in :>> Tt = Tt3;
			in :>> pt = pt3;
			in :>> dotm = dotm3;
			in :>> A = A3;
		}
		out T3 : Real = s.T;
		out p3 : Real = s.p;
		out u3 : Real = s.u;
		out Ma3 : Real = s.Ma;

		// the bypass stream splits off here, areas in proportion to mass flow
		out dotm_byp : Real = mu_bypass * dotm3;
		out dotm_core : Real = dotm3 - dotm_byp;
		out A3a : Real = A3 * dotm_core / dotm3;
		out A3b : Real = A3 - A3a;
	}

	// ====================================================================
	// station 4 : combustor exit
	// ====================================================================
	calc def Station4_CombustorExit {
		in dotm_core : Real;
		in FAR : Real;
		in ht3 : Real;
		in eta_comb : Real;
		in Tt3 : Real;
		in pt3 : Real;
		in A3a : Real;
		in k_aer : Real;
		in k_th : Real;

		out dotmf : Real = FAR * dotm_core;
		out dotm4 : Real = dotm_core + dotmf;

		// energy balance: combustion efficiency acts on the heat release only
		out ht4 : Real = ( ht3 + eta_comb * Hu * FAR ) / ( 1.0 + FAR );
		out Tt4 : Real = TemperatureFromEnthalpy( ht4, FAR );

		out A4 : Real = A3a;
		// X^2 is roughly gamma * Ma^2 at the burner inlet
		out X : Real = dotm_core * ( GasConstant() * Tt3 )**0.5 / ( pt3 * A4 );
		out pt4 : Real = pt3 * ( 1.0 - X*X * ( k_aer + k_th * ( Tt4/Tt3 - 1.0 ) ) );

		calc s : StaticFromTotal {
			in :>> Tt = Tt4;
			in :>> pt = pt4;
			in :>> dotm = dotm4;
			in :>> A = A4;
			in :>> FAR = FAR;
		}
		out T4 : Real = s.T;
		out p4 : Real = s.p;
		out u4 : Real = s.u;
		out Ma4 : Real = s.Ma;
	}

	// ====================================================================
	// station 5 : turbine exit
	// ====================================================================
	calc def Station5_TurbineExit {
		in dotm4 : Real;
		in dotm_cool : Real;
		in ht4 : Real;
		in ht3c : Real;
		in dotmf : Real;
		in Wcomp : Real;
		in eta_shaft : Real;
		in eta_turb : Real;
		in pt4 : Real;

		// cooling air mixes in ahead of the turbine at constant total pressure
		out dotm5 : Real = dotm4 + dotm_cool;
		out ht4m : Real = ( dotm4 * ht4 + dotm_cool * ht3c ) / dotm5;
		out FAR5 : Real = dotmf / ( dotm5 - dotmf );
		out Tt4m : Real = TemperatureFromEnthalpy( ht4m, FAR5 );

		// the turbine drives the compressor through the shaft
		out Wshaft : Real = Wcomp / eta_shaft;
		out ht5 : Real = ht4m - Wshaft / dotm5;
		out Tt5 : Real = TemperatureFromEnthalpy( ht5, FAR5 );

		// isentropic efficiency sets the price in pressure
		out ht5s : Real = ht4m - ( ht4m - ht5 ) / eta_turb;
		out Tt5s : Real = TemperatureFromEnthalpy( ht5s, FAR5 );
		out pt5 : Real = IsentropicPressure( Tt4m, pt4, Tt5s, FAR5 );
	}

	// ====================================================================
	// station 7 : core nozzle throat -- the one solve main.py iterates
	// visibly (a fixed-point loop), with a guard against an unchoked
	// nozzle. Modeled as an action, not a calc, for exactly that reason.
	// ====================================================================
	action def Station7_CoreNozzleThroat {
		in Tt5 : Real;
		in pt5 : Real;
		in ht5 : Real;
		in FAR5 : Real;
		in p0 : Real;
		in dotm5 : Real;
		out T7 : Real;
		out u7 : Real;
		out p7 : Real;
		out A7 : Real;

		attribute gam5 : Real = Gamma( Tt5, FAR5 );
		attribute p_crit : Real =
			pt5 / ( 1.0 + 0.5*( gam5 - 1.0 ) )**( gam5/( gam5 - 1.0 ) );

		assert constraint nozzleIsChoked {
			doc /* main.py raises if this does not hold: the core nozzle
			     * must be choked for the sonic-throat assumption below. */
			p_crit >= p0
		}

		// fixed-point iteration solving h(T7) + c(T7)^2/2 = ht5
		attribute T7_iter : Real = Tt5 / ( 1.0 + 0.5 * ( gam5 - 1.0 ) );
		attribute Told : Real = 0.0;
		attribute u7_iter : Real;

		while abs( T7_iter - Told ) > 1e-6 {
			assign Told := T7_iter;
			assign u7_iter := SpeedOfSound( T7_iter, FAR5 );
			assign T7_iter := TemperatureFromEnthalpy( ht5 - 0.5 * u7_iter**2, FAR5 );
		}

		assign T7 := T7_iter;
		assign u7 := u7_iter;
		assign p7 := IsentropicPressure( Tt5, pt5, T7, FAR5 );
		assign A7 := dotm5 / ( Density( T7, p7, FAR5 ) * u7 );
	}

	// ====================================================================
	// station 9 : core nozzle exit
	// ====================================================================
	calc def Station9_CoreNozzleExit {
		in Tt5 : Real;
		in pt5 : Real;
		in ht5 : Real;
		in FAR5 : Real;
		in p0 : Real;
		in dotm5 : Real;

		// adapted nozzle: expand isentropically to ambient pressure
		out p9 : Real = p0;
		out T9 : Real = IsentropicTemperature( Tt5, pt5, p9, FAR5 );
		out u9 : Real = ( 2.0 * ( ht5 - Enthalpy( T9, FAR5 ) ) )**0.5;
		out A9 : Real = dotm5 / ( Density( T9, p9, FAR5 ) * u9 );
		out Ma9 : Real = u9 / SpeedOfSound( T9, FAR5 );
	}

	// ====================================================================
	// bypass nozzle exit (station "3b")
	// ====================================================================
	calc def BypassNozzleExit {
		in Tt3 : Real;
		in pt3 : Real;
		in ht3 : Real;
		in p0 : Real;
		in dotm_byp : Real;

		out T9b : Real = IsentropicTemperature( Tt3, pt3, p0 );
		out u9b : Real = ( 2.0 * ( ht3 - Enthalpy( T9b ) ) )**0.5;
		out A9b : Real = dotm_byp / ( Density( T9b, p0 ) * u9b );
	}

	// ====================================================================
	// performance
	// ====================================================================
	calc def Performance {
		in dotm5 : Real;
		in u9 : Real;
		in A9 : Real;
		in p9 : Real;
		in p0 : Real;
		in dotm_byp : Real;
		in u9b : Real;
		in dotm1 : Real;
		in u0 : Real;
		in dotmf : Real;

		// both nozzles are adapted, so there is no pressure thrust; ram
		// drag is charged on the full captured flow (includes bleed air)
		out F_core : Real = dotm5 * u9 + A9 * ( p9 - p0 );
		out F_byp : Real = dotm_byp * u9b;
		out F_ram : Real = dotm1 * u0;
		out F : Real = F_core + F_byp - F_ram;

		out dKE : Real = 0.5 * ( dotm5 * u9**2 + dotm_byp * u9b**2 ) - 0.5 * dotm1 * u0**2;
		out eta_th : Real = dKE / ( dotmf * Hu );
		out eta_p : Real = F * u0 / dKE;
		out eta_o : Real = eta_th * eta_p;
	}

	// ====================================================================
	// the whole cycle, station usages wired exactly as in main.py
	// ====================================================================
	action def EngineCycle {
		in design : DesignPoint;

		calc s0 : Station0_FreeStream {
			in :>> alt_ft = design.alt_ft;
			in :>> Ma0 = design.Ma0;
		}

		calc s1 : Station1_CapturedStreamTube {
			in :>> rho0 = s0.rho0;
			in :>> u0 = s0.u0;
			in :>> Do = design.Do;
		}

		calc s2 : Station2_CompressorFace {
			in :>> T0 = s0.T0;
			in :>> p0 = s0.p0;
			in :>> u0 = s0.u0;
			in :>> A1 = s1.A1;
			in :>> Di = design.Di;
			in :>> Tt0 = s0.Tt0;
			in :>> ht0 = s0.ht0;
			in :>> pt0 = s0.pt0;
		}

		calc s3 : Station3_CompressorExit {
			in :>> Tt2 = s2.Tt2;
			in :>> pt2 = s2.pt2;
			in :>> ht2 = s2.ht2;
			in :>> OPR = design.OPR;
			in :>> eta_comp = design.eta_comp;
			in :>> dotm1 = s1.dotm1;
			in :>> mu_cool = design.mu_cool;
			in :>> mu_bleed = design.mu_bleed;
			in :>> mu_bypass = design.mu_bypass;
			in :>> A2 = s2.A2;
			in :>> AR = design.AR;
		}

		calc s4 : Station4_CombustorExit {
			in :>> dotm_core = s3.dotm_core;
			in :>> FAR = design.FAR;
			in :>> ht3 = s3.ht3;
			in :>> eta_comb = design.eta_comb;
			in :>> Tt3 = s3.Tt3;
			in :>> pt3 = s3.pt3;
			in :>> A3a = s3.A3a;
			in :>> k_aer = design.k_aer;
			in :>> k_th = design.k_th;
		}

		calc s5 : Station5_TurbineExit {
			in :>> dotm4 = s4.dotm4;
			in :>> dotm_cool = s3.dotm_cool;
			in :>> ht4 = s4.ht4;
			in :>> ht3c = s3.ht3c;
			in :>> dotmf = s4.dotmf;
			in :>> Wcomp = s3.Wcomp;
			in :>> eta_shaft = design.eta_shaft;
			in :>> eta_turb = design.eta_turb;
			in :>> pt4 = s4.pt4;
		}

		then action s7 : Station7_CoreNozzleThroat {
			in :>> Tt5 = s5.Tt5;
			in :>> pt5 = s5.pt5;
			in :>> ht5 = s5.ht5;
			in :>> FAR5 = s5.FAR5;
			in :>> p0 = s0.p0;
			in :>> dotm5 = s5.dotm5;
		}

		then calc s9 : Station9_CoreNozzleExit {
			in :>> Tt5 = s5.Tt5;
			in :>> pt5 = s5.pt5;
			in :>> ht5 = s5.ht5;
			in :>> FAR5 = s5.FAR5;
			in :>> p0 = s0.p0;
			in :>> dotm5 = s5.dotm5;
		}

		calc byp : BypassNozzleExit {
			in :>> Tt3 = s3.Tt3;
			in :>> pt3 = s3.pt3;
			in :>> ht3 = s3.ht3;
			in :>> p0 = s0.p0;
			in :>> dotm_byp = s3.dotm_byp;
		}

		then calc perf : Performance {
			in :>> dotm5 = s5.dotm5;
			in :>> u9 = s9.u9;
			in :>> A9 = s9.A9;
			in :>> p9 = s9.p9;
			in :>> p0 = s0.p0;
			in :>> dotm_byp = s3.dotm_byp;
			in :>> u9b = byp.u9b;
			in :>> dotm1 = s1.dotm1;
			in :>> u0 = s0.u0;
			in :>> dotmf = s4.dotmf;
		}

		out F : Real = perf.F;
		out TSFC : Real = s4.dotmf / perf.F * 1e6;
	}

	part cruiseDesignPoint : DesignPoint;

	action cruiseCycle : EngineCycle {
		in :>> design = cruiseDesignPoint;
	}

	// ====================================================================
	// Python service binding -- FPB approach 2 (metadata): the FPB and its
	// parameters are annotated with the Python function and keyword names
	// that realize them, so a Service Binding Manager can read the
	// annotations and call main.run_cycle() directly. Only T0 and FAR are
	// exposed; every other run_cycle() argument keeps its main.py default
	// (the DesignPoint values above).
	// ====================================================================
	action def CycleService :> FunctionalProcessBlock {
		@ServiceBinding {
			lang = "python";
			module = "main";
			function = "run_cycle";
		}
		in T0 : Real {                  // free-stream static temperature, K
			@ParameterBinding { pythonName = "T0_override"; }
		}
		in FAR : Real {                 // fuel-air ratio of the core stream
			@ParameterBinding { pythonName = "FAR"; }
		}
		out F : Real {                  // net thrust, N
			@ParameterBinding { pythonName = "F"; }
		}
		out TSFC : Real {               // g/(kN s)
			@ParameterBinding { pythonName = "TSFC"; }
		}
	}

	action hotDayCruise : CycleService {
		in :>> T0 = 231.65;             // ISA + 15 K at 40,000 ft
		in :>> FAR = 0.02;
	}
}

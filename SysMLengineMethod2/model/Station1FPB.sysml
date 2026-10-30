package AircraftEngineStation1FPB {
	doc /* Station 1 only (captured stream tube) as a Functional Process
	     * Block, bound to main.captured_stream_tube() through model metadata
	     * (fpb-demo binding approach 2). It is the executable counterpart of
	     * Station1_CapturedStreamTube in ../../model/EngineCycle.sysml, with
	     * the same in/out parameters:
	     *
	     *   A1    = pi/4 * Do^2
	     *   dotm1 = rho0 * u0 * A1
	     *
	     * rho0 and u0 are station-0 (free-stream) results, so they have no
	     * default and each usage binds them.
	     *
	     * Run from the repository root (so 'main' imports), e.g.:
	     *   python -m SysMLengineMethod2.sbm invoke AircraftEngineStation1FPB::cruiseStation1
	     */

	private import ScalarValues::*;
	private import FPBCore::*;

	action def CapturedStreamTube :> FunctionalProcessBlock {
		@ServiceBinding {
			lang = "python";
			module = "main";
			function = "captured_stream_tube";
		}
		in rho0 : Real {                // free-stream static density, kg/m^3
			@ParameterBinding { pythonName = "rho0"; }
		}
		in u0 : Real {                  // free-stream velocity, m/s
			@ParameterBinding { pythonName = "u0"; }
		}
		in Do : Real = 0.75 {           // compressor face outer diameter, m
			@ParameterBinding { pythonName = "Do"; }
		}
		out A1 : Real {                 // capture area, m^2
			@ParameterBinding { pythonName = "A1"; }
		}
		out dotm1 : Real {              // captured mass flow, kg/s
			@ParameterBinding { pythonName = "dotm1"; }
		}
	}

	// station-0 values of the main.py design point (40,000 ft, Mach 0.85)
	action cruiseStation1 : CapturedStreamTube {
		in :>> rho0 = 0.3026701645983352;
		in :>> u0 = 250.9422313640887;
	}
}

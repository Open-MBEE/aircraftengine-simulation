"""
Design-point cycle deck for a single-shaft jet engine with bleed air, turbine
cooling and a bypass stream.

The engine is computed station by station; the numbering follows SAE ARP 755A
(stations 6 and 8 are skipped on purpose):

    0  free stream               4  combustor exit / turbine inlet
    1  captured stream tube      5  turbine exit
    2  compressor face           7  core nozzle throat (sonic)
    3  compressor exit           9  core nozzle exit (adapted)

Secondary streams, all taken by mass fraction:
    mu_bleed   cabin bleed air, extracted halfway through the compressor and
               dumped overboard (no thrust credit, full ram drag charged)
    mu_cool    turbine cooling air, extracted halfway through the compressor
               and mixed back in ahead of the turbine
    mu_bypass  bypass air, split off at the compressor exit and expanded to
               ambient through its own adapted nozzle

The theory behind every step is derived in THEORY.md.
"""

import math
import pygasturb as gt


# ----------------------------------------------------------------------------
# pretty printing helpers
# ----------------------------------------------------------------------------

_WIDTH = 58

def station( number, name ):
    title = f" Station {number} — {name} "
    print( "\n" + f"{title:─^{_WIDTH}}" )

def block( title ):
    print( "\n" + f"{' ' + title + ' ':═^{_WIDTH}}" )

def row( symbol, value, unit, description="" ):
    text = f"  {symbol:<5} = {value:>10.3f} {unit:<7}"
    if description :
        text += f" {description}"
    print( text )


# gas models are stateless after construction (pure functions of T/p/...), so
# one instance is reused across every run_cycle() call instead of rebuilding
# the polynomial fits (and re-solving the reference state) every time
_g = gt.Gas()
_a = gt.Atmosphere()


def captured_stream_tube( rho0, u0, Do ):
    """Station 1: the engine swallows the stream tube that fits the
    compressor face; far upstream it is still at free-stream conditions.
    Returns the capture area A1 in m² and the captured mass flow dotm1 in
    kg/s. Shared by run_cycle() and the station-1 FPB
    (SysMLengineMethod2/model/Station1FPB.sysml)."""

    A1 = 0.25 * math.pi * Do**2
    dotm1 = rho0 * u0 * A1
    return dict( A1=A1, dotm1=dotm1 )


def run_cycle(
    alt_ft=40e3,        # cruise altitude in ft
    Ma0=0.85,           # cruise Mach number
    Do=0.75,            # outer diameter of the compressor face in m
    Di=0.05,            # diameter of the inlet cone in m
    AR=2.25,            # compressor area contraction A2 / A3
    OPR=25,             # overall pressure ratio pt3 / pt2
    eta_comp=0.88,      # isentropic efficiency
    mu_bypass=0.3,      # bypass fraction of the compressor exit flow
    mu_cool=0.01,       # turbine cooling fraction of the inlet flow
    mu_bleed=0.005,     # cabin bleed fraction of the inlet flow
    eta_comb=0.95,      # combustion efficiency
    FAR=0.02,           # fuel-air ratio of the core stream
    k_aer=10.0,         # aerodynamic (cold) pressure loss parameter
    k_th=0.5,           # fundamental (hot) pressure loss parameter
    eta_turb=0.86,      # isentropic efficiency
    eta_shaft=0.98,     # mechanical efficiency of the shaft
    T0_override=None,   # replace the standard-atmosphere static temperature
                        # (ISA-deviation / hot-day study); p0 stays at the
                        # altitude's standard value, rho0 is recomputed from
                        # the ideal gas law so mass flow stays consistent
    verbose=True,
):
    """Run the design-point cycle once; return a dict of station and
    performance quantities. With verbose=True (the default, used by the CLI)
    it also prints the station-by-station report."""

    g = _g
    a = _a

    # ------------------------------------------------------------------------
    # station 0 : free stream
    # ------------------------------------------------------------------------
    if verbose : station( 0, "free stream" )

    # static state from the standard atmosphere (the model expects m)
    T0, p0, rho0 = a.atm( alt_ft * 0.3048 )
    if T0_override is not None :
        T0 = T0_override
        rho0 = p0 / ( g.R() * T0 )

    # velocity and total state; the total pressure follows from an isentropic
    # deceleration to rest
    u0  = Ma0 * g.c( T0 )
    h0  = g.h( T0 )
    ht0 = h0 + 0.5 * u0**2
    Tt0 = g.T( ht0 )
    pt0 = g.isenp( T0, p0, Tt0 )

    if verbose :
        row( "T",  T0,       "K" )
        row( "p",  p0*1e-5,  "bar" )
        row( "Ma", Ma0,      "-" )
        row( "u",  u0,       "m/s" )
        row( "Tt", Tt0,      "K" )
        row( "pt", pt0*1e-5, "bar" )

    # ------------------------------------------------------------------------
    # station 1 : captured stream tube
    # ------------------------------------------------------------------------
    if verbose : station( 1, "captured stream tube" )

    s1 = captured_stream_tube( rho0, u0, Do )
    A1, dotm1 = s1[ "A1" ], s1[ "dotm1" ]

    if verbose :
        row( "A",  A1,    "m²" )
        row( "ṁ", dotm1, "kg/s" )

    # ------------------------------------------------------------------------
    # station 2 : compressor face
    # ------------------------------------------------------------------------
    if verbose : station( 2, "compressor face" )

    # the inlet cone blocks part of the cross section, so the flow contracts
    # from A1 to A2 and accelerates slightly; the contraction is isentropic
    A2 = A1 - 0.25 * math.pi * Di**2
    T2, p2, u2 = g.compress( T0, p0, u0, A1, A2 )
    Ma2 = u2 / g.c( T2 )

    # the inlet is adiabatic and treated as lossless, so the total state of the
    # free stream is preserved
    Tt2 = Tt0
    ht2 = ht0
    pt2 = pt0

    if verbose :
        row( "A",  A2,       "m²" )
        row( "T",  T2,       "K" )
        row( "p",  p2*1e-5,  "bar" )
        row( "Ma", Ma2,      "-" )
        row( "Tt", Tt2,      "K" )
        row( "pt", pt2*1e-5, "bar" )

    # ------------------------------------------------------------------------
    # station 3 : compressor exit
    # ------------------------------------------------------------------------
    if verbose : station( 3, "compressor exit" )

    # total exit state and specific work from the pressure ratio and the
    # isentropic efficiency
    Tt3, pt3, wcomp = g.compressor( Tt2, pt2, OPR, eta_comp )
    ht3 = g.h( Tt3 )

    # bleed and cooling air are extracted halfway through the compression, at
    # the enthalpy where half of the specific work has been done
    ht3c = ht2 + 0.5 * wcomp

    # the full flow absorbs the first half of the work, only the remainder
    # continues through the second half
    dotm_cool  = mu_cool  * dotm1
    dotm_bleed = mu_bleed * dotm1
    dotm3 = dotm1 - dotm_cool - dotm_bleed
    Wcomp = ( dotm1 + dotm3 ) * 0.5 * wcomp

    # static state at the compressor exit
    A3 = A2 / AR
    T3, p3, u3, Ma3 = g.static_from_total( Tt3, pt3, dotm3, A3 )

    # the bypass stream splits off here; both streams share the same static
    # state, so the areas divide in proportion to the mass flows
    dotm_byp  = mu_bypass * dotm3
    dotm_core = dotm3 - dotm_byp
    A3a = A3 * dotm_core / dotm3
    A3b = A3 - A3a

    if verbose :
        row( "A",  A3,       "m²" )
        row( "T",  T3,       "K" )
        row( "p",  p3*1e-5,  "bar" )
        row( "Ma", Ma3,      "-" )
        row( "Tt", Tt3,      "K" )
        row( "pt", pt3*1e-5, "bar" )
        row( "P",  Wcomp*1e-6, "MW", "compressor power" )

    # ------------------------------------------------------------------------
    # station 4 : combustor exit
    # ------------------------------------------------------------------------
    if verbose : station( 4, "combustor exit" )

    # only the core stream is burned; the fuel-air ratio fixes the fuel flow
    dotmf = FAR * dotm_core
    dotm4 = dotm_core + dotmf

    # energy balance over the burner: the combustion efficiency acts on the
    # heat release only, per kg of mixture
    ht4 = ( ht3 + eta_comb * g.Hu * FAR ) / ( 1.0 + FAR )
    Tt4 = g.T( ht4, FAR )

    # total pressure loss, split into an aerodynamic part and the fundamental
    # loss of heating a moving gas, both scaled with the flow parameter X
    # (X² is roughly gamma Ma² at the burner inlet)
    A4 = A3a
    X  = dotm_core * math.sqrt( g.R() * Tt3 ) / ( pt3 * A4 )
    pt4 = pt3 * ( 1.0 - X*X * ( k_aer + k_th * ( Tt4/Tt3 - 1.0 ) ) )

    T4, p4, u4, Ma4 = g.static_from_total( Tt4, pt4, dotm4, A4, FAR )

    if verbose :
        row( "A",  A4,       "m²" )
        row( "T",  T4,       "K" )
        row( "p",  p4*1e-5,  "bar" )
        row( "Ma", Ma4,      "-" )
        row( "Tt", Tt4,      "K" )
        row( "pt", pt4*1e-5, "bar" )
        row( "ṁf", dotmf,   "kg/s", "fuel flow" )

    # ------------------------------------------------------------------------
    # station 5 : turbine exit
    # ------------------------------------------------------------------------
    if verbose : station( 5, "turbine exit" )

    # the cooling air mixes in ahead of the turbine at constant total pressure;
    # it dilutes the fuel-air ratio of the mixture
    dotm5 = dotm4 + dotm_cool
    ht4m  = ( dotm4 * ht4 + dotm_cool * ht3c ) / dotm5
    FAR5  = dotmf / ( dotm5 - dotmf )
    Tt4m  = g.T( ht4m, FAR5 )

    # the turbine drives the compressor through the shaft, so the power balance
    # fixes the real exit enthalpy
    Wshaft = Wcomp / eta_shaft
    ht5 = ht4m - Wshaft / dotm5
    Tt5 = g.T( ht5, FAR5 )

    # the isentropic efficiency sets the price in pressure: an ideal turbine
    # would extract the same work with a smaller expansion ratio, so the ideal
    # end state defines the exit pressure
    ht5s = ht4m - ( ht4m - ht5 ) / eta_turb
    Tt5s = g.T( ht5s, FAR5 )
    pt5  = g.isenp( Tt4m, pt4, Tt5s, FAR5 )

    if verbose :
        row( "Tt", Tt5,      "K" )
        row( "pt", pt5*1e-5, "bar" )
        row( "P",  Wshaft*1e-6, "MW", "shaft power" )

    # ------------------------------------------------------------------------
    # station 7 : core nozzle throat
    # ------------------------------------------------------------------------
    if verbose : station( 7, "core nozzle throat" )

    # the nozzle only chokes if the pressure ratio exceeds the critical value
    gam5 = g.gamma( Tt5, FAR5 )
    p_crit = pt5 / ( 1.0 + 0.5*( gam5 - 1.0 ) )**( gam5/( gam5 - 1.0 ) )
    if p_crit < p0 :
        raise Exception( "the core nozzle is not choked, "
                         f"pt5/p0 = {pt5/p0:.2f} is below the critical ratio" )

    # at the throat the flow is exactly sonic: solve h(T7) + c(T7)²/2 = ht5 by
    # fixed-point iteration
    ht7 = ht5
    pt7 = pt5
    T7 = Tt5 / ( 1.0 + 0.5 * ( gam5 - 1.0 ) )
    Told = 0.0
    while abs( T7 - Told ) > 1e-6 :
        Told = T7
        u7 = g.c( T7, FAR5 )
        T7 = g.T( ht7 - 0.5 * u7**2, FAR5 )

    p7 = g.isenp( Tt5, pt5, T7, FAR5 )
    A7 = dotm5 / ( g.rho( T7, p7, FAR5 ) * u7 )

    if verbose :
        row( "A",  A7,      "m²" )
        row( "T",  T7,      "K" )
        row( "p",  p7*1e-5, "bar" )
        row( "u",  u7,      "m/s" )

    # ------------------------------------------------------------------------
    # station 9 : core nozzle exit
    # ------------------------------------------------------------------------
    if verbose : station( 9, "core nozzle exit" )

    # the divergent section expands the flow isentropically to the ambient
    # pressure (adapted nozzle), which maximizes the thrust
    p9 = p0
    T9 = g.isenT( Tt5, pt5, p9, FAR5 )
    u9 = math.sqrt( 2.0 * ( ht5 - g.h( T9, FAR5 ) ) )
    A9 = dotm5 / ( g.rho( T9, p9, FAR5 ) * u9 )

    if verbose :
        row( "A",  A9,      "m²" )
        row( "T",  T9,      "K" )
        row( "p",  p9*1e-5, "bar" )
        row( "u",  u9,      "m/s" )
        row( "Ma", u9/g.c( T9, FAR5 ), "-" )

    # ------------------------------------------------------------------------
    # bypass nozzle
    # ------------------------------------------------------------------------
    if verbose : station( "3b", "bypass nozzle exit" )

    # the bypass stream leaves the engine at compressor exit conditions and
    # expands to ambient pressure through its own adapted nozzle
    T9b = g.isenT( Tt3, pt3, p0 )
    u9b = math.sqrt( 2.0 * ( ht3 - g.h( T9b ) ) )
    A9b = dotm_byp / ( g.rho( T9b, p0 ) * u9b )

    if verbose :
        row( "A",  A9b,     "m²" )
        row( "T",  T9b,     "K" )
        row( "u",  u9b,     "m/s" )
        row( "ṁ", dotm_byp, "kg/s" )

    # ------------------------------------------------------------------------
    # performance
    # ------------------------------------------------------------------------
    if verbose : block( "performance" )

    # momentum bookkeeping: both nozzles are adapted, so there is no pressure
    # thrust; the ram drag is charged on the full captured flow, which includes
    # the bleed air that is dumped overboard
    F_core = dotm5 * u9 + A9 * ( p9 - p0 )
    F_byp  = dotm_byp * u9b
    F_ram  = dotm1 * u0
    F = F_core + F_byp - F_ram

    # the standard efficiency chain: the thermal efficiency measures how much
    # fuel heat becomes jet kinetic energy, the propulsive efficiency how much
    # of that becomes thrust power, and their product is the overall efficiency
    dKE    = 0.5 * ( dotm5 * u9**2 + dotm_byp * u9b**2 ) - 0.5 * dotm1 * u0**2
    eta_th = dKE / ( dotmf * g.Hu )
    eta_p  = F * u0 / dKE
    eta_o  = eta_th * eta_p

    if verbose :
        row( "Fcore", F_core*1e-3, "kN", "gross thrust, core" )
        row( "Fbyp",  F_byp*1e-3,  "kN", "gross thrust, bypass" )
        row( "Fram",  F_ram*1e-3,  "kN", "ram drag" )
        row( "F",     F*1e-3,      "kN", "net thrust" )
        row( "F/ṁ",  F/dotm1,     "m/s", "specific thrust" )
        row( "TSFC",  dotmf/F*1e6, "g/(kN·s)", "thrust specific fuel consumption" )
        row( "ηth",  eta_th,      "-", "thermal efficiency" )
        row( "ηp",   eta_p,       "-", "propulsive efficiency" )
        row( "η0",   eta_o,       "-", "overall efficiency" )

    return dict(
        T0=T0, p0=p0, rho0=rho0, u0=u0, Tt0=Tt0, pt0=pt0,
        A1=A1, dotm1=dotm1,
        A2=A2, T2=T2, p2=p2, Ma2=Ma2, Tt2=Tt2, pt2=pt2,
        A3=A3, T3=T3, p3=p3, Ma3=Ma3, Tt3=Tt3, pt3=pt3, Wcomp=Wcomp,
        A4=A4, T4=T4, p4=p4, Ma4=Ma4, Tt4=Tt4, pt4=pt4, dotmf=dotmf,
        Tt5=Tt5, pt5=pt5, Wshaft=Wshaft,
        A7=A7, T7=T7, p7=p7, u7=u7,
        A9=A9, T9=T9, p9=p9, u9=u9,
        A9b=A9b, T9b=T9b, u9b=u9b, dotm_byp=dotm_byp,
        F_core=F_core, F_byp=F_byp, F_ram=F_ram, F=F,
        TSFC=dotmf/F*1e6, eta_th=eta_th, eta_p=eta_p, eta_o=eta_o,
    )


if __name__ == '__main__':
    run_cycle()

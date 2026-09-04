# Theory

This document derives the equations used by `main.py` and the `gasturb` package
to compute the design point of a single-shaft jet engine with bleed air, turbine
cooling and a bypass stream. Everything is one-dimensional, steady and adiabatic
towards the environment; the only heat input is the combustor.

## 1. Station numbering

The stations follow SAE ARP 755A; numbers 6 and 8 are reserved for an
afterburner section and are skipped here.

| Station | Location |
|---|---|
| 0 | free stream |
| 1 | captured stream tube, still at free-stream conditions |
| 2 | compressor face, behind the inlet cone |
| 3 | compressor exit; the bypass stream splits off here |
| 4 | combustor exit = turbine inlet |
| 5 | turbine exit |
| 7 | core nozzle throat |
| 9 | core nozzle exit |

Three secondary streams are taken by mass fraction:

* **Bleed air** (`mu_bleed`), extracted halfway through the compression and
  dumped overboard — it costs work and ram drag and returns nothing.
* **Cooling air** (`mu_cool`), extracted halfway through the compression and
  mixed back into the hot gas ahead of the turbine.
* **Bypass air** (`mu_bypass`), split off at the compressor exit and expanded to
  ambient pressure through its own nozzle.

## 2. Working fluid

The gas model (`gasturb/gas.py`) follows Walsh & Fletcher, *Gas Turbine
Performance*, chapter 3. Air and combustion products are **semi-perfect
gases**: they obey the ideal gas law, but the specific heat depends on
temperature. For dry air

$$c_p(T) = \sum_{i=0}^{8} A_i \, (T/1000)^i \qquad \text{(F3.23)}$$

and for the products of kerosene combustion at fuel–air ratio
$\mathrm{FAR} = \dot m_f / \dot m_\mathrm{air}$

$$c_p(T,\mathrm{FAR}) = c_{p,\mathrm{air}}(T) + 
  \frac{\mathrm{FAR}}{1+\mathrm{FAR}} \sum_{i=0}^{7} B_i \,(T/1000)^i
  \qquad \text{(F3.24)}$$

The weight $\mathrm{FAR}/(1+\mathrm{FAR})$ is the mass fraction of
stoichiometric combustion products in the mixture — one kilogram of mixture
contains $1/(1+\mathrm{FAR})$ kilograms of air and
$\mathrm{FAR}/(1+\mathrm{FAR})$ kilograms of burned fuel.

Enthalpy and entropy follow by integration,

$$h(T) = \int c_p \, dT, \qquad
  s(T,p) = \int \frac{c_p}{T} \, dT - R \ln \frac{p}{p_\mathrm{ref}},$$

which keeps the polynomial form (F3.26/F3.27); the $1/T$ integration turns the
constant term of $c_p$ into a logarithm, which is carried separately. The
integration constants are chosen so that $h$ and $s$ match the NASA CEA
reference values for air at 298.15 K, which makes the model directly comparable
with equilibrium calculations.

The gas constant of the products (F3.29) barely differs from that of air,
because the molar masses of CO₂ and H₂O straddle that of the O₂ they replace;
at FAR = 0.02 the correction is about $2\cdot10^{-4}$ J/(kg K).

Two inversions are needed throughout the cycle and are solved by Newton's
method:

* $T(h)$ — temperature from enthalpy, using $dh/dT = c_p$;
* isentropic temperature from a pressure ratio,
  $s^0(T_2) = s^0(T_1) + R\ln(p_2/p_1)$, using $ds/dT = c_p/T$,

and the inverse of the second, the **isentropic pressure** for a given
temperature change, is explicit:

$$p_2 = p_1 \exp\!\left(\frac{s^0(T_2)-s^0(T_1)}{R}\right).$$

## 3. Atmosphere

`gasturb/atmosphere.py` implements the U.S. Standard Atmosphere 1976. The
geometric altitude $z$ is first converted to geopotential altitude

$$H = \frac{r_E \, z}{r_E + z},$$

which absorbs the altitude dependence of gravity ($r_E$ = 6 356 766 m). The
model then marches through layers of prescribed temperature gradient $\lambda$.
Within a layer, hydrostatic equilibrium $dp = -\rho g_0\,dH$ together with the
ideal gas law integrates to

$$\frac{p}{p_b} = \left(\frac{T}{T_b}\right)^{-g_0/(R\lambda)}
  \quad (\lambda \ne 0), \qquad
  \frac{p}{p_b} = \exp\!\left(-\frac{g_0 (H-H_b)}{R\,T}\right)
  \quad (\lambda = 0),$$

where the subscript $b$ marks the base of the layer. At 40 000 ft the flight
condition sits in the isothermal lower stratosphere: $T_0$ = 216.65 K,
$p_0$ = 0.188 bar.

## 4. Free stream and inlet (stations 0–2)

With the flight Mach number the velocity is $u_0 = \mathrm{Ma}_0 \, c(T_0)$,
where $c = \sqrt{\gamma R T}$. The total state follows from bringing the flow
to rest adiabatically and reversibly:

$$h_{t0} = h(T_0) + \tfrac12 u_0^2, \qquad
  T_{t0} = T(h_{t0}), \qquad
  p_{t0} = p_0 \exp\!\left(\frac{s^0(T_{t0})-s^0(T_0)}{R}\right).$$

At Ma 0.85 this gives $T_{t0} \approx 248$ K and $p_{t0}/p_0 \approx 1.60$ —
useful sanity anchors for the printout.

The engine swallows the stream tube that fills the compressor face,
$A_1 = \pi D_o^2/4$, so the mass flow is $\dot m_1 = \rho_0 u_0 A_1$. Between
stations 1 and 2 the inlet cone blocks the centre of the duct,
$A_2 = A_1 - \pi D_i^2/4$. The contraction is solved as an isentropic duct: the
static state at 2 satisfies conservation of mass, entropy and total enthalpy,

$$\rho_2 u_2 A_2 = \dot m_1, \qquad
  s(T_2,p_2) = s(T_1,p_1), \qquad
  h(T_2) + \tfrac12 u_2^2 = h_t,$$

solved with a damped Newton method (`Gas.compress`). A subsonic flow
accelerates through a contraction, so Ma₂ is slightly above Ma₀. The inlet is
treated as adiabatic and lossless, hence the total state of the free stream is
preserved: $T_{t2} = T_{t0}$, $p_{t2} = p_{t0}$.

## 5. Compressor (station 3)

The compressor is specified by its overall pressure ratio and isentropic
efficiency. On total quantities,

$$p_{t3} = \mathrm{OPR} \cdot p_{t2}, \qquad
  w = \frac{h_t(T_{t3s}) - h_{t2}}{\eta_c},$$

where $T_{t3s}$ is the isentropic exit temperature for the same pressure ratio.
The efficiency divides the ideal work because a real compressor must invest
*more* work to reach the same pressure. The real exit state is
$h_{t3} = h_{t2} + w$.

**Bleed and cooling extraction.** Both secondary flows are drawn off where half
of the specific work has been done, i.e. at the total enthalpy
$h_{t3c} = h_{t2} + w/2$. The full flow $\dot m_1$ absorbs the first half of
the work, only the remainder $\dot m_3 = \dot m_1(1-\mu_\mathrm{cool}-\mu_\mathrm{bleed})$
continues through the second half, so the shaft must provide

$$P_\mathrm{comp} = \left(\dot m_1 + \dot m_3\right) \tfrac12 w .$$

The static state at the exit area $A_3 = A_2/\mathrm{AR}$ is recovered from the
total state and continuity (`Gas.static_from_total`): starting from rest, the
iteration

$$u \leftarrow \frac{\dot m}{\rho(T,p)\,A}, \qquad
  T \leftarrow T\!\left(h_t - \tfrac12 u^2\right), \qquad
  p \leftarrow p_t \exp\!\left(\frac{s^0(T)-s^0(T_t)}{R}\right)$$

converges to the subsonic branch.

**Bypass split.** The bypass stream leaves the core at station 3. Both streams
share the same static state, so the duct areas divide in proportion to the mass
flows: $A_{3a}/A_3 = \dot m_\mathrm{core}/\dot m_3$.

## 6. Combustor (station 4)

Only the core stream is burned. The fuel–air ratio defines the fuel flow
$\dot m_f = \mathrm{FAR} \cdot \dot m_\mathrm{core}$, and the energy balance
over the burner, per kilogram of *mixture*, reads

$$h_{t4} = \frac{h_{t3} + \eta_b \, H_u \, \mathrm{FAR}}{1+\mathrm{FAR}} .$$

The combustion efficiency $\eta_b$ acts only on the heat release: unburned fuel
still passes through the turbine as mass, it just contributes no heat. From
$h_{t4}$ the turbine inlet temperature follows with the product-gas
polynomials, $T_{t4} = T(h_{t4}, \mathrm{FAR})$.

**Pressure loss.** The total pressure drops for two reasons: friction and
mixing in the liner (the *cold* loss), and the fundamental loss of adding heat
to a moving gas (the *hot* or Rayleigh loss). Both scale with the dynamic head
of the incoming flow, which is captured by the non-dimensional flow parameter

$$X = \frac{\dot m_\mathrm{core}\sqrt{R\,T_{t3}}}{p_{t3}\,A_4},
  \qquad X^2 \approx \gamma\,\mathrm{Ma}^2 ,$$

so that

$$\frac{\Delta p_t}{p_{t3}} = X^2\left(k_\mathrm{aer} + 
   k_\mathrm{th}\left(\frac{T_{t4}}{T_{t3}} - 1\right)\right).$$

The defaults are anchored in the literature: $k_\mathrm{aer} = 10$ corresponds
to a pressure-loss factor $\Delta p_t / q_\mathrm{ref} \approx 20$, typical of
annular combustors (Lefebvre), and $k_\mathrm{th} = 0.5$ reproduces the
low-Mach Rayleigh result $\Delta p_t/p_t \approx \tfrac{\gamma}{2}\mathrm{Ma}^2
(T_{t4}/T_{t3}-1)$. With the present geometry the burner inlet Mach number is
about 0.08, giving a total loss of roughly 10 %.

## 7. Turbine (station 5)

**Cooling-air mixing.** Ahead of the turbine the cooling air rejoins the hot
gas. The mixing is modelled at constant total pressure; the mixed enthalpy is
the mass-weighted average

$$h_{t4m} = \frac{\dot m_4 h_{t4} + \dot m_\mathrm{cool}\, h_{t3c}}{\dot m_5},
  \qquad \dot m_5 = \dot m_4 + \dot m_\mathrm{cool},$$

and the fuel–air ratio is diluted accordingly,
$\mathrm{FAR}_5 = \dot m_f / (\dot m_5 - \dot m_f)$.

**Shaft balance.** On a single shaft the turbine must deliver exactly the
compressor power plus the mechanical losses:

$$P_\mathrm{shaft} = \frac{P_\mathrm{comp}}{\eta_\mathrm{shaft}}, \qquad
  h_{t5} = h_{t4m} - \frac{P_\mathrm{shaft}}{\dot m_5}.$$

This fixes the *real* exit enthalpy — energy conservation leaves no freedom
here. What the isentropic efficiency determines is the *pressure* this work
costs: an ideal turbine would extract the same work with a smaller expansion
ratio. The ideal end state

$$h_{t5s} = h_{t4m} - \frac{h_{t4m} - h_{t5}}{\eta_t} \;\le\; h_{t5}$$

lies on the isentrope through the inlet state, so the exit pressure follows
from the entropy relation evaluated at $T_{t5s} = T(h_{t5s})$:

$$p_{t5} = p_{t4} \exp\!\left(\frac{s^0(T_{t5s}) - s^0(T_{t4m})}{R}\right).$$

Because $h_{t5s} < h_{t5}$, the real machine expands *further* in pressure than
the ideal one for the same work — the entropy production is paid in pressure,
not in energy.

## 8. Nozzles (stations 7 and 9)

**Choking.** A convergent–divergent nozzle only works as such if the pressure
ratio exceeds the critical value,

$$\frac{p_{t5}}{p_0} > \left(1 + \frac{\gamma-1}{2}\right)^{\gamma/(\gamma-1)}
  \approx 1.85,$$

which the deck verifies (here $p_{t5}/p_0 \approx 3$).

**Throat.** At the throat the flow is exactly sonic. The static temperature
$T_7$ satisfies the implicit energy equation

$$h(T_7) + \tfrac12 c(T_7)^2 = h_{t5},$$

solved by fixed-point iteration; pressure follows from the isentrope and the
throat area from continuity, $A_7 = \dot m_5 / (\rho_7 u_7)$.

**Exit.** The divergent section expands the flow isentropically to ambient
pressure ($p_9 = p_0$, an *adapted* nozzle, which maximizes thrust). The exit
temperature comes from the isentrope, the velocity from the energy equation:

$$T_9 = T_s(T_{t5}, p_{t5} \to p_0), \qquad
  u_9 = \sqrt{2\left(h_{t5} - h(T_9)\right)} .$$

**Bypass nozzle.** The bypass stream carries the full compressor exit state
$(T_{t3}, p_{t3})$ and expands through its own adapted nozzle by the same two
equations. Because it was compressed through the full pressure ratio but never
heated, it leaves cold and fast — an unusual design compared to a turbofan,
where the bypass air only passes the fan, but a thermodynamically consistent
one.

## 9. Thrust bookkeeping

The net thrust is the momentum theorem applied to a control volume around the
whole engine:

$$F = \underbrace{\dot m_5 u_9 + A_9 (p_9 - p_0)}_{\text{core, gross}}
    + \underbrace{\dot m_\mathrm{byp} u_{9b}}_{\text{bypass, gross}}
    - \underbrace{\dot m_1 u_0}_{\text{ram drag}} .$$

Conventions used here:

* Both nozzles are adapted, so the pressure terms vanish; the core term is kept
  in the code for clarity.
* The ram drag is charged on the **full** captured flow $\dot m_1$, including
  the bleed air. The bleed stream is dumped overboard with no thrust credit —
  its momentum is simply lost.
* The fuel adds exhaust momentum ($\dot m_5$ contains $\dot m_f$) but no ram
  drag, since it is carried on board.

Two figures of merit close the summary: the specific thrust $F/\dot m_1$ and
the thrust specific fuel consumption $\mathrm{TSFC} = \dot m_f / F$.

**Efficiency chain.** The fuel power is converted to thrust power in two
stages, and each stage has its own efficiency (Walsh & Fletcher).
The *thermal* efficiency measures how much of the fuel heat ends up as kinetic
energy of the jets, evaluated in the aircraft-fixed frame:

$$\eta_\mathrm{th} = \frac{\Delta \dot E_\mathrm{kin}}{\dot m_f H_u}, \qquad
  \Delta \dot E_\mathrm{kin} = \tfrac12\left(\dot m_5 u_9^2 +
  \dot m_\mathrm{byp} u_{9b}^2\right) - \tfrac12 \dot m_1 u_0^2 .$$

The *propulsive* efficiency measures how much of that kinetic energy becomes
thrust power — the remainder is left behind as swirl-free wake energy:

$$\eta_p = \frac{F\,u_0}{\Delta \dot E_\mathrm{kin}} .$$

Their product is the *overall* efficiency, which links fuel flow directly to
thrust power:

$$\eta_0 = \eta_\mathrm{th}\,\eta_p = \frac{F\,u_0}{\dot m_f H_u} .$$

## 10. References

* P. P. Walsh, P. Fletcher, *Gas Turbine Performance*, 2nd ed., Blackwell,
  2004. — Gas property polynomials (F3.23–F3.29), cycle conventions.
* A. H. Lefebvre, D. R. Ballal, *Gas Turbine Combustion*, 3rd ed., CRC Press,
  2010. — Combustor pressure-loss factors.
* *U.S. Standard Atmosphere 1976*, NOAA/NASA/USAF, Washington D.C., 1976.
* S. Gordon, B. J. McBride, *Computer Program for Calculation of Complex
  Chemical Equilibrium Compositions and Applications* (NASA CEA), NASA RP-1311,
  1994. — Reference state of air.
* SAE ARP 755A, *Gas Turbine Engine Performance Station Identification and
  Nomenclature*. — Station numbering.

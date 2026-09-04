import math
import numpy as np


class Gas :
    """
    Semi-perfect gas model for dry air and kerosene combustion products.

    Properties follow Walsh and Fletcher, "Gas Turbine Performance", 2nd ed.,
    chapter 3: cp, h and s are eighth-order polynomials in temperature, and the
    influence of combustion is carried by a second polynomial weighted with
    FAR/(1+FAR), where FAR is the fuel-air ratio by mass. The model is valid for
    200 K to 2000 K and lean mixtures.
    """

    def __init__(self ):

        # maximum number of iterations for the Newton and fixed-point solvers
        self._maxit = 100

        # Walsh and Fletcher: Gas Turbine Performance, F3.23 (dry air, A8..A0)
        self._acp = np.array([ -0.081873, 0.794571, -3.234725, 7.097112, -8.893933,
                               6.083152, -1.852148, 0.236688, 0.992313 ])

        # Walsh and Fletcher: Gas Turbine Performance, F3.24 (products, B8..B0)
        self._bcp = np.array( [ 0, -0.003919, -0.361112, 3.081778, -10.233795,
                                 17.254096, -15.863157, 8.747481, -0.718874 ])

        # convert values to pure temperatures
        scale = 1e-24
        for k in range(0,8):
            self._acp[ k ] = self._acp[ k ] * scale
            self._bcp[ k ] = self._bcp[ k ] * scale
            scale *= 1000.

        # creating the enthalpy polynomials
        # Walsh and Fletcher: Gas Turbine Performance, F3.26 and F3.27
        # h = int cp dT, so T^j becomes T^(j+1)/(j+1) and the polynomial gains
        # one degree. In polyval order index k holds T^(8-k), which integrates
        # to T^(9-k)/(9-k), and the integration constant goes in the new slot.
        self._ah = np.zeros( 10 )
        self._bh = np.zeros( 10 )
        for k in range(0,9):
            j = 8 - k
            self._ah[ k ] = self._acp[ k ] / ( j + 1 )
            self._bh[ k ] = self._bcp[ k ]  / ( j + 1 )
        self._ah[9] = 0.422178
        self._bh[9] = 0.055593

        # creating the entropy polynomials
        # s0 = int cp/T dT. In polyval order index k holds T^(8-k), so cp/T holds
        # T^(7-k), which integrates to T^(8-k)/(8-k) -- the degree is unchanged.
        # The constant term of cp (index 8) is the exception: it integrates to a
        # logarithm, which a polynomial cannot carry, so it is held separately and
        # index 8 is left free for the integration constant.
        self._as = np.zeros(9)
        self._bs = np.zeros(9)

        for k in range(0,8):
            j = 8 - k
            self._as[ k ] = self._acp[ k ] / j
            self._bs[ k ] = self._bcp[ k ]  / j

        # coefficients of the ln( T ) term
        self._aslog = self._acp[ 8 ]
        self._bslog = self._bcp[ 8 ]

        self._as[8] = 0.001053
        self._bs[8] = -0.0016079

        # final scale, because we want the coefficients in J/kg/K
        self._acp *= 1e3
        self._bcp *= 1e3
        self._ah *= 1e3
        self._bh *= 1e3
        self._as *= 1e3
        self._bs *= 1e3
        self._aslog *= 1e3
        self._bslog *= 1e3



        # reference state of air from NASA CEA; gas constant in J/(kg K),
        # molar mass in kg/mol via kB * NA / R0
        self._R0 = 287.05
        self._M0 = 1.380649*6.02214076 / self._R0
        self._Tref = 298.15
        self._href = 8649.264/self._M0
        self._sref = -3.921504225*self._R0
        self._cpref = self.cp( self._Tref )

        # overriding the Walsh and Fletcher offsets with the CEA reference data,
        # so that h(Tref) and s(Tref, 1 bar) match the tabulated values
        self._ah[9] = 0
        self._ah[9] = self._href - self.h( self._Tref )

        self._as[8] = 0
        self._as[8] = self._sref - self._s0( self._Tref )

        # lower heating value of kerosene in J/kg
        self.Hu = 42.8e6

    @staticmethod
    def _w(FAR):
        # Walsh and Fletcher weight the combustion-product polynomials with the
        # mass fraction of stoichiometric products in the mixture, FAR/(1+FAR),
        # not with FAR itself (see F3.24 and F3.27).
        return FAR / ( 1.0 + FAR )

    def rho(self, T, p, FAR=0.0 ):
        """Density from the ideal gas law."""
        return p / ( self.R( FAR ) * T )

    def cp(self, T, FAR=0.0):
        """Specific heat capacity, Walsh and Fletcher F3.23/F3.24."""
        if FAR > 0.0:
            return np.polyval(self._acp, T) + self._w(FAR) * np.polyval(self._bcp, T)
        else:
            return np.polyval(self._acp, T)

    def h(self, T, FAR=0.0):
        """Specific enthalpy, Walsh and Fletcher F3.26/F3.27."""
        if FAR > 0.0:
            return np.polyval(self._ah, T) + self._w(FAR) * np.polyval(self._bh, T)
        else:
            return np.polyval(self._ah, T)

    def _s0(self, T, FAR=0.0):
        # temperature part of the entropy; the pressure part is added in s()
        s = np.polyval(self._as, T) + self._aslog * np.log( T )
        if FAR > 0.0:
            s += self._w(FAR) * ( np.polyval(self._bs, T) + self._bslog * np.log( T ) )
        return s

    def R(self, FAR=0.0):
        """
        Specific gas constant, Walsh and Fletcher F3.29. For kerosene the molar
        mass of the products is almost that of air, so the correction is tiny
        (about -2e-4 J/(kg K) at FAR = 0.02).
        """
        return self._R0 + FAR * ( FAR * 1e-7 - 0.0099 )

    def gamma(self, T, FAR=0.0 ):
        cp = self.cp( T, FAR )
        return cp / ( cp - self.R( FAR ) )

    def c(self, T, FAR=0.0 ):
        return math.sqrt( self.gamma( T, FAR ) * self.R( FAR ) * T )

    def s(self, T, p, FAR=0.0):
        # entropy falls with rising pressure, hence the minus sign
        return self._s0(T, FAR) - self.R( FAR ) * np.log( p / 1e5 )

    def dsdT(self, T, FAR=0.0):
        return self.cp( T, FAR ) / T

    def dsdp(self, p, FAR=0.0):
        return -self.R(FAR) / p

    def T(self, h, FAR=0.0):

        # initial guess
        T = (h - self.h(self._Tref, FAR)) / self.cp(self._Tref, FAR) + self._Tref

        # the residual is an enthalpy of order 1e6 J/kg, so it cannot be driven to
        # an absolute tolerance. The Newton step in T is the scale free measure.
        c = 0
        while True:
            dT = ( self.h( T, FAR ) - h ) / self.cp( T, FAR )
            T -= dT
            if abs( dT ) < 1e-10 * abs( T ) :
                break
            c += 1

            if c == self._maxit :
                raise Exception("Failed to converge")
        return T

    def isenT(self, T0, p0, p1, FAR=0.0 ):

        # s( T1, p1 ) = s( T0, p0 )  reduces to  s0( T1 ) = s0( T0 ) + R ln( p1/p0 )
        R = self.R( FAR )
        target = self._s0( T0, FAR ) + R * math.log( p1 / p0 )

        # ideal gas guess with frozen cp
        T1 = T0 * (p1 / p0)**( R / self.cp( T0, FAR ) )

        c = 0
        while True:
            dT = ( self._s0( T1, FAR ) - target ) / self.dsdT( T1, FAR )
            T1 -= dT
            if abs( dT ) < 1e-10 * abs( T1 ) :
                break
            c += 1
            if c == self._maxit:
                raise Exception("Failed to converge")

        return T1

    def isenp(self, T0, p0, T1, FAR=0.0 ):

        # the same relation solved for p1, which needs no iteration
        R = self.R( FAR )
        return p0 * math.exp( ( self._s0( T1, FAR ) - self._s0( T0, FAR ) ) / R )

    def compressor(self, T1, p1, PR, eta=1.0, FAR=0.0 ):
        """
        Compression through the pressure ratio PR with the isentropic efficiency
        eta. Returns T2, p2 and the specific work. eta = 1 is the isentropic case.
        """
        p2 = p1 * PR

        h1 = self.h( T1, FAR )

        # ideal end state, reached without any entropy production
        dhs = self.h( self.isenT( T1, p1, p2, FAR ), FAR ) - h1

        # a real compressor needs more work than the ideal one
        w = dhs / eta

        return self.T( h1 + w, FAR ), p2, w

    def _area_mach(self, Ma, k ):
        # A/A* for isentropic flow
        return ( 1.0/Ma ) * ( ( 2.0/(k+1.0) )
                 * ( 1.0 + 0.5*(k-1.0)*Ma*Ma ) )**( 0.5*(k+1.0)/(k-1.0) )

    def _area_guess(self, T1, p1, Ma1, A1, A2, FAR, supersonic ):
        """
        Starting values for a duct, taken from the isentropic area relation with
        a frozen gamma. The inflow regime selects the branch.
        """
        k = self.gamma( T1, FAR )
        target = self._area_mach( Ma1, k ) * A2 / A1

        lo, hi = ( 1.0, 50.0 ) if supersonic else ( 1e-6, 1.0 )
        for _ in range( 200 ):
            Ma2 = 0.5 * ( lo + hi )
            if ( self._area_mach( Ma2, k ) > target ) == supersonic :
                hi = Ma2
            else :
                lo = Ma2
        Ma2 = 0.5 * ( lo + hi )

        Tt = T1 * ( 1.0 + 0.5*(k-1.0)*Ma1*Ma1 )
        T2 = Tt / ( 1.0 + 0.5*(k-1.0)*Ma2*Ma2 )
        p2 = p1 * ( T2/T1 )**( k/(k-1.0) )
        u2 = Ma2 * math.sqrt( k * self.R( FAR ) * T2 )

        return T2, p2, u2

    def _isen_duct(self, T1, p1, dotm, s1, ht, A2, T2, p2, u2, FAR ):
        """
        Solves mass, entropy and energy for a duct in which the flow stays
        isentropic. T2, p2 and u2 enter as the initial guess.
        """
        # The C++ refines the guess here with a Gauss-Seidel sweep that closes
        # velocity through u2 = sqrt( 2*( ht - h(T2) ) ). That is only conditioned
        # when the kinetic energy dominates, i.e. supersonically. For a subsonic
        # duct it is a small difference of two large enthalpies and the sweep
        # diverges, so the Newton below starts from the area relation directly.
        R = self.R( FAR )
        omega = 0.9

        J = np.zeros( (3,3) )
        rhs = np.zeros( 3 )

        epsilon = 1.0
        c = 0
        while abs( epsilon ) > 1e-10 :
            rho2 = self.rho( T2, p2, FAR )

            dotm2 = A2 * u2 * rho2

            # d(mass)/dT
            J[0,0] = -dotm2/(dotm*T2)

            # d(mass) / dp
            J[0,1] = dotm2/ ( p2 * dotm )

            # d(mass)/du
            J[0,2] = rho2 * A2 / dotm

            # the entropy row is scaled with R, not with s itself: the entropy
            # reference is arbitrary and s can pass through zero
            # d(entropy)/dT
            J[1,0] = self.dsdT( T2, FAR ) / R

            # d(entropy)/dp
            J[1,1] = self.dsdp( p2, FAR ) / R

            # d(entropy)/du
            J[1,2] = 0.

            #  d(energy)/dT
            J[2,0] = self.cp( T2, FAR ) / ht

            #  d(energy)/dp
            J[2,1] = 0.

            #  d(energy)/du
            J[2,2] = u2/ht

            rhs[0] = ( dotm2 - dotm ) / dotm
            rhs[1] = ( self.s( T2, p2, FAR ) - s1 ) / R
            rhs[2] = ( self.h( T2, FAR ) + 0.5*u2*u2 - ht ) / ht

            epsilon = np.linalg.norm( rhs )

            y = np.linalg.solve( J, rhs )
            T2 -= omega * y[0]
            p2 -= omega * y[1]
            u2 -= omega * y[2]

            c += 1

            if c == self._maxit :
                raise Exception( "Maximum number of iterations reached" )

        return T2, p2, u2

    def compress(self, T1 : float, p1: float, u1 : float, A1 : float, A2: float, FAR=0.0 ):

        T2 = T1
        p2 = p1
        u2 = u1

        if( abs( A1-A2 ) < 1E-9 ):
            return T2, p2, u2

        if A2 > A1 :
            raise ValueError( "compress needs A1 >= A2, use expand for a widening duct" )

        # mass
        dotm = self.rho( T1, p1, FAR ) * u1 * A1

        # entropy
        s1 = self.s( T1, p1, FAR )

        # energy
        ht = self.h( T1, FAR ) + 0.5*u1**2

        Ma1 = u1/self.c( T1, FAR )
        supersonic = Ma1 > 1.0

        # A contraction accelerates a subsonic flow and decelerates a supersonic
        # one. It does not separate, so there is no Borda-Carnot loss and the flow
        # stays isentropic on either branch -- only the root differs.
        k = self.gamma( T1, FAR )
        if self._area_mach( Ma1, k ) * A2 / A1 < 1.0 :
            raise Exception(
                "the duct is choked, A2 is below the sonic area of "
                f"{A1/self._area_mach( Ma1, k ):.6g} m^2" )

        T2, p2, u2 = self._area_guess( T1, p1, Ma1, A1, A2, FAR, supersonic )
        T2, p2, u2 = self._isen_duct( T1, p1, dotm, s1, ht, A2, T2, p2, u2, FAR )

        if ( u2 / self.c( T2, FAR ) > 1.0 ) != supersonic :
            raise Exception( "the flow changed regime inside the contraction" )

        return T2, p2, u2

    def expand(self, T1 : float, p1: float, u1 : float, A1 : float, A2: float, FAR=0.0,
               sudden=True ):
        """
        Widening duct. sudden=True is a step, where a subsonic flow separates and
        loses total pressure to a Borda-Carnot shock. sudden=False is a gradual
        diffuser, which does not separate and stays isentropic. A supersonic flow
        expands around the corner either way, so the flag does not affect it.
        """

        T2 = T1
        p2 = p1
        u2 = u1

        if( abs( A1-A2 ) < 1E-9 ):
            return T2, p2, u2

        if A2 < A1 :
            raise ValueError( "expand needs A2 >= A1, use compress for a narrowing duct" )

        # relaxation factor
        omega = 0.9

        # mass
        dotm = self.rho( T1, p1, FAR ) * u1 * A1

        # momentum, only used for the subsonic Borda-Carnot shock
        F = dotm * u1 + p1 * A2 # not a typo, using A2 here

        # entropy, only used for the supersonic isentropic expansion
        s1 = self.s( T1, p1, FAR )

        # energy
        ht = self.h( T1, FAR ) + 0.5*u1**2
        Ma1 = u1/self.c( T1, FAR )

        J = np.zeros( (3,3) )
        rhs = np.zeros(3)


        if Ma1 < 1 and sudden :

            k = self.gamma( T1, FAR )

            # calculate a Borda - Carnot Shock
            u2 =  u1 * ( k * Ma1**2 + A2 / A1 -
                   math.sqrt( ( Ma1**2-1)**2 + ( A2 / A1 - 1. ) *
                     ( 1.0 + 2.0 * k * Ma1**2 + A2 / A1 ) ) ) / ( ( k + 1.0 ) * Ma1**2 )

            T2 = self.T( ht - 0.5*u2*u2, FAR )
            p2 = ( dotm * ( u1-u2) + p1*A2 ) / A2

            epsilon = 1.0
            c = 0

            while abs( epsilon ) > 1e-10 :
                rho2 = self.rho( T2, p2, FAR )

                dotm2 = A2 * u2 * rho2

                # d(mass)/dT
                J[0,0] = -dotm2/(dotm*T2)

                # d(mass) / dp
                J[0, 1] = dotm2/ ( p2 * dotm )

                # d(mass)/du
                J[ 0,2 ] = rho2 * A2 / dotm

                # d(momentum)/dT
                J[1,0] = J[0,0]*u2*dotm / F

                # d(momentum)/dP
                J[1, 1] = ( A2 + u2 * J[0,1] * dotm ) / F

                #  d(energy)/dT
                J[ 2,0 ] = self.cp( T2, FAR ) / ht

                #  d(energy)/dp
                J[ 2,1 ] = 0.

                # d(momentum)/du
                J[ 1,2 ] = 2 * dotm2 / F

                #  d(energy)/du
                J[ 2,2 ] = u2/ht

                rhs[ 0 ] = ( dotm2 - dotm ) / dotm
                rhs[ 1 ] = ( u2 * dotm2 + p2*A2 - F ) / F
                rhs[ 2 ] = ( self.h( T2, FAR ) + 0.5*u2*u2 - ht ) / ht

                epsilon = np.linalg.norm( rhs )

                y = np.linalg.solve( J, rhs )
                T2 -= omega * y[0]
                p2 -= omega * y[1]
                u2 -= omega * y[2]

                c += 1

                if ( c == self._maxit ):
                    raise Exception( "Maximum number of iterations reached" )


        else :

            # Either a supersonic flow, which expands around the corner instead of
            # shocking, or a gradual diffuser, which does not separate. Neither
            # conserves momentum in the control volume, but both stay isentropic,
            # so they share the solver with compress().
            supersonic = Ma1 > 1.0

            T2, p2, u2 = self._area_guess( T1, p1, Ma1, A1, A2, FAR, supersonic )
            T2, p2, u2 = self._isen_duct( T1, p1, dotm, s1, ht, A2, T2, p2, u2, FAR )

            if supersonic and u2 / self.c( T2, FAR ) <= 1.0 :
                raise Exception( "Could not find a supersonic solution" )

        return T2, p2, u2

    def static_from_total(self, Tt: float, pt: float, dotm: float, A: float, FAR=0.0 ):
        """
        Static state of a stream with known total conditions, mass flow and cross
        section. Solves continuity, energy and the isentropic total-static
        relation by fixed-point iteration and returns T, p, u, Ma. Converges to
        the subsonic branch; a supersonic mass flow raises an exception.
        """
        ht = self.h( Tt, FAR )

        # starting from rest: the first pass evaluates the density at total
        # conditions, each following pass at the current static state
        T = Tt
        p = pt
        u = 0.0

        c = 0
        while True:
            u_old = u
            u = dotm / ( A * self.rho( T, p, FAR ) )
            h = ht - 0.5*u*u
            if h <= 0.0:
                raise Exception( "no subsonic solution: mass flow too large for the area" )
            T = self.T( h, FAR )
            p = self.isenp( Tt, pt, T, FAR )
            if abs( u - u_old ) < 1e-10 * max( u, 1.0 ):
                break
            c += 1
            if c == self._maxit :
                raise Exception( "Maximum number of iterations reached" )

        Ma = u / self.c( T, FAR )
        if Ma > 1.0 :
            raise Exception( "the flow is supersonic, the subsonic branch does not exist" )

        return T, p, u, Ma
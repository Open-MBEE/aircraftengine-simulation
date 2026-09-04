import math
import numpy as np


class Atmosphere :

    # defining constants of the U.S. Standard Atmosphere 1976 (ISA)
    _R_STAR = 8.31432e3   # universal gas constant in J/(kmol K), as fixed by the standard
    _M0     = 28.9644     # mean molecular weight of dry air in kg/kmol
    _G0     = 9.80665     # standard gravity in m/s^2
    _R_EARTH = 6356766.0  # effective earth radius in m, defined by the standard

    # the layer model of the standard is defined between these geopotential altitudes
    _H_MIN = -5.0e3
    _H_MAX = 84.852e3

    def __init__( self ):

        self._T0 = 288.15
        self._p0 = 101325.0
        self._R = self._R_STAR / self._M0   # 287.05307 J/(kg K)

        self._g0 = self._G0
        self._earth_radius = self._R_EARTH

        # geopotential altitudes of the layer boundaries in m
        self._h = np.array( [0.0e0, 11.0e3, 20.0e3, 32.0e3, 47.0e3, 51.0e3, 71.0e3, self._H_MAX] )

        # molecular scale temperature gradients of the layers in K/m
        self._l = np.array( [ -6.5e-3, 0.0, 1.0e-3,  2.8e-3, 0.0e00, -2.8e-3, -2.0e-3] )

    def atm(self, alt: float  ):
        """
        Temperature, pressure and density at the geometric altitude alt in m,
        following the U.S. Standard Atmosphere 1976.
        """

        h = self._earth_radius * alt / ( self._earth_radius + alt )

        if not self._H_MIN <= h <= self._H_MAX :
            raise ValueError(
                f"geometric altitude {alt:.1f} m is outside the range of the ISA 1976 layer model "
                f"({self._H_MIN*1e-3:.0f} km to {self._H_MAX*1e-3:.3f} km geopotential)" )

        T = self._T0
        p = self._p0

        n = len( self._h )
        j = 0
        h1 = self._h[ 0 ]
        for k in range( 1, n ):

            h0 = h1
            h1 = self._h[ k ]

            l0 = self._l[ k-1 ]
            if self._h[ k ] >= h :
                j = k - 1
                break
            else:
                if l0 != 0 :
                    T0 = T
                    T += l0 * ( h1- h0 )
                    p *= math.pow( T/T0, -self._g0 / ( self._R * l0 ) )
                else :
                    p *= math.exp( -self._g0 * ( h1 - h0 ) / ( self._R * T ) )

        l0 = self._l[ j ]
        h0 = self._h[ j ]
        if l0 != 0:
            T0 = T
            T += l0 * (h - h0)
            p *= math.pow(T / T0, -self._g0 / (self._R * l0))
        else:
            p *= math.exp(-self._g0 * ( h - h0) / (self._R * T))


        rho = p / ( self._R * T )

        return T, p, rho

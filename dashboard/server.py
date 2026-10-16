"""
Local dashboard for the design-point cycle deck in main.py.

Serves a static page (static/index.html) with an "Input variables" pane
(T0 / FAR, each as a start/end/stepsize sweep row) and an "Output results"
pane. The "Start Sim" button posts the sweep configuration to /api/sweep,
which runs main.run_cycle() once per grid point and returns the results as
JSON; a grid point that raises (e.g. an unchoked nozzle) is reported with its
error message instead of aborting the whole sweep.
"""

import sys
from pathlib import Path

sys.path.insert( 0, str( Path( __file__ ).resolve().parent.parent ) )

from flask import Flask, jsonify, request, send_from_directory

import main as cycle

app = Flask( __name__, static_folder="static", static_url_path="" )

MAX_GRID_POINTS = 2000


def _axis_values( cfg ):
    start = float( cfg[ "start" ] )
    end   = float( cfg[ "end" ] )
    step  = float( cfg[ "step" ] )

    if step == 0 :
        return [ start ]
    if ( end - start ) * step < 0 :
        raise ValueError( "stepsize sign does not match the start/end direction" )

    n = int( round( ( end - start ) / step ) )
    return [ start + i * step for i in range( n + 1 ) ]


@app.route( "/" )
def index():
    return send_from_directory( app.static_folder, "index.html" )


@app.route( "/api/sweep", methods=[ "POST" ] )
def sweep():
    payload = request.get_json( force=True )

    try:
        t0_values  = _axis_values( payload[ "T0" ] )
        far_values = _axis_values( payload[ "FAR" ] )
    except ( KeyError, ValueError ) as exc:
        return jsonify( { "error": str( exc ) } ), 400

    if len( t0_values ) * len( far_values ) > MAX_GRID_POINTS :
        return jsonify( { "error":
            f"grid too large ({len(t0_values)} x {len(far_values)} points, "
            f"max {MAX_GRID_POINTS}); widen the stepsize" } ), 400

    results = []
    for t0 in t0_values :
        for far in far_values :
            try:
                r = cycle.run_cycle( T0_override=t0, FAR=far, verbose=False )
                results.append( {
                    "T0": t0, "FAR": far,
                    "F": r[ "F" ] * 1e-3,          # kN
                    "TSFC": r[ "TSFC" ],           # g/(kN s)
                    "eta_th": r[ "eta_th" ],
                    "eta_p": r[ "eta_p" ],
                    "eta_o": r[ "eta_o" ],
                    "Tt4": r[ "Tt4" ],             # K
                    "error": None,
                } )
            except Exception as exc:
                results.append( {
                    "T0": t0, "FAR": far,
                    "F": None, "TSFC": None, "eta_th": None, "eta_p": None,
                    "eta_o": None, "Tt4": None,
                    "error": str( exc ),
                } )

    return jsonify( { "results": results } )


if __name__ == "__main__":
    app.run( port=5000, debug=False )

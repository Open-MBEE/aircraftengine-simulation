"""
Local dashboard for the whole engine cycle, all stations
(SysMLengineMethod2/model/EngineCycleFPB.sysml, CycleService FPB).

Every run goes through the Service Binding Manager, i.e. FPB binding method 2:
the SBM reads the @ServiceBinding / @ParameterBinding metadata from the model,
calls main.run_cycle() and maps the returned dict back onto the FPB's out
parameters (every station's values plus performance).

Only user-modifiable parameters are exposed: the FPB's 'in' parameters (the
design point and the optional T0), minus run controls such as 'verbose'.
Inputs, their model values and the outputs come from the model (/api/fpb),
so editing the .sysml file changes the dashboard on the next reload.

    python SysMLengineMethod2/cycle_dashboard/server.py      ->  http://localhost:5002
"""

import contextlib
import io
import sys
from pathlib import Path

REPO_ROOT = Path( __file__ ).resolve().parents[ 2 ]
sys.path.insert( 0, str( REPO_ROOT ) )      # for 'main' and 'SysMLengineMethod2.sbm'

from flask import Flask, jsonify, request, send_from_directory

from SysMLengineMethod2.sbm import SbmError, ServiceBindingManager
from SysMLengineMethod2.sbm.model_repo import ModelError

USAGE = "AircraftEngineCycleFPB::cruise"

# in parameters that steer the run rather than describe the engine or flight
# condition; never shown on the dashboard, never accepted from it
RUN_CONTROLS = { "verbose" }

app = Flask( __name__, static_folder="static", static_url_path="" )


def _sbm():
    # built per request: re-reads the .sysml files, so model edits show up
    # without restarting the server
    return ServiceBindingManager()


def _user_inputs( definition ):
    return [ p for p in definition.params( "in" ) if p.name not in RUN_CONTROLS ]


@app.route( "/" )
def index():
    return send_from_directory( app.static_folder, "index.html" )


@app.route( "/api/fpb" )
def fpb():
    """The FPB's user-modifiable inputs (with the usage's values) and its
    outputs, straight from the model."""
    try:
        sbm = _sbm()
        usage = sbm.repo.resolve( USAGE )
        definition = sbm.repo.definition_of( usage )
        values = sbm.repo.effective_values( usage )
    except ( SbmError, ModelError ) as exc:
        return jsonify( { "error": str( exc ) } ), 500

    sb = definition.metadata.get( "ServiceBinding", {} )
    return jsonify( {
        "usage": usage.fqn,
        "definition": definition.fqn,
        "service": f"{sb.get( 'module' )}.{sb.get( 'function' )}",
        "inputs": [
            { "name": p.name, "value": values.get( p.name ), "optional": p.optional }
            for p in _user_inputs( definition )
        ],
        "outputs": [ p.name for p in definition.params( "out" ) ],
    } )


@app.route( "/api/invoke", methods=[ "POST" ] )
def invoke():
    """Invoke the usage with the page's input values as overrides; return the
    out parameters plus the SBM's console trace."""
    overrides = ( request.get_json( force=True ) or {} ).get( "inputs", {} )

    try:
        sbm = _sbm()
        definition = sbm.repo.definition_of( sbm.repo.resolve( USAGE ) )
    except ( SbmError, ModelError ) as exc:
        return jsonify( { "error": str( exc ) } ), 500

    allowed = { p.name for p in _user_inputs( definition ) }
    unknown = sorted( set( overrides ) - allowed )
    if unknown:
        return jsonify( { "error": f"not a user-modifiable parameter: {', '.join( unknown )}" } ), 400
    try:
        overrides = { k: float( v ) for k, v in overrides.items() }
    except ( TypeError, ValueError ):
        return jsonify( { "error": "inputs must be numbers" } ), 400

    log = io.StringIO()
    try:
        with contextlib.redirect_stdout( log ):
            results = sbm.invoke( USAGE, overrides )
    except ( SbmError, ModelError ) as exc:
        return jsonify( { "error": str( exc ), "log": log.getvalue() } ), 400
    except Exception as exc:                # the cycle itself failed, e.g. an unchoked nozzle
        return jsonify( { "error": f"{type( exc ).__name__}: {exc}",
                          "log": log.getvalue() } ), 422

    return jsonify( {
        "results": { k: float( v ) for k, v in results.items() },
        "log": log.getvalue(),
    } )


if __name__ == "__main__":
    app.run( port=5002, debug=False )

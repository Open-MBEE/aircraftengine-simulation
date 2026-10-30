"""
Local dashboard for the station-1 FPB (SysMLengineMethod2/model/Station1FPB.sysml).

Every run goes through the Service Binding Manager, i.e. FPB binding method 2:
the SBM reads the @ServiceBinding / @ParameterBinding metadata from the model,
calls main.captured_stream_tube() and maps the result back onto the FPB's out
parameters. The page's inputs, their model values and the outputs all come
from the model (/api/fpb), so editing the .sysml file changes the dashboard
on the next reload.

    python SysMLengineMethod2/dashboard/server.py      ->  http://localhost:5001
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

USAGE = "AircraftEngineStation1FPB::cruiseStation1"

app = Flask( __name__, static_folder="static", static_url_path="" )


def _sbm():
    # built per request: re-reads the .sysml files, so model edits show up
    # without restarting the server
    return ServiceBindingManager()


@app.route( "/" )
def index():
    return send_from_directory( app.static_folder, "index.html" )


@app.route( "/api/fpb" )
def fpb():
    """The FPB's parameters and the usage's values, straight from the model."""
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
        "parameters": [
            {
                "name": p.name,
                "direction": p.direction,
                "type": p.type_name,
                "pythonName": p.metadata.get( "ParameterBinding", {} )
                                       .get( "pythonName", p.name ),
                "value": values.get( p.name ),
            }
            for p in definition.parameters
        ],
    } )


@app.route( "/api/invoke", methods=[ "POST" ] )
def invoke():
    """Invoke the usage with the page's input values as overrides; return the
    out parameters plus the SBM's console trace."""
    overrides = ( request.get_json( force=True ) or {} ).get( "inputs", {} )
    try:
        overrides = { k: float( v ) for k, v in overrides.items() }
    except ( TypeError, ValueError ):
        return jsonify( { "error": "inputs must be numbers" } ), 400

    log = io.StringIO()
    try:
        with contextlib.redirect_stdout( log ):
            results = _sbm().invoke( USAGE, overrides )
    except ( SbmError, ModelError ) as exc:
        return jsonify( { "error": str( exc ), "log": log.getvalue() } ), 400
    except Exception as exc:                # the service itself failed
        return jsonify( { "error": f"{type( exc ).__name__}: {exc}",
                          "log": log.getvalue() } ), 500

    return jsonify( {
        "results": { k: float( v ) for k, v in results.items() },
        "log": log.getvalue(),
    } )


if __name__ == "__main__":
    app.run( port=5001, debug=False )

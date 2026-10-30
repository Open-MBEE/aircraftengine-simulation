// Station-1 dashboard: inputs and outputs come from the FPB in the model
// (/api/fpb); every change re-invokes the FPB through the Service Binding
// Manager (/api/invoke).

// presentation only -- names, directions and values come from the model
const META = {
	rho0:  { desc: "free-stream static density", unit: "kg/m³", min: 0.05, max: 1.3,  step: 0.001 },
	u0:    { desc: "free-stream velocity",       unit: "m/s",   min: 0,    max: 350,  step: 0.1 },
	Do:    { desc: "compressor face outer diameter", unit: "m", min: 0.3,  max: 1.5,  step: 0.005 },
	A1:    { desc: "capture area",               unit: "m²",    digits: 4 },
	dotm1: { desc: "captured mass flow",         unit: "kg/s",  digits: 3 },
};

const state = {
	inputs: [],       // [{name, value(model), current}]
	outputs: [],      // [name]
	baseline: null,   // results at the model values
	timer: null,
	seq: 0,
};

const $ = ( id ) => document.getElementById( id );

function setStatus( text, isError = false ) {
	$( "status" ).textContent = text;
	$( "status" ).classList.toggle( "error", isError );
}

function fmtInput( v ) {
	return Number.isFinite( v ) ? String( +v.toPrecision( 10 ) ) : "";
}

// ---- inputs ----------------------------------------------------------------

function buildInputs() {
	const root = $( "inputs" );
	root.innerHTML = "";
	for ( const p of state.inputs ) {
		const m = META[ p.name ] || { desc: "", unit: "", min: 0, max: Math.max( 1, p.value * 2 ), step: "any" };
		const row = document.createElement( "div" );
		row.className = "input-row";
		row.innerHTML = `
			<div class="input-label">
				<span class="name">${p.name}</span>
				<span class="desc">${m.desc}</span>
			</div>
			<div class="input-controls">
				<input type="range" min="${m.min}" max="${m.max}" step="${m.step}" aria-label="${p.name} slider">
				<input type="number" step="any" aria-label="${p.name}">
				<span class="unit">${m.unit}</span>
			</div>
			<div class="model-value"></div>`;
		const range = row.querySelector( "input[type=range]" );
		const num = row.querySelector( "input[type=number]" );
		p.range = range;
		p.num = num;
		p.note = row.querySelector( ".model-value" );

		range.addEventListener( "input", () => setInput( p, parseFloat( range.value ), "range" ) );
		num.addEventListener( "input", () => {
			const v = parseFloat( num.value );
			if ( Number.isFinite( v ) ) setInput( p, v, "num" );
		} );
		root.appendChild( row );
		setInput( p, p.value, null, false );
	}
}

function setInput( p, v, source, run = true ) {
	p.current = v;
	if ( source !== "range" ) p.range.value = v;
	if ( source !== "num" ) p.num.value = fmtInput( v );
	const changed = Math.abs( v - p.value ) > 1e-12 * Math.max( 1, Math.abs( p.value ) );
	p.note.textContent = `model value: ${fmtInput( p.value )}` + ( changed ? "  (overridden)" : "" );
	p.note.classList.toggle( "changed", changed );
	if ( run ) scheduleRun();
}

// ---- outputs ---------------------------------------------------------------

function buildOutputs() {
	const root = $( "outputs" );
	root.innerHTML = "";
	for ( const name of state.outputs ) {
		const m = META[ name ] || { desc: "", unit: "" };
		const tile = document.createElement( "div" );
		tile.className = "tile";
		tile.id = `tile-${name}`;
		tile.innerHTML = `
			<div class="label">${name} &middot; ${m.desc}</div>
			<div class="value">–<span class="unit">${m.unit}</span></div>
			<div class="delta">&nbsp;</div>`;
		root.appendChild( tile );
	}
}

function showResults( results ) {
	for ( const name of state.outputs ) {
		const m = META[ name ] || { digits: 4, unit: "" };
		const tile = $( `tile-${name}` );
		const v = results[ name ];
		tile.querySelector( ".value" ).innerHTML =
			`${v.toFixed( m.digits ?? 4 )}<span class="unit">${m.unit}</span>`;

		const delta = tile.querySelector( ".delta" );
		const base = state.baseline && state.baseline[ name ];
		delta.classList.remove( "up", "down" );
		if ( base === undefined || base === null ) {
			delta.innerHTML = "&nbsp;";
		} else if ( Math.abs( v - base ) <= 1e-12 * Math.max( 1, Math.abs( base ) ) ) {
			delta.textContent = "= model value";
		} else {
			const pct = ( v - base ) / base * 100;
			delta.textContent = `${pct > 0 ? "+" : ""}${pct.toFixed( 2 )}% vs model (${base.toFixed( m.digits ?? 4 )})`;
			delta.classList.add( pct > 0 ? "up" : "down" );
		}
	}
}

// ---- server calls ------------------------------------------------------------

async function invoke( inputs ) {
	const res = await fetch( "/api/invoke", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify( { inputs } ),
	} );
	const data = await res.json();
	$( "trace" ).textContent = data.log || "";
	if ( !res.ok ) throw new Error( data.error || `HTTP ${res.status}` );
	return data.results;
}

function scheduleRun() {
	clearTimeout( state.timer );
	state.timer = setTimeout( run, 120 );
}

async function run() {
	const seq = ++state.seq;
	const inputs = Object.fromEntries( state.inputs.map( ( p ) => [ p.name, p.current ] ) );
	setStatus( "Running…" );
	try {
		const results = await invoke( inputs );
		if ( seq !== state.seq ) return;          // a newer run superseded this one
		showResults( results );
		setStatus( `Ran via SBM at ${new Date().toLocaleTimeString()}` );
	} catch ( err ) {
		if ( seq === state.seq ) setStatus( err.message, true );
	}
}

async function init() {
	try {
		const res = await fetch( "/api/fpb" );
		const fpb = await res.json();
		if ( !res.ok ) throw new Error( fpb.error || `HTTP ${res.status}` );

		$( "usage-fqn" ).textContent = fpb.usage;
		$( "service-name" ).textContent = `${fpb.service}()`;
		state.inputs = fpb.parameters
			.filter( ( p ) => p.direction === "in" )
			.map( ( p ) => ( { name: p.name, value: p.value, current: p.value } ) );
		state.outputs = fpb.parameters.filter( ( p ) => p.direction === "out" ).map( ( p ) => p.name );

		buildInputs();
		buildOutputs();

		// baseline at the model's own values (no overrides)
		state.baseline = await invoke( {} );
		showResults( state.baseline );
		setStatus( `Ran via SBM at ${new Date().toLocaleTimeString()}` );
	} catch ( err ) {
		setStatus( err.message, true );
	}
}

$( "reset" ).addEventListener( "click", () => {
	for ( const p of state.inputs ) setInput( p, p.value, null, false );
	run();
} );

init();

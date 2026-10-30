// Whole-cycle dashboard: the user-modifiable inputs and all outputs come from
// the CycleService FPB in the model (/api/fpb); every change re-invokes the
// FPB through the Service Binding Manager (/api/invoke).

// ---- presentation only -- names, values and which ones exist come from the model

// inputs grouped by the station of main.py where each one enters the cycle
// (every input is used at exactly one station; 7, 9 and 3b have none)
const INPUT_GROUPS = [
	[ "0", "Free stream",          [ "alt_ft", "Ma0", "T0" ] ],
	[ "1", "Captured stream tube", [ "Do" ] ],
	[ "2", "Compressor face",      [ "Di" ] ],
	[ "3", "Compressor exit",      [ "OPR", "eta_comp", "AR", "mu_bypass", "mu_cool", "mu_bleed" ] ],
	[ "4", "Combustor exit",       [ "FAR", "eta_comb", "k_aer", "k_th" ] ],
	[ "5", "Turbine exit",         [ "eta_turb", "eta_shaft" ] ],
];
const INPUTS_OF_STATION = Object.fromEntries( INPUT_GROUPS.map( ( [ num, , names ] ) => [ num, names ] ) );

const INPUT_META = {
	alt_ft:    { desc: "altitude",                       unit: "ft",  min: 0,     max: 50000, step: 500 },
	Ma0:       { desc: "flight Mach number",             unit: "-",   min: 0.3,   max: 0.95,  step: 0.01 },
	T0:        { desc: "static temperature override",    unit: "K",   min: 180,   max: 320,   step: 0.5 },
	Do:        { desc: "compressor face outer diameter", unit: "m",   min: 0.3,   max: 1.5,   step: 0.01 },
	Di:        { desc: "inlet cone diameter",            unit: "m",   min: 0,     max: 0.3,   step: 0.005 },
	AR:        { desc: "compressor area ratio A2/A3",    unit: "-",   min: 1,     max: 4,     step: 0.05 },
	OPR:       { desc: "overall pressure ratio",         unit: "-",   min: 2,     max: 50,    step: 0.5 },
	eta_comp:  { desc: "compressor isentropic eff.",     unit: "-",   min: 0.7,   max: 0.95,  step: 0.005 },
	mu_bypass: { desc: "bypass fraction",                unit: "-",   min: 0,     max: 0.6,   step: 0.01 },
	mu_cool:   { desc: "turbine cooling fraction",       unit: "-",   min: 0,     max: 0.1,   step: 0.005 },
	mu_bleed:  { desc: "cabin bleed fraction",           unit: "-",   min: 0,     max: 0.05,  step: 0.001 },
	eta_comb:  { desc: "combustion efficiency",          unit: "-",   min: 0.8,   max: 1,     step: 0.005 },
	FAR:       { desc: "fuel-air ratio",                 unit: "-",   min: 0.01,  max: 0.035, step: 0.0005 },
	k_aer:     { desc: "cold pressure loss parameter",   unit: "-",   min: 0,     max: 30,    step: 0.5 },
	k_th:      { desc: "hot pressure loss parameter",    unit: "-",   min: 0,     max: 2,     step: 0.05 },
	eta_turb:  { desc: "turbine isentropic eff.",        unit: "-",   min: 0.7,   max: 0.95,  step: 0.005 },
	eta_shaft: { desc: "shaft mechanical eff.",          unit: "-",   min: 0.9,   max: 1,     step: 0.005 },
};

// [out name, symbol, unit, scale, decimals]
const PERF = [
	[ "F",        "Net thrust F",          "kN",       1e-3, 2 ],
	[ "TSFC",     "TSFC",                  "g/(kN·s)", 1,    2 ],
	[ "eta_o",    "Overall eff. η0",       "",         1,    3 ],
	[ "eta_th",   "Thermal eff. ηth",      "",         1,    3 ],
	[ "eta_p",    "Propulsive eff. ηp",    "",         1,    3 ],
	[ "dotm1",    "Air mass flow",         "kg/s",     1,    2 ],
	[ "dotmf",    "Fuel flow",             "kg/s",     1,    3 ],
	[ "Tt4",      "Turbine inlet Tt4",     "K",        1,    0 ],
	[ "F_core",   "Core gross thrust",     "kN",       1e-3, 2 ],
	[ "F_byp",    "Bypass gross thrust",   "kN",       1e-3, 2 ],
	[ "F_ram",    "Ram drag",              "kN",       1e-3, 2 ],
];

const BAR = 1e-5, MW = 1e-6;
const STATIONS = [
	[ "0",  "Free stream", [
		[ "T0_used", "T", "K", 1, 2 ], [ "p0", "p", "bar", BAR, 4 ], [ "rho0", "ρ", "kg/m³", 1, 4 ],
		[ "u0", "u", "m/s", 1, 1 ], [ "Tt0", "Tt", "K", 1, 2 ], [ "pt0", "pt", "bar", BAR, 4 ] ] ],
	[ "1",  "Captured stream tube", [
		[ "A1", "A", "m²", 1, 4 ], [ "dotm1", "ṁ", "kg/s", 1, 3 ] ] ],
	[ "2",  "Compressor face", [
		[ "A2", "A", "m²", 1, 4 ], [ "T2", "T", "K", 1, 2 ], [ "p2", "p", "bar", BAR, 4 ],
		[ "Ma2", "Ma", "-", 1, 3 ], [ "Tt2", "Tt", "K", 1, 2 ], [ "pt2", "pt", "bar", BAR, 4 ] ] ],
	[ "3",  "Compressor exit", [
		[ "A3", "A", "m²", 1, 4 ], [ "T3", "T", "K", 1, 2 ], [ "p3", "p", "bar", BAR, 3 ],
		[ "Ma3", "Ma", "-", 1, 3 ], [ "Tt3", "Tt", "K", 1, 2 ], [ "pt3", "pt", "bar", BAR, 3 ],
		[ "Wcomp", "P comp", "MW", MW, 3 ] ] ],
	[ "4",  "Combustor exit", [
		[ "A4", "A", "m²", 1, 4 ], [ "T4", "T", "K", 1, 1 ], [ "p4", "p", "bar", BAR, 3 ],
		[ "Ma4", "Ma", "-", 1, 3 ], [ "Tt4", "Tt", "K", 1, 1 ], [ "pt4", "pt", "bar", BAR, 3 ],
		[ "dotmf", "ṁ fuel", "kg/s", 1, 4 ] ] ],
	[ "5",  "Turbine exit", [
		[ "Tt5", "Tt", "K", 1, 1 ], [ "pt5", "pt", "bar", BAR, 4 ], [ "Wshaft", "P shaft", "MW", MW, 3 ] ] ],
	[ "7",  "Core nozzle throat", [
		[ "A7", "A", "m²", 1, 4 ], [ "T7", "T", "K", 1, 1 ], [ "p7", "p", "bar", BAR, 4 ], [ "u7", "u", "m/s", 1, 1 ] ] ],
	[ "9",  "Core nozzle exit", [
		[ "A9", "A", "m²", 1, 4 ], [ "T9", "T", "K", 1, 1 ], [ "p9", "p", "bar", BAR, 4 ], [ "u9", "u", "m/s", 1, 1 ] ] ],
	[ "3b", "Bypass nozzle exit", [
		[ "A9b", "A", "m²", 1, 4 ], [ "T9b", "T", "K", 1, 1 ], [ "u9b", "u", "m/s", 1, 1 ],
		[ "dotm_byp", "ṁ", "kg/s", 1, 3 ] ] ],
];

// ---- state ---------------------------------------------------------------------

const state = {
	inputs: [],         // [{name, value (model, may be null), optional, current, enabled}]
	outputs: [],        // out parameter names from the model
	baseline: null,     // results at the model values
	last: null,         // latest successful results
	timer: null,
	seq: 0,
};

const $ = ( id ) => document.getElementById( id );

// ---- remembered UI state (this browser only): open/closed panels and which
// design inputs are variables

const UI_KEY = "cycleDashboard.ui";
const ui = loadUi();

function loadUi() {
	const ui = { panelOpen: true, closed: [], inputsOpen: true, variables: [] };
	try {
		const s = JSON.parse( localStorage.getItem( UI_KEY ) );
		if ( s && typeof s === "object" ) {
			ui.panelOpen = s.panelOpen !== false;
			ui.inputsOpen = s.inputsOpen !== false;
			if ( Array.isArray( s.closed ) ) ui.closed = s.closed;
			if ( Array.isArray( s.variables ) ) ui.variables = s.variables;
		}
	} catch ( e ) { /* storage unavailable or corrupt: use defaults */ }
	return ui;
}

function saveUi() {
	ui.panelOpen = $( "stations-pane" ).open;
	ui.inputsOpen = $( "inputs-pane" ).open;
	if ( document.querySelector( "details.station" ) ) {      // cards not built yet: keep the saved list
		ui.closed = [ ...document.querySelectorAll( "details.station:not([open])" ) ].map( ( d ) => d.dataset.station );
	}
	if ( state.inputs.length ) ui.variables = state.inputs.filter( ( p ) => p.isVar ).map( ( p ) => p.name );
	try { localStorage.setItem( UI_KEY, JSON.stringify( ui ) ); } catch ( e ) { /* not persisted */ }
}

function setAllStations( open ) {
	for ( const d of document.querySelectorAll( "details.station" ) ) d.open = open;
	saveUi();
}
const same = ( a, b ) => Math.abs( a - b ) <= 1e-12 * Math.max( 1, Math.abs( b ) );

function fmtInput( v ) {
	return Number.isFinite( v ) ? String( +v.toPrecision( 10 ) ) : "";
}

function setStatus( text, isError = false ) {
	$( "status" ).textContent = text;
	$( "status" ).classList.toggle( "error", isError );
}

function deltaHtml( v, base ) {
	if ( base === undefined || base === null || !Number.isFinite( base ) ) return [ "", "" ];
	if ( same( v, base ) ) return [ "", "" ];
	if ( base === 0 ) return [ "changed", "" ];
	const pct = ( v - base ) / Math.abs( base ) * 100;
	if ( Math.abs( pct ) < 0.005 ) return [ "", "" ];       // would print as ±0.00%
	return [ `${pct > 0 ? "+" : ""}${pct.toFixed( Math.abs( pct ) < 10 ? 2 : 1 )}%`, pct > 0 ? "up" : "down" ];
}

// ---- inputs ----------------------------------------------------------------------

function inputGroups() {
	const have = new Set( state.inputs.map( ( p ) => p.name ) );
	const groups = INPUT_GROUPS.map( ( [ num, title, names ] ) => [ num, title, names.filter( ( n ) => have.has( n ) ) ] );
	const rest = [ ...have ].filter( ( n ) => !INPUT_GROUPS.some( ( [ , , ns ] ) => ns.includes( n ) ) );
	if ( rest.length ) groups.push( [ "–", "Other", rest ] );
	return groups;
}

// each input's row is built once; layoutInputs() moves it between the
// Variables and Design inputs panels (listeners travel with the element)
function buildInputs() {
	for ( const p of state.inputs ) {
		p.isVar = ui.variables.includes( p.name );
		p.row = buildInputRow( p );
	}
	layoutInputs();
}

function layoutInputs() {
	const byName = Object.fromEntries( state.inputs.map( ( p ) => [ p.name, p ] ) );
	for ( const [ rootId, wantVar ] of [ [ "variables", true ], [ "inputs", false ] ] ) {
		const root = $( rootId );
		root.innerHTML = "";
		for ( const [ num, title, names ] of inputGroups() ) {
			const ps = names.map( ( n ) => byName[ n ] ).filter( ( p ) => p.isVar === wantVar );
			if ( !ps.length ) continue;
			const g = document.createElement( "div" );
			g.className = "group";
			g.innerHTML = `<div class="group-title"><span class="num">${num}</span>${title}</div>`;
			for ( const p of ps ) g.appendChild( p.row );
			root.appendChild( g );
		}
		if ( !root.children.length ) {
			root.innerHTML = `<p class="empty">${wantVar
				? "No variables yet — tick <em>variable</em> on a design input below to move it here."
				: "Every design input is a variable."}</p>`;
		}
	}
	const n = state.inputs.filter( ( p ) => p.isVar ).length;
	$( "variables-count" ).textContent = n ? `(${n})` : "";
}

function flashRow( row ) {
	row.classList.remove( "flash" );
	void row.offsetWidth;                       // restart the highlight animation
	row.classList.add( "flash" );
}

function buildInputRow( p ) {
	const v0 = p.value ?? 0;
	const m = INPUT_META[ p.name ] || { desc: "", unit: "", min: 0, max: Math.max( 1, Math.abs( v0 ) * 2 ), step: "any" };
	const row = document.createElement( "div" );
	row.className = "input-row";
	row.innerHTML = `
		<div class="input-label">
			<span class="name">${p.name}</span>
			<span class="toggles">
				<label class="toggle var-toggle" title="variable: explore it with a slider in the Variables panel; unticked: held constant">
					<input type="checkbox" aria-label="${p.name} is a variable"> variable
				</label>
			</span>
			<span class="desc">${m.desc}</span>
		</div>
		<div class="input-controls">
			<input type="range" min="${m.min}" max="${m.max}" step="${m.step}" aria-label="${p.name} slider">
			<input type="number" step="any" aria-label="${p.name}">
			<span class="unit">${m.unit}</span>
		</div>
		<div class="model-value"></div>`;
	p.range = row.querySelector( "input[type=range]" );
	p.num = row.querySelector( "input[type=number]" );
	p.note = row.querySelector( ".model-value" );

	// constant (default) or variable: only moves the row and shows/hides its
	// slider -- both kinds are sent to every run with their current value
	row.addEventListener( "animationend", () => row.classList.remove( "flash" ) );

	p.varBox = row.querySelector( ".var-toggle input" );
	p.varBox.checked = p.isVar;
	row.classList.toggle( "is-variable", p.isVar );
	p.varBox.addEventListener( "change", () => {
		p.isVar = p.varBox.checked;
		row.classList.toggle( "is-variable", p.isVar );
		layoutInputs();
		saveUi();
		row.scrollIntoView( { behavior: "smooth", block: "nearest" } );
		flashRow( row );
	} );

	if ( p.optional ) {
		// optional parameter: unbound unless the user switches the override on
		const t = document.createElement( "label" );
		t.className = "toggle";
		t.innerHTML = `<input type="checkbox" aria-label="override ${p.name}"> override`;
		row.querySelector( ".toggles" ).appendChild( t );
		p.toggle = t.querySelector( "input" );
		p.toggle.addEventListener( "change", () => {
			p.enabled = p.toggle.checked;
			if ( p.enabled && !Number.isFinite( p.current ) ) {
				p.current = state.last ? state.last.T0_used ?? v0 : v0;    // start from the value in use
			}
			syncInput( p );
			scheduleRun();
		} );
	}

	p.range.addEventListener( "input", () => { p.current = parseFloat( p.range.value ); syncInput( p, "range" ); scheduleRun(); } );
	p.num.addEventListener( "input", () => {
		const v = parseFloat( p.num.value );
		if ( Number.isFinite( v ) ) { p.current = v; syncInput( p, "num" ); scheduleRun(); }
	} );
	syncInput( p );
	return row;
}

function syncInput( p, source ) {
	const active = !p.optional || p.enabled;
	p.range.disabled = p.num.disabled = !active;
	if ( p.toggle ) p.toggle.checked = !!p.enabled;

	let shown = p.current;
	if ( !active && p.name === "T0" && state.last ) shown = state.last.T0_used;   // show the ISA value in use
	if ( source !== "range" && Number.isFinite( shown ) ) p.range.value = shown;
	if ( source !== "num" ) p.num.value = fmtInput( shown );

	let changed, text;
	if ( p.optional ) {
		changed = !!p.enabled;
		text = p.enabled ? "model: unbound (standard atmosphere) — overridden" : "model: unbound — standard atmosphere at alt_ft";
	} else {
		changed = !same( p.current, p.value );
		text = `model value: ${fmtInput( p.value )}` + ( changed ? " — overridden" : "" );
	}
	p.note.textContent = text;
	p.note.classList.toggle( "changed", changed );
}

function currentOverrides() {
	const o = {};
	for ( const p of state.inputs ) {
		if ( p.optional ) { if ( p.enabled ) o[ p.name ] = p.current; }
		else if ( !same( p.current, p.value ) ) o[ p.name ] = p.current;
	}
	return o;
}

// ---- outputs -----------------------------------------------------------------------

function buildOutputs() {
	const have = new Set( state.outputs );

	$( "perf" ).innerHTML = PERF.filter( ( [ n ] ) => have.has( n ) ).map( ( [ n, label, unit ] ) => `
		<div class="tile" data-out="${n}">
			<div class="label">${label}</div>
			<div class="value">–<span class="unit">${unit}</span></div>
			<div class="delta">&nbsp;</div>
		</div>` ).join( "" );

	const shown = new Set( [ ...PERF.map( ( r ) => r[ 0 ] ), ...STATIONS.flatMap( ( s ) => s[ 2 ].map( ( r ) => r[ 0 ] ) ) ] );
	const extra = state.outputs.filter( ( n ) => !shown.has( n ) ).map( ( n ) => [ n, n, "", 1, 4 ] );
	const stations = extra.length ? [ ...STATIONS, [ "–", "Other outputs", extra ] ] : STATIONS;

	$( "stations" ).innerHTML = stations.map( ( [ num, title, rows ] ) => {
		const body = rows.filter( ( [ n ] ) => have.has( n ) ).map( ( [ n, sym, unit ] ) => `
			<tr data-out="${n}">
				<td class="sym" title="${n}">${sym}</td>
				<td class="val">–</td>
				<td class="unit">${unit}</td>
				<td class="delta"></td>
			</tr>` ).join( "" );
		if ( !body ) return "";
		const ins = ( INPUTS_OF_STATION[ num ] || [] ).filter( ( n ) => state.inputs.some( ( p ) => p.name === n ) );
		const chips = ins.length
			? `<div class="station-inputs">inputs: ${ins.map( ( n ) =>
				`<button type="button" class="chip" data-input="${n}">${n}</button>` ).join( "" )}</div>`
			: "";
		return `
			<details class="station" data-station="${num}"${ui.closed.includes( num ) ? "" : " open"}>
				<summary class="station-head"><span class="num">${num}</span><span class="title">${title}</span></summary>
				${chips}
				<table>${body}</table>
			</details>`;
	} ).join( "" );

	for ( const card of $( "stations" ).querySelectorAll( "details.station" ) ) {
		card.addEventListener( "toggle", saveUi );
	}

	// a station's input chip jumps to that input in the inputs pane
	for ( const chip of $( "stations" ).querySelectorAll( ".chip" ) ) {
		chip.addEventListener( "click", ( e ) => {
			e.stopPropagation();
			const p = state.inputs.find( ( q ) => q.name === chip.dataset.input );
			const row = p.row;
			const pane = row.closest( "details" );   // a constant inside a collapsed Design inputs panel
			if ( pane && !pane.open ) pane.open = true;
			row.scrollIntoView( { behavior: "smooth", block: "center" } );
			flashRow( row );
			( p.num.disabled ? p.toggle : p.num ).focus( { preventScroll: true } );
		} );
	}
}

function showResults( r ) {
	const fmt = {};
	for ( const [ n, , unit, scale, dec ] of PERF ) fmt[ n ] = { unit, scale, dec };
	const sfmt = {};
	for ( const [ , , rows ] of STATIONS ) for ( const [ n, , unit, scale, dec ] of rows ) sfmt[ n ] = { unit, scale, dec };

	for ( const tile of document.querySelectorAll( ".tile[data-out]" ) ) {
		const n = tile.dataset.out, f = fmt[ n ];
		tile.querySelector( ".value" ).innerHTML = `${( r[ n ] * f.scale ).toFixed( f.dec )}<span class="unit">${f.unit}</span>`;
		const [ txt, cls ] = deltaHtml( r[ n ], state.baseline?.[ n ] );
		const d = tile.querySelector( ".delta" );
		d.className = `delta ${cls}`;
		d.innerHTML = txt ? `${txt} vs model` : "= model value";
	}
	for ( const tr of document.querySelectorAll( "tr[data-out]" ) ) {
		const n = tr.dataset.out, f = sfmt[ n ] || { scale: 1, dec: 4 };
		tr.querySelector( ".val" ).textContent = ( r[ n ] * f.scale ).toFixed( f.dec );
		const [ txt, cls ] = deltaHtml( r[ n ], state.baseline?.[ n ] );
		const d = tr.querySelector( ".delta" );
		d.className = `delta ${cls}`;
		d.textContent = txt;
	}
}

function setStale( stale ) {
	$( "outputs-col" ).querySelectorAll( ".tiles, .stations" ).forEach( ( el ) => el.classList.toggle( "stale", stale ) );
}

// ---- server calls ------------------------------------------------------------------

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
	state.timer = setTimeout( run, 150 );
}

async function run() {
	const seq = ++state.seq;
	setStatus( "Running…" );
	try {
		const r = await invoke( currentOverrides() );
		if ( seq !== state.seq ) return;            // superseded by a newer run
		state.last = r;
		showResults( r );
		for ( const p of state.inputs ) if ( p.optional && !p.enabled ) syncInput( p );
		$( "error-banner" ).hidden = true;
		setStale( false );
		setStatus( `Ran via SBM at ${new Date().toLocaleTimeString()}` );
	} catch ( err ) {
		if ( seq !== state.seq ) return;
		$( "error-banner" ).textContent = `Cycle could not be computed for these inputs — ${err.message}`;
		$( "error-banner" ).hidden = false;
		setStale( true );
		setStatus( "Run failed", true );
	}
}

async function init() {
	try {
		const res = await fetch( "/api/fpb" );
		const fpb = await res.json();
		if ( !res.ok ) throw new Error( fpb.error || `HTTP ${res.status}` );

		$( "usage-fqn" ).textContent = fpb.usage;
		$( "service-name" ).textContent = `${fpb.service}()`;
		state.inputs = fpb.inputs.map( ( p ) => ( { ...p, current: p.value ?? NaN, enabled: false } ) );
		state.outputs = fpb.outputs;

		buildInputs();
		buildOutputs();

		state.baseline = await invoke( {} );          // the model's own values
		state.last = state.baseline;
		showResults( state.baseline );
		for ( const p of state.inputs ) syncInput( p );
		setStatus( `Ran via SBM at ${new Date().toLocaleTimeString()}` );
	} catch ( err ) {
		setStatus( err.message, true );
	}
}

$( "stations-pane" ).open = ui.panelOpen;
$( "stations-pane" ).addEventListener( "toggle", saveUi );
$( "inputs-pane" ).open = ui.inputsOpen;
$( "inputs-pane" ).addEventListener( "toggle", saveUi );
$( "expand-all" ).addEventListener( "click", () => setAllStations( true ) );
$( "collapse-all" ).addEventListener( "click", () => setAllStations( false ) );

$( "reset" ).addEventListener( "click", () => {
	for ( const p of state.inputs ) {
		p.current = p.value ?? NaN;
		p.enabled = false;
		syncInput( p );
	}
	run();
} );

init();

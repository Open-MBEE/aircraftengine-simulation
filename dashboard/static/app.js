const startButton   = document.getElementById( "start-sim" );
const statusEl      = document.getElementById( "results-status" );
const resultsTable   = document.getElementById( "results-table" );
const resultsBody    = resultsTable.querySelector( "tbody" );

const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_SERIES = 8;   // categorical palette slots; never cycle past this

const chartSection = document.getElementById( "chart-section" );
const chartSvg      = document.getElementById( "f-far-chart" );
const chartLegend   = document.getElementById( "chart-legend" );
const chartTooltip  = document.getElementById( "chart-tooltip" );
const chartNote     = document.getElementById( "chart-note" );
const chartWrap     = chartSvg.closest( ".chart-wrap" );

const CHART_W = 640, CHART_H = 340;
const MARGIN = { top: 16, right: 24, bottom: 40, left: 52 };

function axisConfig( prefix ) {
	return {
		start: document.getElementById( `${prefix}-start` ).value,
		end:   document.getElementById( `${prefix}-end` ).value,
		step:  document.getElementById( `${prefix}-step` ).value,
	};
}

function fmt( value, digits ) {
	return value === null || value === undefined ? "—" : value.toFixed( digits );
}

function renderResults( results ) {
	resultsBody.innerHTML = "";

	for ( const r of results ) {
		const tr = document.createElement( "tr" );
		if ( r.error ) {
			tr.classList.add( "row-error" );
			tr.title = r.error;
		}

		tr.innerHTML = `
			<td>${fmt( r.T0, 2 )}</td>
			<td>${fmt( r.FAR, 4 )}</td>
			<td>${fmt( r.F, 3 )}</td>
			<td>${fmt( r.TSFC, 3 )}</td>
			<td>${fmt( r.eta_th, 3 )}</td>
			<td>${fmt( r.eta_p, 3 )}</td>
			<td>${fmt( r.eta_o, 3 )}</td>
			<td>${fmt( r.Tt4, 2 )}</td>
		`;
		resultsBody.appendChild( tr );
	}

	resultsTable.hidden = results.length === 0;
}

function niceTicks( min, max, count = 5 ) {
	if ( min === max ) { min -= 1; max += 1; }
	const span = ( max - min ) || 1;
	const rawStep = span / count;
	const mag = Math.pow( 10, Math.floor( Math.log10( rawStep ) ) );
	const residual = rawStep / mag;
	const step = residual > 5 ? 10 * mag : residual > 2 ? 5 * mag : residual > 1 ? 2 * mag : mag;

	const niceMin = Math.floor( min / step ) * step;
	const niceMax = Math.ceil( max / step ) * step;
	const ticks = [];
	for ( let v = niceMin; v <= niceMax + step * 1e-6; v += step ) {
		ticks.push( Math.round( v / step ) * step );
	}
	return ticks;
}

function svgEl( tag, attrs = {} ) {
	const el = document.createElementNS( SVG_NS, tag );
	for ( const [ k, v ] of Object.entries( attrs ) ) el.setAttribute( k, v );
	return el;
}

function seriesColorVar( slot ) {
	return `var(--series-${slot + 1})`;
}

function renderChart( results ) {
	const points = results.filter( r => r.FAR !== null && r.T0 !== null );

	if ( points.length === 0 ) {
		chartSection.hidden = true;
		return;
	}
	chartSection.hidden = false;

	// group by T0 (one series per distinct T0), capped at the palette size
	const t0Values = [ ...new Set( points.map( p => p.T0 ) ) ].sort( ( a, b ) => a - b );
	const shown = t0Values.slice( 0, MAX_SERIES );

	chartNote.hidden = shown.length === t0Values.length;
	if ( !chartNote.hidden ) {
		chartNote.textContent =
			`Showing the first ${shown.length} of ${t0Values.length} T0 values ` +
			`(narrow the T0 sweep to see the rest).`;
	}

	const series = shown.map( t0 => ( {
		t0,
		points: points
			.filter( p => p.T0 === t0 )
			.sort( ( a, b ) => a.FAR - b.FAR ),
	} ) );

	// x domain: every distinct FAR value swept (used for ticks + snapping)
	const farValues = [ ...new Set( points.map( p => p.FAR ) ) ].sort( ( a, b ) => a - b );
	const farMin = farValues[ 0 ], farMax = farValues[ farValues.length - 1 ];

	const fValues = points.map( p => p.F ).filter( f => f !== null );
	const yTicks = niceTicks( Math.min( ...fValues ), Math.max( ...fValues ), 5 );
	const yMin = yTicks[ 0 ], yMax = yTicks[ yTicks.length - 1 ];

	const innerW = CHART_W - MARGIN.left - MARGIN.right;
	const innerH = CHART_H - MARGIN.top - MARGIN.bottom;

	const xScale = far => farMax === farMin
		? MARGIN.left + innerW / 2
		: MARGIN.left + ( far - farMin ) / ( farMax - farMin ) * innerW;
	const yScale = f => MARGIN.top + innerH - ( f - yMin ) / ( yMax - yMin ) * innerH;

	chartSvg.innerHTML = "";
	chartSvg.setAttribute( "viewBox", `0 0 ${CHART_W} ${CHART_H}` );

	// gridlines + y ticks
	for ( const t of yTicks ) {
		const y = yScale( t );
		chartSvg.appendChild( svgEl( "line", {
			class: "gridline", x1: MARGIN.left, x2: CHART_W - MARGIN.right, y1: y, y2: y,
		} ) );
		const label = svgEl( "text", {
			class: "axis-tick", x: MARGIN.left - 8, y: y + 3, "text-anchor": "end",
		} );
		label.textContent = t.toLocaleString();
		chartSvg.appendChild( label );
	}

	// x axis baseline + ticks
	chartSvg.appendChild( svgEl( "line", {
		class: "axis-line",
		x1: MARGIN.left, x2: CHART_W - MARGIN.right,
		y1: CHART_H - MARGIN.bottom, y2: CHART_H - MARGIN.bottom,
	} ) );
	for ( const far of farValues ) {
		const x = xScale( far );
		const label = svgEl( "text", {
			class: "axis-tick", x, y: CHART_H - MARGIN.bottom + 16, "text-anchor": "middle",
		} );
		label.textContent = far.toString();
		chartSvg.appendChild( label );
	}

	const xTitle = svgEl( "text", {
		class: "axis-title", x: MARGIN.left + innerW / 2, y: CHART_H - 4, "text-anchor": "middle",
	} );
	xTitle.textContent = "FAR";
	chartSvg.appendChild( xTitle );

	const yTitle = svgEl( "text", {
		class: "axis-title", x: 0, y: 12, "text-anchor": "start",
	} );
	yTitle.textContent = "F (kN)";
	chartSvg.appendChild( yTitle );

	// one line per T0 series, broken into segments around missing (failed) points
	series.forEach( ( s, i ) => {
		const color = seriesColorVar( i );
		let segment = [];
		const flushSegment = () => {
			if ( segment.length > 1 ) {
				const d = segment.map( ( p, j ) =>
					`${ j === 0 ? "M" : "L" } ${xScale( p.FAR )} ${yScale( p.F )}` ).join( " " );
				chartSvg.appendChild( svgEl( "path", { class: "series-line", d, stroke: color } ) );
			}
			segment = [];
		};
		for ( const p of s.points ) {
			if ( p.F === null ) { flushSegment(); continue; }
			segment.push( p );
		}
		flushSegment();

		for ( const p of s.points ) {
			if ( p.F === null ) continue;
			chartSvg.appendChild( svgEl( "circle", {
				class: "series-dot", cx: xScale( p.FAR ), cy: yScale( p.F ), r: 4, fill: color,
			} ) );
		}

		if ( series.length <= 4 ) {
			const last = [ ...s.points ].reverse().find( p => p.F !== null );
			if ( last ) {
				const label = svgEl( "text", {
					class: "direct-label", x: xScale( last.FAR ) + 6, y: yScale( last.F ) + 3,
					fill: "var(--ink-secondary)",
				} );
				label.textContent = `T0=${s.t0}`;
				chartSvg.appendChild( label );
			}
		}
	} );

	// crosshair, added last so it draws on top
	const crosshair = svgEl( "line", {
		class: "crosshair", y1: MARGIN.top, y2: CHART_H - MARGIN.bottom,
	} );
	chartSvg.appendChild( crosshair );

	// legend (always present for 2+ series; a single series names itself via the title)
	chartLegend.innerHTML = "";
	if ( series.length > 1 ) {
		series.forEach( ( s, i ) => {
			const item = document.createElement( "div" );
			item.className = "legend-item";
			const key = document.createElement( "span" );
			key.className = "legend-key";
			key.style.background = seriesColorVar( i );
			const text = document.createElement( "span" );
			text.textContent = `T0 = ${s.t0} K`;
			item.append( key, text );
			chartLegend.appendChild( item );
		} );
	}

	// hover: snap to nearest FAR, show every series' value in one tooltip
	chartSvg.onpointermove = ( evt ) => {
		const rect = chartSvg.getBoundingClientRect();
		const scaleX = CHART_W / rect.width;
		const xSvg = ( evt.clientX - rect.left ) * scaleX;

		let nearest = farValues[ 0 ];
		let bestDist = Infinity;
		for ( const far of farValues ) {
			const d = Math.abs( xScale( far ) - xSvg );
			if ( d < bestDist ) { bestDist = d; nearest = far; }
		}

		crosshair.setAttribute( "x1", xScale( nearest ) );
		crosshair.setAttribute( "x2", xScale( nearest ) );
		crosshair.style.display = "block";

		chartTooltip.innerHTML = "";
		const farRow = document.createElement( "div" );
		farRow.className = "tooltip-far";
		farRow.textContent = `FAR = ${nearest}`;
		chartTooltip.appendChild( farRow );

		series.forEach( ( s, i ) => {
			const p = s.points.find( pt => pt.FAR === nearest );
			const row = document.createElement( "div" );
			row.className = "tooltip-row";
			const key = document.createElement( "span" );
			key.className = "tooltip-key";
			key.style.background = seriesColorVar( i );
			const name = document.createElement( "span" );
			name.className = "tooltip-name";
			name.textContent = `T0=${s.t0}`;
			const value = document.createElement( "span" );
			value.className = "tooltip-value";
			value.textContent = p && p.F !== null ? p.F.toFixed( 3 ) : "—";
			row.append( key, name, value );
			chartTooltip.appendChild( row );
		} );

		const wrapRect = chartWrap.getBoundingClientRect();
		const scaleY = CHART_H / rect.height;
		const pxX = ( rect.left - wrapRect.left ) + xScale( nearest ) / scaleX;
		chartTooltip.style.display = "block";
		chartTooltip.style.left = `${Math.min( pxX + 12, wrapRect.width - 140 )}px`;
		chartTooltip.style.top = `${MARGIN.top / scaleY}px`;
	};
	chartSvg.onpointerleave = () => {
		crosshair.style.display = "none";
		chartTooltip.style.display = "none";
	};
}

async function startSim() {
	startButton.disabled = true;
	statusEl.textContent = "Running…";
	statusEl.classList.remove( "error" );
	resultsTable.hidden = true;
	chartSection.hidden = true;

	const payload = {
		T0:  axisConfig( "t0" ),
		FAR: axisConfig( "far" ),
	};

	try {
		const response = await fetch( "/api/sweep", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify( payload ),
		} );
		const data = await response.json();

		if ( !response.ok ) {
			throw new Error( data.error || `request failed (${response.status})` );
		}

		const failed = data.results.filter( r => r.error ).length;
		statusEl.textContent = failed === 0
			? `${data.results.length} point(s) computed.`
			: `${data.results.length} point(s) computed, ${failed} failed (hover a row for the reason).`;

		renderResults( data.results );
		renderChart( data.results );
	} catch ( err ) {
		statusEl.textContent = `Error: ${err.message}`;
		statusEl.classList.add( "error" );
	} finally {
		startButton.disabled = false;
	}
}

startButton.addEventListener( "click", startSim );

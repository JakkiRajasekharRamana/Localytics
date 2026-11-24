// Colour buildings by indicative PM2.5 (nearest monitor within a few km), instead of by search match.
// Colours and bands come from the city data so they match the Localytics app. Not an official AQI.
import './airlayer.css';

const NO_DATA = '#6b6b73';

const byBand = (bands, fallback = NO_DATA) => ['case', ['boolean', ['feature-state', 'sel'], false], '#ffffff',
  ['match', ['get', 'aq'], ...bands.flatMap((b, i) => [i, b.color]), fallback]];

// Overrides the paint of the society layers. Call setBaseMode() first to go back to search-match colours.
export function setAirMode(map, bands) {
  if (!map?.getLayer?.('bld')) return;
  map.setPaintProperty('bld', 'fill-extrusion-color', byBand(bands));
  map.setPaintProperty('site-fill', 'fill-color', byBand(bands));
  map.setPaintProperty('site-fill', 'fill-opacity', 0.3);
  map.setPaintProperty('site-line', 'line-color', byBand(bands));
  map.setPaintProperty('site-line', 'line-opacity', 0.95);
  map.setPaintProperty('glow', 'circle-color', byBand(bands));
  map.setPaintProperty('glow', 'circle-opacity', 0.55);
}

const escapeHtml = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

export function airLegend(air) {
  const rows = air.bands.map((b, i) => {
    const lo = i === 0 ? 0 : air.bands[i - 1].upper;
    const range = b.upper == null ? `> ${lo}` : `${i === 0 ? 0 : lo + 1}–${b.upper}`;
    return `<span><i style="background:${escapeHtml(b.color)}"></i>${escapeHtml(b.label)} <small>${range}</small></span>`;
  }).join('');
  const fetched = air.fetched ? ` Readings last cached ${escapeHtml(String(air.fetched).slice(0, 10))}.` : '';
  return `<b>PM2.5, µg/m³ (nearest monitor)</b><div class="air-bands">${rows}<span><i style="background:${NO_DATA}"></i>No monitor nearby</span></div>`
    + `<small>${escapeHtml(air.note)}${fetched}</small>`;
}

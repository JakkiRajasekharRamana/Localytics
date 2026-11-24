// "Ask Localytics": a side chat that asks what you need, runs a real search, and highlights the best areas on the map.
// The assistant (Claude) only asks questions and fills in a brief. The search runs in integration/advisor.py over the same data
// as the map, so every number shown here is measured, and the building count equals what the filter panel shows.
// Without an API key the same search runs from a short form.
import './advisor.css';
import maplibregl from 'maplibre-gl';
import { formatINR } from './filters.js';

const API = '/api/localytics/advisor';
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const EXAMPLES = [
  ["I'm moving for work near Golf Course Road. 3 BHK to rent, around ₹70k a month, and air quality matters to me.", 'Work near Golf Course Road'],
  ['2 BHK to buy in Gurugram under ₹1.5 crore, with a metro nearby.', 'Buy in Gurugram near a metro'],
  ['Cheapest 2 BHK rents in Delhi with a metro and a school close by.', 'Delhi rents near metro and school'],
  ['Find me a nice place to live.', 'A vague request (it will ask)'],
];
const RENT_BUDGETS = [['', 'No limit'], [15000, '₹15k'], [25000, '₹25k'], [40000, '₹40k'], [60000, '₹60k'], [90000, '₹90k'], [150000, '₹1.5 L']];
const BUY_BUDGETS = [['', 'No limit'], [5e6, '₹50 L'], [1e7, '₹1 Cr'], [2e7, '₹2 Cr'], [3e7, '₹3 Cr'], [5e7, '₹5 Cr'], [1e8, '₹10 Cr']];
const NEAR_LABEL = { metro: 'Metro or rail', school: 'School', park: 'Park', hospital: 'Hospital', shopping: 'Mall or supermarket' };

let ctx, llm = false, quick = false, formOpen = true, busy = false, session = '';
let areas = [], pins = [], active = null;
const store = { get: (k, d) => { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } } };

const newSession = () => (crypto.randomUUID ? crypto.randomUUID() : `s${Date.now()}${Math.random().toString(16).slice(2)}`);

async function post(path, body) {
  let r;
  try {
    r = await fetch(`${API}/${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  } catch {
    throw { error: 'offline', message: 'Could not reach the Localytics data service. Start it (see the README), then try again.' };
  }
  if (!(r.headers.get('content-type') || '').includes('application/json')) throw { error: 'offline', message: 'The Localytics data service is not running. Start it (see the README), then try again.' };
  const j = await r.json();
  if (!r.ok) throw j;
  return j;
}

// ---------- the thread ----------
function say(role, text) {
  const el = document.createElement('div');
  el.className = `adv-msg ${role}`;
  el.textContent = role.startsWith('bot') ? text.replace(/\*\*(.+?)\*\*/g, '$1') : text; // never innerHTML: the text comes from a model; drop stray **bold** marks
  $('adv-thread').append(el);
  scroll();
  return el;
}
const scroll = () => { const t = $('adv-thread'); t.scrollTop = t.scrollHeight; };

function greet() {
  $('adv-thread').replaceChildren();
  say('bot', quick
    ? 'Tell me what you need and I will rank areas and highlight them on the map. Fill in what you know; budget and BHK matter most.'
    : 'Tell me what you are looking for (rent or buy, bedrooms, budget, where you work, what matters) and I will find areas and highlight them on the map. If something is unclear I will ask.');
  if (!quick) {
    const box = document.createElement('div');
    box.className = 'adv-examples';
    for (const [text, label] of EXAMPLES) {
      const b = document.createElement('button');
      b.className = 'adv-example';
      b.textContent = label;
      b.onclick = () => send(text);
      box.append(b);
    }
    $('adv-thread').append(box);
  }
}

async function send(text) {
  text = (text || '').trim();
  if (!text || busy) return;
  $('adv-text').value = '';
  grow();
  say('user', text);
  setBusy(true);
  const wait = say('bot wait', 'Thinking');
  try {
    const out = await post('chat', { session, text });
    session = out.session || session;
    wait.remove();
    say('bot', out.reply);
    if (out.search) showSearch(out.search);
  } catch (e) {
    wait.remove();
    fail(e, text);
  } finally {
    setBusy(false);
  }
}

function fail(e, text) {
  const message = e.message || 'Something went wrong.';
  if (e.error === 'limit') { say('bot', message); return; }
  say('bot err', message);
  if (e.error === 'busy' || e.error === 'refused') return; // the chat itself still works: let them try again
  llm = false; // no key, no connection or a service error: carry on with the form, which needs no assistant
  setMode(true, text);
}

function setBusy(on) {
  busy = on;
  $('adv-send').disabled = on;
  $('adv-text').disabled = on;
  if (!on && !quick) $('adv-text').focus();
}

function grow() { const t = $('adv-text'); t.style.height = 'auto'; t.style.height = `${Math.min(t.scrollHeight, 110)}px`; }

// ---------- the quick form (same search, no language model) ----------
function buildQuick() {
  const f = $('adv-quick');
  const seg = (name, items, on) => `<div class="seg small adv-seg" data-name="${name}">${items.map(([v, l]) => `<button type="button" data-v="${v}" class="${v === on ? 'on' : ''}">${l}</button>`).join('')}</div>`;
  f.innerHTML = `
    <label class="k">Rent or buy</label>${seg('mode', [['rent', 'Rent'], ['buy', 'Buy']], 'rent')}
    <label class="k">City</label>${seg('city', [['both', 'Both'], ['delhi', 'Delhi'], ['gurugram', 'Gurugram']], 'both')}
    <label class="k">Bedrooms</label><div class="chips adv-bhk">${[1, 2, 3, 4, 5].map((n) => `<button type="button" class="chip" data-b="${n}">${n === 5 ? '5+' : n}</button>`).join('')}</div>
    <label class="k" for="aq-budget">Budget <span class="val" id="aq-unit">per month</span></label><select id="aq-budget"></select>
    <label class="k" for="aq-work">Where you work <span class="val">optional</span></label>
    <input id="aq-work" type="text" placeholder="A sector, colony or society, e.g. Golf Course Road" autocomplete="off">
    <label class="k" for="aq-km">Longest distance to work <span class="val">straight line</span></label>
    <select id="aq-km"><option value="">No limit</option><option>3</option><option>5</option><option>8</option><option>12</option><option>20</option></select>
    <label class="k" for="aq-air">How much does air quality matter</label>
    <select id="aq-air"><option value="none">Not at all</option><option value="some" selected>Somewhat</option><option value="high">A lot</option></select>
    <label class="k">Must be close to</label>
    <div class="chips adv-near">${Object.entries(NEAR_LABEL).map(([k, l]) => `<button type="button" class="chip" data-n="${k}">${l}</button>`).join('')}</div>
    <p class="adv-formerr" id="aq-err" hidden></p>
    <button type="submit" class="primary" id="aq-go">Find areas</button>`;
  const fillBudget = () => {
    const rent = f.querySelector('[data-name=mode] .on').dataset.v === 'rent';
    $('aq-budget').replaceChildren(...(rent ? RENT_BUDGETS : BUY_BUDGETS).map(([v, l]) => new Option(l, v)));
    $('aq-unit').textContent = rent ? 'per month' : 'total';
  };
  fillBudget();
  f.querySelectorAll('.adv-seg').forEach((s) => s.querySelectorAll('button').forEach((b) => (b.onclick = () => {
    s.querySelectorAll('button').forEach((x) => x.classList.toggle('on', x === b));
    if (s.dataset.name === 'mode') fillBudget();
  })));
  f.querySelectorAll('.adv-bhk .chip, .adv-near .chip').forEach((b) => (b.onclick = () => b.classList.toggle('on')));
  f.onsubmit = async (ev) => {
    ev.preventDefault();
    const val = (n) => f.querySelector(`[data-name=${n}] .on`).dataset.v;
    const bhk = [...f.querySelectorAll('.adv-bhk .on')].map((b) => +b.dataset.b);
    const err = $('aq-err');
    err.hidden = true;
    if (!bhk.length) { err.textContent = 'Pick at least one bedroom count.'; err.hidden = false; return; }
    const brief = {
      mode: val('mode'), city: val('city'), bhk, budget_max: $('aq-budget').value ? +$('aq-budget').value : null,
      workplace: $('aq-work').value.trim() || null, max_commute_km: $('aq-km').value ? +$('aq-km').value : null,
      air_priority: $('aq-air').value, must_be_near: [...f.querySelectorAll('.adv-near .on')].map((b) => b.dataset.n), nice_to_have: [], kinds: ['apartment', 'builder floor'],
    };
    const label = `${brief.mode === 'rent' ? 'Rent' : 'Buy'} · ${brief.bhk.join('/')} BHK · ${$('aq-budget').selectedOptions[0].text} · ${{ both: 'Delhi + Gurugram', delhi: 'Delhi', gurugram: 'Gurugram' }[brief.city]}`;
    $('aq-go').disabled = true;
    try {
      const out = await post('search', { brief });
      say('user', label);
      say('bot', summary(out.search));
      showSearch(out.search);
      formOpen = false; // fold the form away so the results have the room
      render();
    } catch (e) {
      err.textContent = e.message || 'The search failed.';
      err.hidden = false;
    } finally {
      $('aq-go').disabled = false;
    }
  };
}

function summary(s) {
  const c = s.counts;
  if (!s.areas.length) return c.matched ? `${c.matched.toLocaleString()} buildings match, but too few in any one area to rank. They are highlighted on the map.` : `Nothing matches. ${whyEmpty(s)}`;
  return `${c.matched.toLocaleString()} buildings match (${c.gurugram.toLocaleString()} in Gurugram, ${c.delhi.toLocaleString()} in Delhi). The best areas are numbered on the map and listed below.`;
}

function whyEmpty(s) {
  const w = s.why_empty;
  if (!w) return '';
  const bits = Object.entries(w.matches_if_dropped || {}).filter(([, n]) => n > 0).map(([k, n]) => `without the ${({ budget_max: 'budget', max_commute_km: 'distance limit', must_be_near: 'nearby requirement', bhk: 'bedroom choice' })[k]}: ${n.toLocaleString()}`);
  return bits.length ? `Matches ${bits.join('; ')}.` : '';
}

// ---------- showing a search ----------
function showSearch(s) {
  ctx.apply(s.criteria);
  const panel = ctx.count();
  areas = s.areas;
  active = null;
  drawAreas(true);
  const holder = document.createElement('div');
  holder.className = 'adv-results';
  const note = document.createElement('p');
  note.className = 'adv-count';
  note.textContent = `${s.counts.matched.toLocaleString()} buildings match` + (panel !== s.counts.matched ? ` (the filter panel shows ${panel.toLocaleString()})` : ', same as the filter panel on the left')
    + (s.counts.without_locality ? ` · ${s.counts.without_locality.toLocaleString()} have no locality name and are not grouped` : '');
  holder.append(note);
  s.areas.forEach((a) => holder.append(areaCard(a, s)));
  if (s.warnings?.length) {
    const d = document.createElement('details');
    d.className = 'adv-warn';
    d.innerHTML = `<summary>Read before relying on this (${s.warnings.length})</summary>${s.warnings.map((w) => `<p>${esc(w)}</p>`).join('')}`;
    holder.append(d);
  }
  $('adv-thread').append(holder);
  scroll();
}

function areaCard(a, s) {
  const el = document.createElement('article');
  el.className = 'adv-area';
  el.dataset.rank = a.rank;
  const money = (v) => formatINR(v) + (s.criteria.mode === 'rent' ? '/mo' : '');
  const price = a.price ? `<span class="adv-price">${money(a.price.median)}</span>` : '';
  const school = a.school ? `<p class="adv-school">Schools in pincode ${esc(a.school.pincode)}: ${a.school.schools} (${a.school.private_pct}% private${a.school.pupil_teacher_ratio ? `, about ${esc(a.school.pupil_teacher_ratio)} pupils per teacher` : ''}). A profile from UDISE+ 2024-25, not a quality score.</p>` : '';
  el.innerHTML = `
    <header><span class="adv-rank">${a.rank}</span><div class="adv-title"><b>${esc(a.name)}</b><small>${esc(a.city)} · ${a.n} building${a.n === 1 ? '' : 's'} match</small></div>${price}</header>
    <p class="adv-fit">Fit ${a.score}/100 <small>among ${esc(a.city)} areas</small></p>
    <ul>${a.reasons.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>
    ${school}
    <div class="adv-bld">${a.buildings.map((b) => `<button type="button" class="adv-b" data-id="${esc(b.id)}">${esc(b.name)}${b.price ? ` <small>${b.estimated ? '~' : ''}${money(b.price)}</small>` : ''}</button>`).join('')}</div>`;
  el.onclick = (ev) => {
    const b = ev.target.closest('.adv-b');
    if (b) { ctx.open(b.dataset.id); return; }
    selectArea(a.rank, true);
  };
  return el;
}

function selectArea(rank, fly) {
  active = rank;
  document.querySelectorAll('.adv-area').forEach((e) => e.classList.toggle('on', +e.dataset.rank === rank));
  drawAreas(false);
  const a = areas.find((x) => x.rank === rank);
  const map = ctx.map();
  if (fly && a && map) map.flyTo({ center: [a.lng, a.lat], zoom: 13.6, duration: 1600, essential: true, offset: ctx.isMobile ? [0, -120] : [-180, 0] });
}

// ---------- map: a ring and a number for each recommended area ----------
function ring(lng, lat, metres, n = 64) {
  const dLat = metres / 111320, dLng = metres / (111320 * Math.cos((lat * Math.PI) / 180));
  const pts = Array.from({ length: n }, (_, i) => { const t = (2 * Math.PI * i) / n; return [lng + dLng * Math.cos(t), lat + dLat * Math.sin(t)]; });
  return [...pts, pts[0]];
}

function ensureLayers(map) {
  if (map.getSource('adv-areas')) return true;
  if (!map.getLayer('site-fill')) return false; // the map is still loading
  map.addSource('adv-areas', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'adv-fill', type: 'fill', source: 'adv-areas', paint: { 'fill-color': '#ff9f1c', 'fill-opacity': ['case', ['get', 'sel'], 0.2, 0.09] } }, 'site-fill');
  map.addLayer({ id: 'adv-line', type: 'line', source: 'adv-areas', paint: { 'line-color': '#ff9f1c', 'line-width': ['case', ['get', 'sel'], 3, 1.5], 'line-dasharray': [2, 1.5] } }, 'site-fill');
  return true;
}

function drawAreas(fit) {
  const map = ctx.map();
  pins.forEach((p) => p.remove());
  pins = [];
  if (!map || !ensureLayers(map)) return;
  map.getSource('adv-areas').setData({ type: 'FeatureCollection', features: areas.map((a) => ({
    type: 'Feature', properties: { rank: a.rank, sel: a.rank === active }, geometry: { type: 'Polygon', coordinates: [ring(a.lng, a.lat, a.radius_m)] } })) });
  for (const a of areas) {
    const el = document.createElement('button');
    el.className = `adv-pin${a.rank === active ? ' on' : ''}`;
    el.textContent = a.rank;
    el.title = `${a.name}, ${a.city}`;
    el.onclick = () => { selectArea(a.rank, false); document.querySelector(`.adv-area[data-rank="${a.rank}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); };
    pins.push(new maplibregl.Marker({ element: el }).setLngLat([a.lng, a.lat]).addTo(map));
  }
  if (fit && areas.length) {
    const b = new maplibregl.LngLatBounds();
    areas.forEach((a) => ring(a.lng, a.lat, a.radius_m, 8).forEach((p) => b.extend(p)));
    const padding = ctx.isMobile ? { top: 50, bottom: Math.round(innerHeight * 0.6), left: 24, right: 24 } : { top: 70, bottom: 70, left: 370, right: 450 };
    map.fitBounds(b, { padding, maxZoom: 12.5, duration: 1800, essential: true });
  }
}

function clearAreas() {
  areas = [];
  active = null;
  drawAreas(false);
  ctx.map()?.getSource?.('adv-areas')?.setData({ type: 'FeatureCollection', features: [] });
}

// ---------- panel ----------
function setMode(useQuick, keepText = '') {
  quick = useQuick;
  formOpen = true;
  if (quick && !$('adv-quick').childElementCount) buildQuick();
  if (keepText && quick) say('bot', 'You can run the same search from this form.');
  render();
  if (!$('adv-thread').childElementCount) greet();
}

// What shows below the thread: the chat box, or the form (which folds away once it has produced results).
function render() {
  $('adv-chat-form').hidden = quick;
  $('adv-quick').hidden = !(quick && formOpen);
  $('adv-switch').textContent = !quick ? 'Prefer a short form?' : !formOpen ? 'Edit my search' : llm ? 'Back to chat' : '';
  $('adv-banner').hidden = llm || !quick;
  if (!quick && !busy) $('adv-text').focus();
}

function open(on) {
  document.body.classList.toggle('advisor-open', on);
  $('advisor').hidden = !on;
  $('btn-ask').classList.toggle('live', on);
  store.set('ff-advisor-open', on);
  if (on && !quick) setTimeout(() => $('adv-text').focus(), 50);
}

export async function initAdvisor(c) {
  ctx = c;
  const button = $('btn-ask');
  if (!ctx.enabled || !button) { if (button) button.hidden = true; return; }
  button.hidden = false;
  session = newSession();
  button.onclick = () => open($('advisor').hidden);
  $('adv-close').onclick = () => open(false);
  $('adv-new').onclick = () => {
    post('reset', { session }).catch(() => {});
    session = newSession();
    clearAreas();
    ctx.reset();
    greet();
  };
  $('adv-switch').onclick = () => {
    if (!quick) setMode(true);
    else if (!formOpen) { formOpen = true; render(); }
    else if (llm) setMode(false);
  };
  $('adv-chat-form').onsubmit = (ev) => { ev.preventDefault(); send($('adv-text').value); };
  $('adv-text').oninput = grow;
  $('adv-text').onkeydown = (ev) => { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); send($('adv-text').value); } };
  try {
    llm = !!(await fetch(`${API}/status`).then((r) => r.json())).llm;
  } catch {
    llm = false;
  }
  setMode(!llm);
  if (new URLSearchParams(location.search).has('ask') || store.get('ff-advisor-open', false)) open(true);
}

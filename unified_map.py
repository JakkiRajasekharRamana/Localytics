"""One map for air observations and local connectivity; click anywhere to inspect."""
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import folium
from branca.element import MacroElement, Template


def build_map(records):
    groups = defaultdict(list)
    skipped = 0
    for r in records:
        try:
            lat, lon = float(r['latitude']), float(r['longitude'])
            if not (math.isfinite(lat) and math.isfinite(lon) and -90<=lat<=90 and -180<=lon<=180):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        groups[(str(r.get('station','Unknown')),lat,lon)].append(r)
    stations = [dict(name=k[0],lat=k[1],lon=k[2],readings=v) for k,v in groups.items()]
    transport = []
    path = Path(__file__).parent/'connectivity'/'transport_locations.csv'
    # Transport is optional: unavailable or damaged files must not hide air data.
    try:
        with path.open(encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('category') not in ('bus_stop', 'metro_station', 'airport_terminal'):
                    continue
                try:
                    lat, lon = float(r['latitude']), float(r['longitude'])
                    if not (math.isfinite(lat) and math.isfinite(lon)
                            and -90 <= lat <= 90 and -180 <= lon <= 180):
                        continue
                    transport.append(dict(name=r.get('name') or 'Unnamed', lat=lat, lon=lon,
                                          category=r['category'], method=r.get('coordinate_method', 'unknown')))
                except (KeyError, TypeError, ValueError):
                    continue
    except (OSError, UnicodeError, csv.Error):
        transport = []
    # Conservative consolidation of same-name mapped objects, within 100 metres.
    # Unnamed features stay separate; opposite-direction named stops may merge.
    def distance_km(lat1, lon1, lat2, lon2):
        a, b = math.radians(lat1), math.radians(lat2)
        h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
        return 6371.0088 * 2 * math.asin(math.sqrt(min(1, h)))
    unique, names = [], defaultdict(list)
    for p in transport:
        key=(p['category'],p['name'].strip().casefold())
        if key[1] != 'unnamed' and any(distance_km(p['lat'],p['lon'],q['lat'],q['lon'])<.1 for q in names[key]):
            continue
        unique.append(p)
        names[key].append(p)
    center = [22.5937,78.9629]
    if stations:
        center=[sum(s['lat'] for s in stations)/len(stations),sum(s['lon'] for s in stations)/len(stations)]
    m=folium.Map(location=center,zoom_start=11 if stations else 5,tiles='OpenStreetMap')
    if len(stations)>1:
        m.fit_bounds([[s['lat'],s['lon']] for s in stations],max_zoom=12)
    control=MacroElement()
    control._name='CombinedExplorer'
    control.stations=stations
    control.transport=unique
    metadata_path = path.with_name('metadata.json')
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        bounds = [item['bounds'] for item in metadata['source_header_bounds']]
        bounds = [b for b in bounds if isinstance(b, list) and len(b) == 4
                  and all(isinstance(v, (int, float)) and math.isfinite(v) for v in b)
                  and -180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90]
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        bounds = []
    control.bounds = bounds if unique else []
    control._template=Template(r'''
{% macro script(this, kwargs) %}
(function(){
const map={{this._parent.get_name()}}, stations={{this.stations|tojson}}, facilities={{this.transport|tojson}};
const bounds={{this.bounds|tojson}};
const names={bus_stop:'Bus stops',metro_station:'Metro stations',airport_terminal:'Airport terminals'};
const colors={bus_stop:'#2878b5',metro_station:'#8b46a5',airport_terminal:'#db7618'};
let radius=2, lastSelection=null;
const esc=x=>String(x??'NA').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const distance=(a,b)=>map.distance([a.lat,a.lon],[b.lat,b.lon])/1000;
function connections(point){
 const found=facilities.map(p=>({...p,d:distance(point,p)})).filter(p=>p.d<=radius).sort((a,b)=>a.d-b.d);
 const counts=Object.fromEntries(Object.keys(names).map(k=>[k,found.filter(p=>p.category===k).length]));
 const types=Object.values(counts).filter(n=>n>0).length;
 // 50% variety, 50% count; a count of 20 reaches the count component's cap.
 const score=found.length ? Math.round(50*types/3+50*Math.min(found.length/20,1)):0;
 const label=!found.length?'No mapped matches':score>=70?'High':score>=40?'Medium':'Low';
 const color=!found.length?'#808080':score>=70?'#16834a':score>=40?'#e9a522':'#cc4949';
 // A score is withheld unless the entire search radius fits within an extract.
 const dy=radius/110, dx=radius/(110*Math.max(.001,Math.cos(point.lat*Math.PI/180)));
 const covered=bounds.some(b=>point.lon-dx>=b[0] && point.lat-dy>=b[1] && point.lon+dx<=b[2] && point.lat+dy<=b[3]);
 const coverageNote=covered?'Within a downloaded extract; OSM completeness is not guaranteed.':'Search radius is outside or crosses the downloaded extract boundary. Counts below include available records only.';
 return {found,counts,types,score:covered?score:null,label:covered?label:'Transport coverage unavailable or partial',color:covered?color:'#808080',coverageNote};
}
function air(station){
 const candidates=station.readings.filter(r=>r.pollutant_id==='PM2.5');
 const stamp=s=>{const a=String(s||'').match(/^(\d{2})-(\d{2})-(\d{4}) (\d{2}):(\d{2}):(\d{2})$/);return a?`${a[3]}${a[2]}${a[1]}${a[4]}${a[5]}${a[6]}`:''};
 candidates.sort((a,b)=>stamp(b.last_update).localeCompare(stamp(a.last_update)));
 const raw=candidates[0]?.avg_value;
 const v=raw===undefined||raw===null||String(raw).trim()===''?NaN:Number(raw);
 if(!Number.isFinite(v)||v<0)return {label:'No PM2.5 data',color:'#808080',value:'NA'};
 const bands=[[30,'Good','#008000'],[60,'Satisfactory','#8fbc3f'],[90,'Moderate','#ffff00'],[120,'Poor','#ff9900'],[250,'Very poor','#ff0000'],[Infinity,'Severe','#800000']];
 const band=bands.find(b=>v<=b[0]);return {value:v,label:band[1],color:band[2]};
}
const connectivity=L.featureGroup().addTo(map), airLayer=L.featureGroup().addTo(map), selected=L.featureGroup().addTo(map);
const transportLayers=Object.fromEntries(Object.keys(names).map(k=>[k,L.featureGroup()]));
for(const p of facilities){L.circleMarker([p.lat,p.lon],{radius:4,color:colors[p.category],weight:1,fillOpacity:.8}).bindTooltip(esc(names[p.category]+': '+p.name)).addTo(transportLayers[p.category]);}
function repaint(){connectivity.clearLayers();for(const s of stations){const c=connections(s);L.circleMarker([s.lat,s.lon],{radius:16,color:c.color,weight:5,fill:false}).bindTooltip('Connectivity: '+c.label+(c.score===null?'':' ('+c.score+'/100)')).on('click',()=>inspect(s,s)).addTo(connectivity);}}
function inspect(point,exact){
 lastSelection={point,exact};
 selected.clearLayers();
 const c=connections(point);
 L.circle([point.lat,point.lon],{radius:radius*1000,color:c.color,weight:2,fillOpacity:.04}).addTo(selected);
 L.circleMarker([point.lat,point.lon],{radius:5,color:'#172d40',fillOpacity:1}).addTo(selected);
 const nearest=exact||stations.slice().sort((a,b)=>distance(point,a)-distance(point,b))[0];
 let connectivityHtml=`<div style="font:14px Arial;line-height:1.6;overflow-wrap:anywhere"><b>${esc(exact?.name||'Selected location')}</b><br>${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}<hr><b>Connectivity: ${c.label}${c.score===null?'':' · '+c.score+'/100'}</b><br><small>${c.coverageNote}</small><br>${c.found.length} mapped facilities · ${c.types}/3 types within ${radius} km<ul>`;
 for(const k of Object.keys(names)) connectivityHtml+=`<li>${names[k]}: ${c.counts[k]}</li>`;
 connectivityHtml+='</ul><details><summary>Nearest facilities (up to 5 per type)</summary>';
 for(const k of Object.keys(names)){connectivityHtml+=`<b>${names[k]}</b><ul>`;const items=c.found.filter(p=>p.category===k).slice(0,5);connectivityHtml+=items.length?items.map(p=>`<li>${esc(p.name)} · ${p.d.toFixed(2)} km${p.method!=='mapped_point'?' (approximate centre)':''}</li>`).join(''):'<li>No mapped matches</li>';connectivityHtml+='</ul>';}
 connectivityHtml+='</details>';
 let html=`<div style="font:14px Arial;line-height:1.6;overflow-wrap:anywhere"><b>Air-quality observations</b><br>`;
 if(nearest){const a=air(nearest),d=distance(point,nearest);html+=`${esc(nearest.name)} · ${d.toFixed(2)} km away<br>Indicative PM2.5: <b>${esc(a.value)} · ${a.label}</b><br><small>Nearest loaded monitor; not a measurement at the clicked location.</small><div style="max-height:220px;overflow:auto"><table style="width:100%;border-collapse:collapse" border="1" cellpadding="5"><tr><th>Pollutant</th><th>Min</th><th>Max</th><th>Avg</th><th>Updated</th></tr>`;
 for(const r of nearest.readings)html+=`<tr>${['pollutant_id','min_value','max_value','avg_value','last_update'].map(k=>'<td>'+esc(r[k])+'</td>').join('')}</tr>`;
 html+='</table></div>';}else html+='No loaded air-quality readings. Use “Load station data” to fetch them.';
 html+='<hr>'+connectivityHtml+'</div>';
 html+='<hr><small>Project connectivity score, not an official rating. Straight-line distances. OSM coverage and duplicates affect counts; passenger airport service is unverified. PM2.5 colours assume 24-hour µg/m³ and are not official overall AQI.</small></div>';
 window.parent.postMessage({type:'localytics:selection',html:html}, window.location.origin === 'null' ? '*' : window.location.origin);
}
for(const s of stations){const a=air(s);L.circleMarker([s.lat,s.lon],{radius:8,color:'#333',weight:1,fillColor:a.color,fillOpacity:1}).bindTooltip(esc(s.name)+' · PM2.5 '+esc(a.value)+' · '+a.label).on('click',()=>inspect(s,s)).addTo(airLayer);}
map.on('click',e=>inspect({lat:e.latlng.lat,lon:e.latlng.lng}));
L.control.layers(null,{'Air quality (inner dots)':airLayer,'Connectivity (outer rings)':connectivity,'Bus stops':transportLayers.bus_stop,'Metro stations':transportLayers.metro_station,'Airport terminals':transportLayers.airport_terminal}).addTo(map);
const legend=L.control({position:'bottomleft'});
legend.onAdd=function(){const div=L.DomUtil.create('div');div.style.cssText='background:white;padding:12px;border-radius:7px;max-width:285px;font:12px Arial;box-shadow:0 1px 6px #999';div.innerHTML='<details><summary style="cursor:pointer;font-weight:bold">Map legend &amp; search radius</summary><b>Click anywhere to inspect an area</b><br><br>Connectivity radius: <select aria-label="Connectivity radius"><option value="1">1 km</option><option value="2" selected>2 km</option><option value="5">5 km</option><option value="10">10 km</option><option value="25">25 km</option></select><br><br><b>Outer ring: connectivity</b><br><span style="color:#16834a">● High ≥70</span> · <span style="color:#e9a522">● Medium 40–69</span><br><span style="color:#cc4949">● Low &lt;40</span> · <span style="color:#808080">● No matches / coverage unavailable</span><br><small>Score = 50 × types/3 + 50 × min(count/20, 1). Radius changes scores.</small><br><br><b>Inner dot: indicative PM2.5</b><br><span style="color:#008000">● Good ≤30</span> · <span style="color:#8fbc3f">● Satisfactory ≤60</span><br><span style="color:#b59d00">● Moderate ≤90</span> · <span style="color:#ff9900">● Poor ≤120</span><br><span style="color:#ff0000">● Very poor ≤250</span> · <span style="color:#800000">● Severe &gt;250</span><br>Grey = missing. Not overall AQI.</details>';L.DomEvent.disableClickPropagation(div);L.DomEvent.disableScrollPropagation(div);div.querySelector('select').onchange=e=>{radius=Number(e.target.value);repaint();if(lastSelection)inspect(lastSelection.point,lastSelection.exact);};return div;};legend.addTo(map);
})();
{% endmacro %}
''')
    m.add_child(control)
    return m._repr_html_(),len(stations),skipped

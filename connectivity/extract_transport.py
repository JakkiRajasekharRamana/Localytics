"""Extract mapped transport features from an OSM PBF; no network calls.
Install: pip install osmium
Run: python extract_transport.py /path/to/delhi.pbf
"""
import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import osmium


def classify(t):
    if t.get('aeroway') == 'terminal':
        return 'airport_terminal'
    if t.get('aeroway') == 'aerodrome':
        return 'airport'
    if t.get('railway') == 'subway_entrance':
        return 'metro_entrance'
    if (t.get('railway') in ('station', 'halt') or
            t.get('public_transport') == 'station') and (
            t.get('station') == 'subway' or t.get('subway') == 'yes'):
        return 'metro_station'
    if (t.get('highway') == 'bus_stop' or t.get('amenity') == 'bus_station' or
            (t.get('public_transport') in ('platform', 'stop_position', 'station')
             and t.get('bus') == 'yes')):
        return 'bus_stop'
    if t.get('railway') in ('station', 'halt'):
        return 'railway_station'
    return None


class Transport(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.invalid = 0

    def add(self, obj, kind, lat, lon, method):
        t = dict(obj.tags)
        self.rows.append(dict(
            osm_type=kind, osm_id=obj.id, osm_version=obj.version, osm_timestamp=str(obj.timestamp), category=classify(t),
            name=t.get('name:en') or t.get('name') or t.get('ref') or 'Unnamed',
            latitude=lat, longitude=lon, coordinate_method=method,
            operator=t.get('operator', ''), network=t.get('network', ''),
            tags_json=json.dumps(t, ensure_ascii=False)))

    def node(self, node):
        if classify(dict(node.tags)):
            if node.location.valid():
                self.add(node, 'node', node.location.lat, node.location.lon, 'mapped_point')
            else:
                self.invalid += 1

    def way(self, way):
        if not classify(dict(way.tags)):
            return
        try:
            coords = [(n.lat, n.lon) for n in way.nodes]
        except osmium.InvalidLocationError:
            self.invalid += 1
            return
        if not coords:
            self.invalid += 1
            return
        # Approximate point for mapped platforms/buildings/airport grounds.
        lat = (min(p[0] for p in coords) + max(p[0] for p in coords)) / 2
        lon = (min(p[1] for p in coords) + max(p[1] for p in coords)) / 2
        self.add(way, 'way', lat, lon, 'approximate_bbox_center')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pbf', type=Path, nargs='+')
    parser.add_argument('--output', type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    merged = {}
    source_counts = {}
    duplicates = 0
    invalid = 0
    for source in args.pbf:
        print('Reading ' + source.name, flush=True)
        part = Transport()
        processor = osmium.FileProcessor(str(source), entities=osmium.osm.NODE | osmium.osm.WAY).with_locations('flex_mem')
        processor.with_filter(osmium.filter.KeyFilter('highway', 'amenity', 'railway', 'public_transport', 'aeroway'))
        for obj in processor:
            if obj.is_node():
                part.node(obj)
            elif obj.is_way():
                part.way(obj)
        source_counts[source.name] = len(part.rows)
        invalid += part.invalid
        for row in part.rows:
            row['source_files'] = source.name
            key = (row['osm_type'], row['osm_id'])
            old = merged.get(key)
            if old is not None:
                duplicates += 1
                sources = sorted(set(old['source_files'].split(';') + [source.name]))
                if (row['osm_version'], row['osm_timestamp']) >= (old['osm_version'], old['osm_timestamp']):
                    row['source_files'] = ';'.join(sources)
                    merged[key] = row
                else:
                    old['source_files'] = ';'.join(sources)
            else:
                merged[key] = row
        print(f'{len(part.rows)} features; {len(merged)} unique objects so far', flush=True)
    handler = Transport()
    handler.rows = list(merged.values())
    handler.invalid = invalid
    args.output.mkdir(parents=True, exist_ok=True)
    fields = ['osm_type','osm_id','category','name','latitude','longitude',
              'coordinate_method','operator','network','tags_json','osm_version','osm_timestamp','source_files']
    with (args.output / 'transport_locations.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(handler.rows)
    features = []
    for row in handler.rows:
        properties = {k: v for k,v in row.items() if k not in ('latitude','longitude','tags_json')}
        properties['osm_tags'] = json.loads(row['tags_json'])
        features.append({'type':'Feature', 'geometry':{'type':'Point',
                         'coordinates':[row['longitude'],row['latitude']]},
                         'properties':properties})
    (args.output / 'transport_locations.geojson').write_text(json.dumps(
        {'type':'FeatureCollection','features':features},ensure_ascii=False), encoding='utf-8')
    metadata = dict(source_files=[p.name for p in args.pbf], source_feature_counts=source_counts, overlap_duplicates_removed=duplicates, deduplication='OSM type + ID; highest object version/timestamp wins; later input wins ties', extracted_at_utc=datetime.now(timezone.utc).isoformat(),
        counts=dict(Counter(r['category'] for r in handler.rows)), invalid_features=handler.invalid,
        limitations=['OSM nodes and ways only; relation-only facilities are not extracted.',
        'Multiple OSM objects may represent the same physical facility; counts are mapped features, not unique stations.',
        'Way coordinates are bounding-box centres, not entrances or guaranteed interior points.',
        'Classification depends on OSM tags; metro facilities may be missing or classified as railway stations.',
        'Airports/terminals may include private or military facilities; passenger service is not verified.',
        'Coverage is limited to the supplied extract, not necessarily all Delhi NCT/NCR.'],
        attribution='© OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright')
    (args.output / 'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata,indent=2))


if __name__ == '__main__':
    main()

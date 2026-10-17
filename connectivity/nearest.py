"""Local nearest-feature lookup. No external dependencies or API key."""
import csv
import math
from pathlib import Path


def distance_km(lat1, lon1, lat2, lon2):
    a,b = math.radians(lat1),math.radians(lat2)
    dlat,dlon = b-a,math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1,max(0,h))))


def nearest(latitude, longitude, category='bus_stop', limit=5, radius_km=None,
            csv_path=None):
    """Return nearest mapped features, with straight-line distances.
    Category: bus_stop, metro_station, metro_entrance, railway_station,
    airport_terminal, airport. Duplicates may represent one physical facility.
    """
    latitude,longitude = float(latitude),float(longitude)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError('Invalid latitude/longitude')
    if limit < 1:
        raise ValueError('limit must be positive')
    if radius_km is not None and radius_km < 0:
        raise ValueError('radius_km must be nonnegative')
    path = Path(csv_path) if csv_path else Path(__file__).with_name('transport_locations.csv')
    matches = []
    with path.open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['category'] != category:
                continue
            row['latitude'],row['longitude'] = float(row['latitude']),float(row['longitude'])
            distance = distance_km(latitude,longitude,row['latitude'],row['longitude'])
            if radius_km is None or distance <= radius_km:
                row['distance_km'] = distance
                matches.append(row)
    return sorted(matches,key=lambda x:x['distance_km'])[:limit]


if __name__ == '__main__':
    for category in ('bus_stop','metro_station','airport_terminal'):
        print('\n'+category)
        for place in nearest(28.6139,77.2090,category):
            print(f"{place['name']}: {place['distance_km']:.2f} km")

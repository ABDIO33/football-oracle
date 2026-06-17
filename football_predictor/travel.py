"""
travel.py — Travel distance calculation using STADIUM_DB
"""

import os, json, math

_DB_PATH = os.path.join(os.path.dirname(__file__), 'stadium_db.json')
_STADIUM_CACHE = None

# National team home locations (fallback for WC teams not in STADIUM_DB)
NATIONAL_TEAMS = {
    'Algeria': (36.7538, 3.0588), 'Argentina': (-34.6037, -58.3816),
    'Australia': (-35.2809, 149.1300), 'Austria': (48.2082, 16.3738),
    'Belgium': (50.8503, 4.3517), 'Bosnia & Herzegovina': (43.8563, 18.4131),
    'Brazil': (-15.7939, -47.8828), 'Cabo Verde': (14.9330, -23.5133),
    'Canada': (45.4215, -75.6972), 'Colombia': (4.7110, -74.0721),
    'Croatia': (45.8150, 15.9819), 'Curaçao': (12.1696, -68.9900),
    'Czechia': (50.0755, 14.4378), 'Côte d\'Ivoire': (6.8276, -5.2893),
    'DR Congo': (-4.4419, 15.2663), 'Ecuador': (-0.1807, -78.4678),
    'Egypt': (30.0444, 31.2357), 'England': (51.5074, -0.1278),
    'France': (48.8566, 2.3522), 'Germany': (52.5200, 13.4050),
    'Ghana': (5.6037, -0.1870), 'Haiti': (18.5944, -72.3074),
    'Iran': (35.6892, 51.3890), 'Iraq': (33.3152, 44.3661),
    'Japan': (35.6762, 139.6503), 'Jordan': (31.9454, 35.9284),
    'Mexico': (19.4326, -99.1332), 'Morocco': (33.5731, -7.5898),
    'Netherlands': (52.3676, 4.9041), 'New Zealand': (-41.2865, 174.7762),
    'Norway': (59.9139, 10.7522), 'Panama': (8.9824, -79.5199),
    'Paraguay': (-25.2637, -57.5759), 'Portugal': (38.7223, -9.1393),
    'Qatar': (25.2854, 51.5310),     'Saudi Arabia': (24.7136, 46.6753),
    'Serbia': (44.7866, 20.4489),
    'Scotland': (55.9533, -3.1883), 'Senegal': (14.7167, -17.4677),
    'South Africa': (-25.7461, 28.1881), 'South Korea': (37.5665, 126.9780),
    'Spain': (40.4168, -3.7038), 'Sweden': (59.3293, 18.0686),
    'Switzerland': (46.9480, 7.4474), 'Tunisia': (36.8065, 10.1815),
    'Türkiye': (39.9334, 32.8597), 'USA': (38.9072, -77.0369),
    'Uruguay': (-34.9011, -56.1645), 'Uzbekistan': (41.2995, 69.2401),
}

def _load_stadiums():
    global _STADIUM_CACHE
    if _STADIUM_CACHE is not None:
        return
    try:
        with open(_DB_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except:
        _STADIUM_CACHE = {}
        return
    _STADIUM_CACHE = {}
    for team, info in data.items():
        _STADIUM_CACHE[team.lower()] = {
            'lat': info.get('lat', 0),
            'lng': info.get('lng', 0),
            'city': info.get('city', ''),
            'venue_name': info.get('venue_name', ''),
            'team_name': team,
        }

def get_team_location(team_name):
    _load_stadiums()
    key = team_name.strip().lower()
    if _STADIUM_CACHE and key in _STADIUM_CACHE:
        return _STADIUM_CACHE[key]
    if _STADIUM_CACHE:
        for cached_key, info in _STADIUM_CACHE.items():
            if key in cached_key or cached_key in key:
                return info
    # Fallback: national team
    for nt_key, (lat, lng) in NATIONAL_TEAMS.items():
        if nt_key.lower() == key or key in nt_key.lower() or nt_key.lower() in key:
            return {'lat': lat, 'lng': lng, 'city': nt_key, 'venue_name': '', 'team_name': nt_key}
    return None

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def get_travel_distance(team_name, venue_lat, venue_lon):
    loc = get_team_location(team_name)
    if not loc or not loc['lat'] or not loc['lng']:
        return None
    return haversine(loc['lat'], loc['lng'], venue_lat, venue_lon)

def get_venue_coords(venue_name):
    _load_stadiums()
    if not _STADIUM_CACHE or not venue_name:
        return None
    vn = venue_name.strip().lower()
    for info in _STADIUM_CACHE.values():
        cached_vn = info.get('venue_name', '').lower()
        if vn == cached_vn or vn in cached_vn or cached_vn in vn:
            return (info['lat'], info['lng'])
    return None

if __name__ == '__main__':
    d = get_travel_distance('Manchester City', 53.483, -2.200)
    print(f'Man City to Etihad: {d:.0f} km (should be ~0)')
    d2 = get_travel_distance('Real Madrid', 53.483, -2.200)
    print(f'Real Madrid to Manchester: {d2:.0f} km')
    loc = get_team_location('Liverpool')
    print(f'Liverpool location: {loc}')

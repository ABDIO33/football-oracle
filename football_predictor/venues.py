import os, json

WC2026_VENUES = {
    'Estadio Azteca':       {'city': 'Mexico City', 'country': 'Mexico', 'altitude_m': 2240, 'capacity': 87523, 'avg_temp_c': 22, 'is_roof': False, 'surface': 'grass'},
    'Estadio Akron':        {'city': 'Guadalajara', 'country': 'Mexico', 'altitude_m': 1562, 'capacity': 49325, 'avg_temp_c': 25, 'is_roof': False, 'surface': 'grass'},
    'Estadio BBVA':         {'city': 'Monterrey', 'country': 'Mexico', 'altitude_m': 538, 'capacity': 53500, 'avg_temp_c': 28, 'is_roof': False, 'surface': 'grass'},
    'MetLife Stadium':      {'city': 'New York', 'country': 'USA', 'altitude_m': 8, 'capacity': 82500, 'avg_temp_c': 27, 'is_roof': False, 'surface': 'artificial'},
    "Levi's Stadium":       {'city': 'San Francisco', 'country': 'USA', 'altitude_m': 16, 'capacity': 68500, 'avg_temp_c': 22, 'is_roof': False, 'surface': 'grass'},
    'AT&T Stadium':         {'city': 'Dallas', 'country': 'USA', 'altitude_m': 186, 'capacity': 105000, 'avg_temp_c': 32, 'is_roof': True, 'surface': 'artificial'},
    'SoFi Stadium':         {'city': 'Los Angeles', 'country': 'USA', 'altitude_m': 34, 'capacity': 70240, 'avg_temp_c': 28, 'is_roof': True, 'surface': 'artificial'},
    'Arrowhead Stadium':    {'city': 'Kansas City', 'country': 'USA', 'altitude_m': 327, 'capacity': 76416, 'avg_temp_c': 29, 'is_roof': False, 'surface': 'grass'},
    'NRG Stadium':           {'city': 'Houston', 'country': 'USA', 'altitude_m': 15, 'capacity': 72220, 'avg_temp_c': 33, 'is_roof': True, 'surface': 'artificial'},
    'Hard Rock Stadium':    {'city': 'Miami', 'country': 'USA', 'altitude_m': 2, 'capacity': 65326, 'avg_temp_c': 31, 'is_roof': False, 'surface': 'grass'},
    'Lincoln Financial Field': {'city': 'Philadelphia', 'country': 'USA', 'altitude_m': 9, 'capacity': 69596, 'avg_temp_c': 28, 'is_roof': False, 'surface': 'grass'},
    'Gillette Stadium':     {'city': 'Boston', 'country': 'USA', 'altitude_m': 32, 'capacity': 66829, 'avg_temp_c': 26, 'is_roof': False, 'surface': 'artificial'},
    'Lumen Field':          {'city': 'Seattle', 'country': 'USA', 'altitude_m': 21, 'capacity': 72000, 'avg_temp_c': 22, 'is_roof': False, 'surface': 'artificial'},
    'BC Place':             {'city': 'Vancouver', 'country': 'Canada', 'altitude_m': 4, 'capacity': 54500, 'avg_temp_c': 21, 'is_roof': True, 'surface': 'artificial'},
    'BMO Field':            {'city': 'Toronto', 'country': 'Canada', 'altitude_m': 76, 'capacity': 30991, 'avg_temp_c': 24, 'is_roof': False, 'surface': 'grass'},
    'Rose Bowl':            {'city': 'Los Angeles', 'country': 'USA', 'altitude_m': 270, 'capacity': 92542, 'avg_temp_c': 27, 'is_roof': False, 'surface': 'grass'},
}

_VENUE_ALIASES = {}
for name, info in WC2026_VENUES.items():
    _VENUE_ALIASES[name.lower()] = name
    _VENUE_ALIASES[info['city'].lower()] = name
    _VENUE_ALIASES[f"{info['city'].lower()}_{info['country'].lower()}"] = name

def _resolve_venue(venue_name):
    if not venue_name:
        return None
    vn = venue_name.lower().strip()
    if vn in _VENUE_ALIASES:
        return _VENUE_ALIASES[vn]
    for alias, full_name in _VENUE_ALIASES.items():
        if alias in vn or vn in alias:
            return full_name
    return None

def venue_factor(venue_name=None, home_team=None, away_team=None, fixture_id=None):
    result = {
        'goals_multiplier': 1.0,
        'home_advantage_multiplier': 1.12,
        'is_high_altitude': False,
        'is_high_temp': False,
        'is_dome': False,
        'venue_name': venue_name or 'unknown',
        'applied': False,
    }
    vname = venue_name
    if not vname:
        return result
    resolved = _resolve_venue(vname)
    if not resolved:
        return result
    venue = WC2026_VENUES[resolved]
    result['venue_name'] = resolved
    # High altitude effect (>1500m): thinner air → ball travels faster, more goals
    if venue['altitude_m'] > 1500:
        result['goals_multiplier'] *= 1.06
        result['is_high_altitude'] = True
    elif venue['altitude_m'] > 500:
        result['goals_multiplier'] *= 1.02
    # High temp effect: fatigue for both teams, slightly fewer goals
    if venue['avg_temp_c'] > 30:
        result['goals_multiplier'] *= 0.97
        result['is_high_temp'] = True
    elif venue['avg_temp_c'] > 28:
        result['goals_multiplier'] *= 0.985
    # Dome: no weather effects on goals
    if venue['is_roof']:
        result['is_dome'] = True
    # Home advantage: neutral venue unless host nation playing
    result['home_advantage_multiplier'] = 1.0
    if home_team and _is_host_nation(home_team, resolved):
        result['home_advantage_multiplier'] = 1.05
    if away_team and _is_host_nation(away_team, resolved):
        result['home_advantage_multiplier'] = 1.0  # away team gets no boost
    result['applied'] = True
    return result

def _is_host_nation(team_name, venue_name):
    team_lower = team_name.lower()
    venue_info = WC2026_VENUES.get(venue_name)
    if not venue_info:
        return False
    country = venue_info['country']
    if country == 'USA' and ('united states' in team_lower or 'usa' in team_lower or 'america' in team_lower):
        return True
    if country == 'Mexico' and ('mexico' in team_lower):
        return True
    if country == 'Canada' and ('canada' in team_lower):
        return True
    return False

def get_venue_for_fixture(fixture_id):
    return ''

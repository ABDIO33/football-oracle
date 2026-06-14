import re
import requests
import os
import time
from urllib.parse import urlparse, parse_qs, unquote

API_SPORT_KEY = os.environ.get('API_SPORT_KEY', '')
API_FOOTBALL_BASE = 'https://v3.football.api-sports.io'
headers_api_football = lambda: {'x-apisports-key': os.environ.get('API_SPORT_KEY', '')}

_team_search_cache = {}
_cache = {}

SOFASCORE_PATTERN = re.compile(r'sofascore\.com.*?/(?:team|match)/football/([^/#?]+?)(?:/([^/#?]+?))?(?:/|$|#|\?)', re.I)
FLASHSCORE_PATTERN = re.compile(r'flashscore\.com.*?/match/([^/#?]+?)-vs-([^/#?]+?)(?:/|$|#|\?)', re.I)
LIVESCORE_PATTERN = re.compile(r'livescore\.com.*?/match/([^/#?]+?)-vs-([^/#?]+?)(?:/|$|#|\?)', re.I)
FOTMOB_PATTERN = re.compile(r'fotmob\.com.*?/match/([^/#?]+?)-vs-([^/#?]+?)(?:/|$|#|\?)', re.I)
WHOSCORED_PATTERN = re.compile(r'whoscored\.com.*?/matches/([^/#?]+?)-vs-([^/#?]+?)(?:/|$|#|\?)', re.I)
GENERIC_VS_PATTERN = re.compile(r'([a-z0-9\-]+)-vs-([a-z0-9\-]+)', re.I)

_TEAM_NAMES = {
    'manchester city', 'manchester united', 'liverpool', 'arsenal', 'chelsea',
    'tottenham', 'newcastle', 'aston villa', 'barcelona', 'real madrid',
    'atletico madrid', 'bayern munich', 'borussia dortmund', 'rb leipzig',
    'inter milan', 'ac milan', 'juventus', 'napoli', 'roma', 'lazio',
    'paris saint germain', 'marseille', 'lyon', 'monaco', 'lille',
    'benfica', 'porto', 'sporting', 'ajax', 'feyenoord', 'psv',
    'celtic', 'rangers', 'galatasaray', 'fenerbahce', 'besiktas',
    'shakhtar', 'dynamo kyiv', 'sporting cp', 'al hilal', 'al nassr',
    'usa', 'england', 'france', 'germany', 'spain', 'italy',
    'portugal', 'netherlands', 'belgium', 'brazil', 'argentina',
    'uruguay', 'colombia', 'japan', 'south korea', 'australia',
    'saudi arabia', 'qatar', 'united arab emirates', 'egypt',
    'morocco', 'senegal', 'nigeria', 'cameroon', 'ghana',
    'ivory coast', 'tunisia', 'algeria', 'mexico', 'canada',
    'costa rica', 'panama', 'chile', 'peru', 'ecuador',
    'paraguay', 'bolivia', 'venezuela', 'honduras', 'jamaica',
    'togo', 'burkina faso', 'mali', 'zambia', 'south africa',
    'democratic republic of the congo', 'republic of the congo',
    'angola', 'mozambique', 'uganda', 'kenya', 'zimbabwe',
    'cape verde', 'mauritania', 'niger', 'guinea', 'guinea bissau',
    'equatorial guinea', 'sierra leone', 'liberia', 'sudan',
    'ethiopia', 'rwanda', 'burundi', 'madagascar', 'comoros',
    'seychelles', 'djibouti', 'lesotho', 'botswana', 'namibia',
    'eswatini', 'gambia', 'gabon', 'chad', 'central african republic',
    'sao tome and principe', 'eritrea', 'south sudan', 'croatia',
    'denmark', 'sweden', 'norway', 'switzerland', 'austria',
    'poland', 'czech republic', 'slovakia', 'hungary', 'romania',
    'bulgaria', 'serbia', 'croatia', 'slovenia', 'bosnia',
    'montenegro', 'albania', 'north macedonia', 'greece', 'turkey',
    'ukraine', 'russia', 'finland', 'iceland', 'wales',
    'scotland', 'northern ireland', 'republic of ireland',
    'israel', 'iran', 'iraq', 'jordan', 'lebanon', 'syria',
    'oman', 'yemen', 'bahrain', 'kuwait', 'palestine',
    'uzbekistan', 'kazakhstan', 'kyrgyzstan', 'tajikistan',
    'turkmenistan', 'china', 'india', 'indonesia', 'thailand',
    'vietnam', 'malaysia', 'philippines', 'singapore', 'myanmar',
    'cambodia', 'laos', 'brunei', 'timor leste', 'maldives',
    'bhutan', 'nepal', 'bangladesh', 'sri lanka', 'mongolia',
    'taiwan', 'hong kong', 'macau', 'new zealand', 'fiji',
    'papua new guinea', 'solomon islands', 'vanuatu', 'samoa',
    'tonga', 'cook islands', 'new caledonia', 'tahiti',
}


def _cached(fn, key, ttl_minutes=1440):
    now = time.time()
    if key in _cache and (now - _cache[key].get('time', 0)) < ttl_minutes * 60:
        return _cache[key]['value']
    result = fn()
    _cache[key] = {'value': result, 'time': now}
    return result


def _normalize(name):
    return name.lower().strip().replace('-', ' ').replace('_', ' ')


def _clean_team_name(name):
    n = name.strip()
    n = re.sub(r'\b(?:FC|AFC|SC|CF|Real|Clube)\b', '', n, flags=re.I)
    n = re.sub(r'[^a-zA-Z0-9\s\'-]', '', n)
    return re.sub(r'\s+', ' ', n).strip().title()


def _search_team_api(name):
    n = _normalize(name)
    if n in _team_search_cache:
        return _team_search_cache[n]
    api_key = os.environ.get('API_SPORT_KEY', '')
    if not api_key:
        _team_search_cache[n] = None
        return None
    try:
        url = f"{API_FOOTBALL_BASE}/teams?search={requests.utils.quote(name)}"
        headers = headers_api_football()
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('response') and len(data['response']) > 0:
                team = data['response'][0]['team']
                result = {'name': team['name'], 'id': team['id'], 'logo': team.get('logo', '')}
                _team_search_cache[n] = result
                return result
    except:
        pass
    _team_search_cache[n] = None
    return None


def _validate_team(name1, name2):
    t1 = _cached(lambda: _search_team_api(name1), f"validate_{_normalize(name1)}", 1440)
    t2 = _cached(lambda: _search_team_api(name2), f"validate_{_normalize(name2)}", 1440)
    return (
        t1 is not None,
        t2 is not None,
        t1['name'] if t1 else name1,
        t2['name'] if t2 else name2
    )


def _fuzzy_match(name, candidates):
    n = _normalize(name)
    best = None
    best_score = 0
    for c in candidates:
        cn = _normalize(c)
        if not cn:
            continue
        matches = sum(1 for a, b in zip(n, cn) if a == b)
        score = matches / max(len(n), len(cn), 1)
        if score > best_score:
            best_score = score
            best = c
    return best, best_score


def _resolve_slugs(slug1, slug2, source, url):
    if slug2 and slug2.isdigit():
        slug2 = ''

    n1 = _normalize(slug1)
    n2 = _normalize(slug2)

    if not n2:
        for sep in ['-vs-', '-v-', '_vs_']:
            if sep in slug1:
                parts = slug1.split(sep, 1)
                n1 = _normalize(parts[0])
                n2 = _normalize(parts[1])
                break

    words = n1.split() + n2.split()
    if not words:
        return None

    best_score = -1
    best_home = ''
    best_away = ''

    for i in range(1, len(words)):
        h = ' '.join(words[:i])
        a = ' '.join(words[i:])
        valid1, valid2, r1, r2 = _validate_team(h, a)
        score = 3 if (valid1 and valid2) else (1 if (valid1 or valid2) else 0)
        if score > best_score:
            best_score = score
            best_home = r1 if valid1 else h
            best_away = r2 if valid2 else a

    if best_score <= 0:
        best_score = -1
        raw_combined = f"{slug1}-vs-{slug2}" if slug2 else slug1
        for sep in ['-vs-', '-v-', '_vs_', '-']:
            parts = re.split(sep, raw_combined)
            if len(parts) < 2:
                continue
            nh = parts[0].replace('-', ' ').replace('_', ' ').strip()
            na = parts[-1].replace('-', ' ').replace('_', ' ').strip()
            if not nh or not na:
                continue
            h_match, h_score = _fuzzy_match(nh, _TEAM_NAMES)
            a_match, a_score = _fuzzy_match(na, _TEAM_NAMES)
            score = h_score + a_score
            if score > best_score:
                best_score = score
                best_home = h_match.title() if h_match else nh.title()
                best_away = a_match.title() if a_match else na.title()

    if best_score < 0:
        return None

    return {
        'home_team': _clean_team_name(best_home),
        'away_team': _clean_team_name(best_away),
        'source': source,
        'url': url
    }


def parse_match_url(url):
    url = url.strip()
    if not url.startswith('http'):
        url = 'https://' + url
    url = unquote(url)

    m = SOFASCORE_PATTERN.search(url)
    if m:
        slug1 = m.group(1)
        slug2 = m.group(2) or ''
        return _resolve_slugs(slug1, slug2, 'sofascore', url)

    m = FLASHSCORE_PATTERN.search(url)
    if m:
        return _resolve_slugs(m.group(1), m.group(2), 'flashscore', url)

    m = LIVESCORE_PATTERN.search(url)
    if m:
        return _resolve_slugs(m.group(1), m.group(2), 'livescore', url)

    m = FOTMOB_PATTERN.search(url)
    if m:
        return _resolve_slugs(m.group(1), m.group(2), 'fotmob', url)

    m = WHOSCORED_PATTERN.search(url)
    if m:
        return _resolve_slugs(m.group(1), m.group(2), 'whoscored', url)

    m = GENERIC_VS_PATTERN.search(url)
    if m:
        return _resolve_slugs(m.group(1), m.group(2), 'generic', url)

    return None

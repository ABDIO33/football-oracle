"""
FIRE 🔥 — FOTMOB MASSIVE HEIST RUNNER
Run this directly: python -X utf8 heist_fotmob_runner.py
"""
import sys, os, time, json
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))
from heist_fotmob_bulk import *

print('🔥🔥🔥 FOTMOB MASSIVE HEIST 🔥🔥🔥')
print(f'Started: {datetime.now().isoformat()}')

bid = get_build_id()
print(f'Build ID: {bid}')

# Comprehensive league list
VERIFIED_LEAGUES = {
    47: 'Premier League',
    53: 'LaLiga',
    54: 'Bundesliga',
    55: 'Serie A',
    74: 'Ligue 1',
    48: 'Championship',
    49: 'League One',
    50: 'League Two',
    137: 'LaLiga2',
    56: '2. Bundesliga',
    73: 'UEFA Champions League',
    72: 'UEFA Europa League',
    87: 'Primeira Liga',
    59: 'Eredivisie',
    62: 'Scottish Premiership',
    64: 'Süper Lig',
    65: 'Russian PL',
    130: 'MLS',
    133: 'Liga MX',
    135: 'Brasileirão',
    138: 'Argentine PD',
    153: 'J1 League',
    155: 'K League 1',
    157: 'CSL',
    162: 'Saudi PL',
    166: 'AFC CL',
    178: 'CAF CL',
    202: 'A-League',
    364: 'Copa Libertadores',
    365: 'Copa Sudamericana',
    61: 'Belgian PL',
    67: 'Greek SL',
    68: 'Czech FL',
    69: 'Ekstraklasa',
    70: 'HNL',
    71: 'Swiss SL',
    75: 'Allsvenskan',
    76: 'Eliteserien',
    77: 'Danish SL',
    88: 'Liga Portugal 2',
    57: 'Serie B',
    58: 'Ligue 2',
    60: 'Eerste Divisie',
    63: 'Scottish Champ',
    66: 'Ukrainian PL',
    131: 'USL Champ',
    136: 'Série B (BRA)',
    139: 'Primera B Nac',
    140: 'Primera CHI',
    141: 'Primera PER',
    142: 'Primera COL',
    146: 'Primera URU',
    147: 'Serie A ECU',
    148: 'Primera VEN',
    149: 'Primera PAR',
    150: 'Primera BOL',
    152: 'CanPL',
    154: 'J2 League',
    156: 'K League 2',
    158: 'China L1',
    159: 'ISL',
    161: 'Thai L1',
    163: 'UAE PL',
    164: 'Qatar SL',
    165: 'Iran PL',
    168: 'Uzbek SL',
    169: 'V-League',
    180: 'Egypt PL',
    181: 'Botola Pro',
    184: 'SA PSL',
    208: 'FIFA WC',
    209: 'Euro Champ',
    210: 'Copa América',
    211: 'AFCON',
    216: 'UEFA NL',
    221: 'WCQ UEFA',
    222: 'WCQ CONMEBOL',
    223: 'WCQ CONCACAF',
    224: 'WCQ CAF',
    225: 'WCQ AFC',
    231: 'FA WSL',
    236: 'NWSL',
    241: 'FIFA WWC',
    359: 'Primera PAR',
    361: 'Primera BOL',
    362: 'Primera VEN',
    367: 'Liga MX',
    381: 'CONCACAF CC',
    384: 'J1 League',
    387: 'K League 1',
    389: 'CSL',
    392: 'ISL',
    394: 'Thai L1',
    396: 'Saudi PL',
    398: 'UAE PL',
    400: 'Qatar SL',
    402: 'Iran PL',
    406: 'V-League',
    408: 'Malaysia SL',
    410: 'Liga 1 IDN',
    412: 'SGP PL',
    413: 'HK PL',
    421: 'AFC CL Elite',
    424: 'CAF CL',
    427: 'Egypt PL',
    429: 'Botola Pro',
    431: 'Algeria L1',
    433: 'Tunisia L1',
    435: 'SA PSL',
    439: 'NPFL',
    443: 'DRC Linafoot',
    444: 'Zambia SL',
    447: 'CIV L1',
    448: 'CMR Elite',
    450: 'Angola Girabola',
    452: 'TZ Ligi Kuu',
    453: 'Uganda PL',
    455: 'Ethiopia PL',
    489: 'A-League',
    494: 'OFC CL',
    514: 'Copa del Rey',
    515: 'DFB-Pokal',
    516: 'FA Cup',
    517: 'Coupe de France',
    518: 'Coppa Italia',
    519: 'EFL Cup',
    525: 'Taça de Portugal',
    526: 'KNVB Beker',
    527: 'Scottish Cup',
    534: 'Svenska Cupen',
    593: 'Copa do Brasil',
    594: 'Copa Argentina',
    605: 'US Open Cup',
    606: 'J.League Cup',
    607: "Emperor's Cup",
    608: 'Korean FA Cup',
    651: 'PL2',
}

print(f'\nTargeting {len(VERIFIED_LEAGUES)} leagues')
total_matches = 0
leagues_ok = 0
leagues_fail = 0
match_log = []

# === PHASE 1: League Overviews ===
print('\n=== PHASE 1: League Overviews ===\n')

for lid, name in VERIFIED_LEAGUES.items():
    try:
        pp = fetch_league_via_data_route(lid, bid)
        if pp is None:
            pp = fetch_league_page(lid)
        
        match_count = 0
        if pp:
            matches = extract_matches_from_pageprops(pp, lid)
            parsed = []
            for m in matches:
                pm = parse_fotmob_match(m)
                if pm:
                    pm['league_name'] = name
                    parsed.append(pm)
            
            match_count = len(parsed)
            if match_count > 0:
                save_league_data(lid, 'overview', pp)
                save_league_teams_standings(lid, pp)
                update_progress(lid, 'done', match_count, match_count)
                
                append_jsonl(f'fotmob_{lid}', {
                    'league_id': lid, 'league_name': name,
                    'matches': parsed, 'count': match_count,
                })
                total_matches += match_count
                leagues_ok += 1
            else:
                leagues_ok += 1  # Still ok, just no matches currently
        else:
            leagues_fail += 1
        
        print(f'  {name:35s} => {match_count:5d} matches')
        time.sleep(0.15 + (0.1 if leagues_fail > 10 else 0))
        
    except Exception as e:
        leagues_fail += 1
        if leagues_fail <= 5:
            print(f'  {name:35s} => ERROR: {str(e)[:60]}')

print(f'\nPhase 1 done: {leagues_ok} OK, {leagues_fail} fail, {total_matches} total matches')

# === PHASE 2: Match Details (top leagues only) ===
print('\n=== PHASE 2: Match Details (top 10 leagues) ===\n')

top_lids = [47, 53, 54, 55, 74, 48, 73, 130, 133, 135, 138, 364, 365, 87, 59, 153, 162, 202]
detail_count = 0

for lid in top_lids:
    if lid not in VERIFIED_LEAGUES:
        continue
    try:
        pp = fetch_league_via_data_route(lid, bid)
        if pp is None:
            continue
        matches = extract_matches_from_pageprops(pp, lid)
        finished_matches = [m for m in matches 
                          if isinstance(m, dict) and 
                          m.get('status', {}).get('finished', False) and 
                          m.get('id')][:100]
        
        for m in finished_matches:
            try:
                mid = m.get('id') or m.get('matchId')
                if not mid:
                    continue
                pp2 = get_match_detail_nextjs(mid, bid)
                if pp2:
                    detail = extract_match_stats_from_detail(pp2)
                    detail['league_id'] = lid
                    append_jsonl('fotmob_detail', detail)
                    detail_count += 1
                time.sleep(0.25)
            except:
                pass
        
        print(f'  {VERIFIED_LEAGUES[lid]:35s} => {detail_count} total details')
    except:
        pass

print(f'\nPhase 2 done: {detail_count} match details')

# === FINAL REPORT ===
print('\n' + '='*60)
print('HEIST COMPLETE')
print('='*60)
print(f'  Leagues OK:    {leagues_ok}')
print(f'  Leagues fail:  {leagues_fail}')
print(f'  Total matches: {total_matches}')
print(f'  Match details: {detail_count}')
print(f'  Finished: {datetime.now().isoformat()}')

# Save summary
append_jsonl('fotmob_summary', {
    'leagues_ok': leagues_ok,
    'leagues_fail': leagues_fail,
    'total_matches': total_matches,
    'detail_count': detail_count,
    'completed_at': datetime.now(timezone.utc).isoformat(),
})

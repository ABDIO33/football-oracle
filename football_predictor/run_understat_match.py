#!/usr/bin/env python3
"""
Understat Matcher — يطابق فرق تحتستات مع بيانات التدريب
باستخدام rapidfuzz + unidecode + manual mapping
"""
import sys, os, sqlite3, json
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

from rapidfuzz import fuzz
from unidecode import unidecode

MANUAL_MAP = {
    'SD Huesca': 'Huesca', 'FC Heidenheim': 'Heidenheim',
    'Borussia M.Gladbach': 'Borussia Mönchengladbach',
    'Greuther Fuerth': 'Greuther Fürth', 'Parma Calcio 1913': 'Parma',
    'AC Milan': 'Milan', 'FC Internazionale': 'Inter Milan',
    '1. FC Koeln': 'FC Cologne', '1. FC Köln': 'FC Cologne',
    'Bayer 04 Leverkusen': 'Bayer Leverkusen',
    'Hertha Berlin': 'Hertha BSC', 'Hertha BSC': 'Hertha Berlin',
    'RB Leipzig': 'RasenBallsport Leipzig',
    'FC Salzburg': 'RB Salzburg', 'Red Bull Salzburg': 'RB Salzburg',
    'Sporting CP': 'Sporting Lisbon', 'Paris Saint Germain': 'Paris Saint Germain',
    'FC Cologne': 'FC Koln', 'Wolverhampton Wanderers': 'Wolverhampton',
    'Mainz 05': 'Mainz', 'SPAL 2013': 'SPAL',
    # Russian teams (keep as-is, may not be in training)
    'Akron': 'Akron', 'Amkar': 'Amkar Perm', 'Anzhi Makhachkala': 'Anzhi Makhachkala',
    'Arsenal Tula': 'Arsenal Tula', 'Baltika': 'Baltika Kaliningrad',
    'FC Rotor Volgograd': 'Rotor Volgograd', 'FC Tambov': 'Tambov',
    'FC Ufa': 'Ufa', 'FC Yenisey Krasnoyarsk': 'Yenisey',
    'FK Akhmat': 'Akhmat Grozny', 'Fakel': 'Fakel Voronezh',
    'Khimki': 'Khimki', 'Kuban Krasnodar': 'Kuban Krasnodar',
    'Mordovya': 'Mordovia Saransk', 'Nizhny Novgorod': 'Nizhny Novgorod',
    'PFC Sochi': 'Sochi', 'SKA-Khabarovsk': 'SKA Khabarovsk',
    'Tom Tomsk': 'Tom Tomsk', 'Torpedo Moscow': 'Torpedo Moskva',
    'Tosno': 'Tosno', 'Ural': 'Ural Yekaterinburg',
    # Common European teams with shortened names in football-data
    'Arminia Bielefeld': 'Bielefeld',
    'Athletic Club': 'Ath Bilbao',
    'Atletico Madrid': 'Ath Madrid',
    'Bayer Leverkusen': 'Leverkusen',
    'Borussia Dortmund': 'Dortmund',
    'Celta Vigo': 'Celta',
    'Clermont Foot': 'Clermont',
    'Deportivo La Coruna': 'La Coruna',
    'Hamburger SV': 'Hamburg',
    'Manchester City': 'Man City',
    'Manchester United': 'Man United',
    'Newcastle United': 'Newcastle',
    'Queens Park Rangers': 'QPR',
    'Rayo Vallecano': 'Vallecano',
    'Real Betis': 'Betis',
    'Real Oviedo': 'Oviedo',
    'Real Sociedad': 'Real Sociedad',
    'Saint-Etienne': 'St Etienne',
    'Sporting Gijon': 'Sp Gijon',
    'West Bromwich Albion': 'West Brom',
    # Russian teams - keep Russian
    'CSKA Moscow': 'CSKA Moscow',
    'Dinamo Moscow': 'Dinamo Moscow',
    'Dynamo Makhachkala': 'Dynamo Makhachkala',
    'FC Krasnodar': 'Krasnodar',
    'FC Orenburg': 'Orenburg',
    'FC Rostov': 'Rostov',
    'Krylya Sovetov Samara': 'Krylya Sovetov',
    'Lokomotiv Moscow': 'Lokomotiv Moscow',
    'Rubin Kazan': 'Rubin Kazan',
    'Spartak Moscow': 'Spartak Moscow',
    'Zenit St. Petersburg': 'Zenit',
    # Remaining 32 teams that failed fuzzy matching
    'CSKA Moscow': 'CSKA Moscow',
    'Dinamo Moscow': 'Dynamo Moscow',
    'Spartak Moscow': 'FC Spartak Moscow',
    'Lokomotiv Moscow': 'Lokomotiv Moscow',
    'Torpedo Moscow': 'Torpedo Moscow',
    'Zenit St. Petersburg': 'Zenit St. Petersburg',
    'FC Krasnodar': 'FC Krasnodar',
    'FC Rostov': 'FC Rostov',
    'FC Orenburg': 'FC Orenburg',
    'Krylya Sovetov Samara': 'Krylya Sovetov Samara',
    'Rubin Kazan': 'Rubin Kazan',
    'Dynamo Makhachkala': 'Dynamo Makhachkala',
    # Already above but ensure coverage
    'Akron': 'Akron',
    'Amkar': 'Amkar Perm',
    'Anzhi Makhachkala': 'Anzhi Makhachkala',
    'Arsenal Tula': 'Arsenal Tula',
    'Baltika': 'Baltika Kaliningrad',
    'FC Rotor Volgograd': 'FC Rotor Volgograd',
    'FC Tambov': 'FC Tambov',
    'FC Ufa': 'FC Ufa',
    'FC Yenisey Krasnoyarsk': 'FC Yenisey Krasnoyarsk',
    'FK Akhmat': 'FK Akhmat',
    'Fakel': 'Fakel',
    'Khimki': 'Khimki',
    'Kuban Krasnodar': 'Kuban Krasnodar',
    'Mordovya': 'Mordovya Saransk',
    'Nizhny Novgorod': 'Nizhny Novgorod',
    'PFC Sochi': 'PFC Sochi',
    'SKA-Khabarovsk': 'SKA-Khabarovsk',
    'Tom Tomsk': 'Tom Tomsk',
    'Ural': 'Ural Yekaterinburg',
}

def clean(n):
    return unidecode(n).replace('.',' ').strip().lower()

conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()

# Get teams
ut = set(t[0] for t in c.execute('SELECT DISTINCT home_team FROM source_understat UNION SELECT DISTINCT away_team FROM source_understat').fetchall())
fd = set(t[0] for t in c.execute('SELECT DISTINCT home_team FROM source_football_data_uk UNION SELECT DISTINCT away_team FROM source_football_data_uk').fetchall())
print(f'Understat teams: {len(ut)}', flush=True)
print(f'Training teams: {len(fd)}', flush=True)

# Match
results = {}
matched = 0
for u in sorted(ut):
    if u in MANUAL_MAP:
        results[u] = MANUAL_MAP[u]; matched += 1; continue
    
    # Direct match
    if u in fd:
        results[u] = u; matched += 1; continue
    
    # Clean match
    uc = clean(u)
    found = False
    for f in fd:
        if uc == clean(f):
            results[u] = f; matched += 1; found = True; break
    if found: continue
    
    # Fuzzy
    best, best_score = '', 0
    for f in fd:
        s = fuzz.token_sort_ratio(uc, clean(f))
        if s > best_score: best, best_score = f, s
    if best_score >= 80:
        results[u] = best; matched += 1
    else:
        results[u] = f'❌ {best}({best_score}%)'

print(f'\nMatched: {matched}/{len(ut)} = {matched/len(ut)*100:.0f}%')
for u, r in results.items():
    if '❌' in r:
        print(f'  FAILED: {u:35s} → {r}')

# Save mapping
with open(os.path.join(BASE, 'understat_mapping.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'\nMapping saved to understat_mapping.json')

# Count usable Understat matches (both teams in training)
matched_set = {v for v in results.values() if '❌' not in v}
usable = c.execute(f'''SELECT COUNT(*) FROM source_understat u
    WHERE u.home_team IN ({','.join('?' for _ in matched_set)})
    AND u.away_team IN ({','.join('?' for _ in matched_set)})
''', list(matched_set) * 2).fetchone()[0]
print(f'Usable Understat matches (both teams found): {usable:,} / 49,238')
print(f'OLD: ~26K (53%) | NEW: ~{usable:,} ({usable/49238*100:.0f}%)')

conn.close()

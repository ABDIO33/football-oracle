#!/usr/bin/env python3
"""
Understat Matcher V2 — يطابق كل فرق تحتستات مع بيانات التدريب
باستخدام rapidfuzz + unidecode + manual mapping شامل
"""
import sys, os, sqlite3, json, warnings
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')

from rapidfuzz import fuzz
from unidecode import unidecode

MANUAL = {
    # Known differences from analysis
    'Bayer Leverkusen': 'Bayer 04 Leverkusen',
    'Borussia M.Gladbach': "Borussia M'gladbach",
    'Borussia Mönchengladbach': "Borussia M'gladbach",
    'Deportivo La Coruna': 'Deportivo de La Coruña',
    'Dinamo Moscow': 'Dynamo Moscow',
    'Dynamo Makhachkala': 'Dinamo Makhachkala',
    'Fortuna Duesseldorf': 'Fortuna Düsseldorf',
    'Greuther Fuerth': 'Greuther Furth',
    'Nuernberg': 'Nurnberg',
    'FC Heidenheim': '1. FC Heidenheim',
    'SC Bastia': 'Bastia',
    'Spartak Moscow': 'FC Spartak Moscow',
    'St. Pauli': 'St Pauli',
    'FC Koln': 'FC Cologne', 'FC Koln': 'FC Cologne',
    'Hertha Berlin': 'Hertha BSC',
    'Hertha BSC': 'Hertha Berlin',
    # Common shortened names
    'Manchester City': 'Man City',
    'Manchester United': 'Man United',
    'Newcastle United': 'Newcastle',
    'West Bromwich Albion': 'West Brom',
    'Queens Park Rangers': 'QPR',
    'Wolverhampton Wanderers': 'Wolverhampton',
    'Paris Saint Germain': 'Paris Saint Germain',
    'Saint-Etienne': 'St Etienne',
    'Arminia Bielefeld': 'Bielefeld',
    'Hamburger SV': 'Hamburg',
    'Mainz 05': 'Mainz',
    'FC Cologne': 'FC Koln',
    '1. FC Koeln': 'FC Koln', '1. FC Köln': 'FC Koln',
    'RasenBallsport Leipzig': 'RB Leipzig',
    'RB Leipzig': 'RasenBallsport Leipzig',
    'Athletic Club': 'Ath Bilbao',
    'Atletico Madrid': 'Ath Madrid',
    'Celta Vigo': 'Celta',
    'Clermont Foot': 'Clermont',
    'Rayo Vallecano': 'Vallecano',
    'Real Betis': 'Betis',
    'Real Oviedo': 'Oviedo',
    'Real Sociedad': 'Real Sociedad',
    'Sporting Gijon': 'Sp Gijon',
    'SD Huesca': 'Huesca',
    'Parma Calcio 1913': 'Parma',
    'SPAL 2013': 'SPAL',
    'AC Milan': 'Milan',
    'FC Internazionale': 'Inter Milan',
    'FC Salzburg': 'RB Salzburg',
    'Red Bull Salzburg': 'RB Salzburg',
    'Sporting CP': 'Sporting Lisbon',
    'GFC Ajaccio': 'Ajaccio GFCO',
    # Russian teams
    'CSKA Moscow': 'CSKA Moscow',
    'Lokomotiv Moscow': 'Lokomotiv Moscow',
    'Zenit St. Petersburg': 'Zenit St. Petersburg',
    'FC Krasnodar': 'FC Krasnodar',
    'FC Rostov': 'FC Rostov',
    'Dinamo Moscow': 'Dynamo Moscow',
    'Spartak Moscow': 'FC Spartak Moscow',
    'Rubin Kazan': 'Rubin Kazan',
    'FC Orenburg': 'Orenburg',
    'Torpedo Moscow': 'Torpedo Moscow',
    'Krylya Sovetov Samara': 'Krylya Sovetov Samara',
    # Keep Russian teams as-is (may not be in training data)
    'Akron': 'Akron', 'Amkar': 'Amkar',
    'Anzhi Makhachkala': 'Anzhi Makhachkala',
    'Arsenal Tula': 'Arsenal Tula',
    'Baltika': 'Baltika Kaliningrad',
    'FC Rotor Volgograd': 'Rotor Volgograd',
    'FC Tambov': 'Tambov',
    'FC Ufa': 'FC Ufa',
    'FC Yenisey Krasnoyarsk': 'Yenisey',
    'FK Akhmat': 'Akhmat Grozny',
    'Fakel': 'Fakel', 'Khimki': 'Khimki',
    'Kuban Krasnodar': 'Kuban Krasnodar',
    'Mordovya': 'Mordovia',
    'Nizhny Novgorod': 'Nizhny Novgorod',
    'PFC Sochi': 'Sochi',
    'SKA-Khabarovsk': 'SKA Khabarovsk',
    'Tom Tomsk': 'Tom Tomsk',
    'Tosno': 'Tosno',
    'Ural': 'Ural',
}

def clean(n):
    return unidecode(n).replace('.',' ').lower().strip()

conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()

# Get all teams
understat = set(t[0] for t in c.execute(
    'SELECT DISTINCT home_team FROM source_understat UNION SELECT DISTINCT away_team FROM source_understat').fetchall())
fd = set(t[0] for t in c.execute(
    'SELECT DISTINCT home_team FROM source_football_data_uk UNION SELECT DISTINCT away_team FROM source_football_data_uk').fetchall())
ss = set(t[0] for t in c.execute(
    'SELECT DISTINCT home_team FROM source_sofascore_extended UNION SELECT DISTINCT away_team FROM source_sofascore_extended').fetchall())
all_ref = fd | ss

print(f'Understat: {len(understat)}, Reference: {len(all_ref)}', flush=True)

results = {}
for ut in sorted(understat):
    if ut in MANUAL:
        results[ut] = MANUAL[ut]
        continue
    if ut in all_ref:
        results[ut] = ut
        continue
    uc = clean(ut)
    if any(uc == clean(r) for r in all_ref):
        results[ut] = [r for r in all_ref if uc == clean(r)][0]
        continue
    # Fuzzy match
    best, best_s = '', 0
    for r in all_ref:
        s = fuzz.token_sort_ratio(uc, clean(r))
        if s > best_s:
            best, best_s = r, s
    if best_s >= 80:
        results[ut] = best
        print(f'  FUZZY({best_s:.0f}%): {ut:40s} → {best}', flush=True)
    else:
        results[ut] = f'❌BEST:{best}({best_s:.0f}%)'
        print(f'  ❌ FAILED[{best_s:.0f}%]: {ut:40s} → {best}', flush=True)

matched = sum(1 for v in results.values() if '❌' not in v)
print(f'\n✅ Matched: {matched}/{len(results)} = {matched/len(results)*100:.1f}%', flush=True)

# Save mapping
with open(os.path.join(BASE, 'understat_mapping.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'Saved understat_mapping.json', flush=True)

# Count usable matches
matched_names = {v for v in results.values() if '❌' not in v}
if matched_names:
    placeholders = ','.join('?' for _ in matched_names)
    usable = c.execute(f'''
        SELECT COUNT(*) FROM source_understat u
        WHERE u.home_team IN ({placeholders})
        AND u.away_team IN ({placeholders})
    ''', list(matched_names) + list(matched_names)).fetchone()[0]
    print(f'Usable: {usable:,}/49,238 = {usable/49238*100:.1f}% (was 53%)', flush=True)

conn.close()

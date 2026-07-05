#!/usr/bin/env python3
"""المرحلة 1: استخراج كل الميزات من قاعدة البيانات الضخمة 🦅"""

import sqlite3, math, json, os, sys
import numpy as np
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'scrape_cache.db')
FOOTBALL_DB = os.path.join(BASE, 'football_data.db')
OUT = os.path.join(BASE, 'build_legend')

os.makedirs(OUT, exist_ok=True)

print('='*70)
print('🔥 المرحلة 1: استخراج الميزات من قواعد البيانات الضخمة')
print('='*70)

conn = sqlite3.connect(DB)

# ========== 1. COUNT ALL DATA ==========
print('\n📊 إحصائيات قواعد البيانات:')

tables_info = {
    'walkforward_state': 'Elos + xG لكل فريق',
    'glicko_state': 'Glicko ratings',
    'neg_team_strength': 'قوة الفرق (هجوم/دفاع)',
    'neg_poisson_params': 'Poisson params',
    'neg_h2h_features': 'تاريخ المواجهات',
    'neg_streaks': 'سلاسل النتائج',
    'neg_league_averages': 'متوسطات الدوريات',
    'source_clubelo_enhanced': 'Club Elo محدث',
    'source_livescore': 'نتائج حية سابقة',
    'flashscore_matches': 'مباريات Flashscore',
    'sofa_match_stats': 'إحصائيات SofaScore',  
    'source_weather': 'الطقس',
    'venue_weather': 'حالة الطقس للملاعب',
    'team_venue': 'مواقع الفرق',
    'unified_features': 'ميزات موحدة',
    'unified_odds': 'الاحتمالات الموحدة',
    'team_ratings': 'تقييمات الفرق',
}

total_rows = 0
for table, desc in tables_info.items():
    try:
        c = conn.cursor()
        c.execute(f'SELECT COUNT(*) FROM {table}')
        count = c.fetchone()[0]
        print(f'  📁 {table}: {count:,} صف ← {desc}')
        total_rows += count
    except Exception as e:
        pass

print(f'\n  💾 المجموع: {total_rows:,} صف في قاعدة البيانات')

# ========== 2. EXTRACT ELO DATA ==========
print('\n📥 استخراج Elos...')
elo_data = {}
c = conn.cursor()
c.execute('SELECT team_name, elo, rolling_xg_for, rolling_xg_against, form_points, matches_played FROM walkforward_state WHERE elo IS NOT NULL')
count = 0
for row in c.fetchall():
    team = row[0]
    if team not in elo_data or (row[5] or 0) > elo_data[team].get('matches', 0):
        elo_data[team] = {
            'elo': float(row[1] or 1500),
            'xg_for': float(row[2] or 1.2),
            'xg_against': float(row[3] or 1.2),
            'form': float(row[4] or 0.5),
            'matches': int(row[5] or 0)
        }
    count += 1
    if count % 100000 == 0:
        print(f'    {count:,}...')

print(f'  ✅ {len(elo_data)} فريق مع Elo')

# ========== 3. EXTRACT POISSON PARAMS ==========
print('\n📥 استخراج Poisson params...')
poisson_data = {}
c.execute('SELECT team_name, attack_strength_home, attack_strength_away, defense_strength_home, defense_strength_away, lambda_home_scored, lambda_away_scored FROM neg_poisson_params')
for row in c.fetchall():
    poisson_data[row[0]] = {
        'att_h': float(row[1] or 1.0), 'att_a': float(row[2] or 1.0),
        'def_h': float(row[3] or 1.0), 'def_a': float(row[4] or 1.0),
        'lam_h': float(row[5] or 1.2), 'lam_a': float(row[6] or 0.8),
    }
print(f'  ✅ {len(poisson_data)} فريق مع Poisson params')

# ========== 4. EXTRACT H2H ==========
print('\n📥 استخراج H2H...')
h2h_data = {}
c.execute('SELECT home_team, away_team, home_wins, draws, away_wins, home_goals_total, away_goals_total FROM neg_h2h_features')
for row in c.fetchall():
    h2h_data[(row[0], row[1])] = {
        'hw': int(row[2] or 0), 'dr': int(row[3] or 0), 'aw': int(row[4] or 0),
        'hg': float(row[5] or 0), 'ag': float(row[6] or 0),
        'total': int(row[2] or 0) + int(row[3] or 0) + int(row[4] or 0),
    }
print(f'  ✅ {len(h2h_data)} H2H records')

# ========== 5. EXTRACT RECENT FORM ==========
print('\n📥 استخراج آخر النتائج...')
form_data = defaultdict(list)
c.execute('SELECT home_team, away_team, home_score, away_score, match_date FROM source_livescore WHERE home_score IS NOT NULL ORDER BY match_date DESC')
for row in c.fetchall():
    home, away, hs, av, date = row
    try:
        hs, av = int(hs), int(av)
        form_data[home].append({'gf': hs, 'ga': av, 'is_home': True, 'date': date})
        form_data[away].append({'gf': av, 'ga': hs, 'is_home': False, 'date': date})
    except: pass

# Keep last 10 per team
for team in form_data:
    form_data[team] = form_data[team][:10]

print(f'  ✅ {len(form_data)} فريق مع آخر النتائج')

# ========== 6. SAVE ALL ==========
print('\n💾 حفظ البيانات...')
np.savez_compressed(
    os.path.join(OUT, 'extracted_data.npz'),
    elo_data=elo_data,
    poisson_data=poisson_data,
    h2h_data=h2h_data,
    form_data=form_data,
)

# Save team list
teams = set()
teams.update(elo_data.keys())
teams.update(poisson_data.keys())
for h, a in h2h_data:
    teams.add(h); teams.add(a)
teams.update(form_data.keys())

with open(os.path.join(OUT, 'all_teams.json'), 'w', encoding='utf-8') as f:
    json.dump(sorted(teams), f, ensure_ascii=False)

print(f'  ✅ {len(teams)} فريق فريد في المجموع')
print(f'\n{"="*70}')
print(f'✅ المرحلة 1 اكتملت!')
print(f'   {len(elo_data)} Elo | {len(poisson_data)} Poisson | {len(h2h_data)} H2H | {len(form_data)} Form')
print(f'   {len(teams)} فريق')
print(f'{"="*70}')

conn.close()

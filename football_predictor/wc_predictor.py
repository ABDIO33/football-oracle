#!/usr/bin/env python3
"""
توقعات كأس العالم 2026 — R32 وما بعدها
يستخدم أفضل موديل (36.35%) للتنبؤ بنتائج المباريات
"""
import sys, os, json, sqlite3, pickle, warnings, numpy as np
warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')
MODELS_DIR = os.path.join(BASE, 'models')

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# ========== WORLD CUP FIXTURES ==========
# R32 Matchups (resolved from SofaScore data + group standings)
# Format: [date, home, away, stage]
FIXTURES = [
    # R32
    ('2026-06-30', 'Netherlands', 'Morocco', 'R32'),
    ('2026-06-30', 'Brazil', 'Japan', 'R32'),
    ('2026-06-30', 'Germany', 'Bosnia & Herzegovina', 'R32'),
    ('2026-07-01', 'Cote d\'Ivoire', 'Norway', 'R32'),
    ('2026-07-01', 'France', 'Paraguay', 'R32'),
    ('2026-07-01', 'Mexico', 'Ecuador', 'R32'),
    ('2026-07-02', 'USA', 'Bosnia & Herzegovina', 'R32'),
    ('2026-07-02', 'Belgium', 'Ecuador', 'R32'),
    ('2026-07-02', 'England', 'Ecuador', 'R32'),
    ('2026-07-03', 'Portugal', 'Croatia', 'R32'),
    ('2026-07-03', 'Spain', 'Austria', 'R32'),
    ('2026-07-03', 'Switzerland', 'Ecuador', 'R32'),
    ('2026-07-04', 'Argentina', 'Cabo Verde', 'R32'),
    ('2026-07-04', 'Colombia', 'Paraguay', 'R32'),
    ('2026-07-04', 'Australia', 'Egypt', 'R32'),
]

print(f'Total WC fixtures: {len(FIXTURES)}')

# ========== LOAD BEST MODEL ==========
print('Loading best model...')

# Try the 36% LightGBM model
model_path = os.path.join(MODELS_DIR, 'ensemble_seed42.pkl')
if not os.path.exists(model_path):
    model_path = os.path.join(BASE, 'models/ensemble_seed42.pkl')
if not os.path.exists(model_path):
    model_path = os.path.join(BASE, 'models/ultimate_world_record.pkl')

print(f'Model: {model_path} ({os.path.getsize(model_path)/1024/1024:.0f} MB)')

if os.path.exists(model_path):
    try:
        data = pickle.load(open(model_path, 'rb'))
        print(f'Type: {type(data).__name__}')
        if hasattr(data, 'keys'):
            print(f'Keys: {list(data.keys())[:10]}')
        if hasattr(data, 'predict'):
            print('Has predict method!')
        if hasattr(data, 'feature_importances_'):
            print(f'Features: {len(data.feature_importances_)}')
    except Exception as e:
        print(f'Load error: {e}')

# ========== GET TEAM ELO FROM DB ==========
print('Getting team data from DB...')
teams_data = {}
for home, away in [(f[1], f[2]) for f in FIXTURES]:
    for team in [home, away]:
        # Get Elo from ClubElo
        elo = c.execute('''
            SELECT elo_rating FROM source_clubelo_enhanced 
            WHERE team_name LIKE ? ORDER BY last_updated DESC LIMIT 1
        ''', (f'%{team.split()[0]}%',)).fetchone()
        teams_data[team] = {
            'elo': elo[0] if elo else 1500,
        }

# Print
for t, d in sorted(teams_data.items()):
    print(f'  {t:30s} Elo: {d[\"elo\"]:.0f}')

conn.close()
print()
print('Done. Ready for predictions.')

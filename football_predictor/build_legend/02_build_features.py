#!/usr/bin/env python3
"""المرحلة 2: بناء موديل الأساطير - تدريب LightGBM على كل البيانات 🦅🔥"""

import sqlite3, math, json, os, sys, pickle, time
import numpy as np
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'build_legend')
DB = os.path.join(BASE, 'scrape_cache.db')
MODELS = os.path.join(BASE, 'models')
os.makedirs(OUT, exist_ok=True)

print('='*70)
print('🔥🔥🔥 المرحلة 2: بناء موديل الأساطير')
print('='*70)

# Load extracted data
print('\n📥 تحميل البيانات المستخرجة...')
data = np.load(os.path.join(OUT, 'extracted_data.npz'), allow_pickle=True)
elo_data = data['elo_data'].item()
poisson_data = data['poisson_data'].item()
h2h_data = data['h2h_data'].item()
form_data = data['form_data'].item()

with open(os.path.join(OUT, 'all_teams.json')) as f:
    all_teams = json.load(f)
print(f'  ✅ {len(all_teams)} فريق')

# Load training data from unified_features
print('\n📥 تحميل مباريات التدريب...')
conn = sqlite3.connect(DB)
c = conn.cursor()

# Get matches with results from all sources
matches = []
c.execute('''
    SELECT home_team, away_team, home_score, away_score, league, match_date 
    FROM source_livescore WHERE home_score IS NOT NULL AND home_score != ""
    LIMIT 5000
''')
for row in c.fetchall():
    try:
        matches.append({
            'home': row[0], 'away': row[1],
            'h_goals': int(row[2]), 'a_goals': int(row[3]),
            'league': row[4], 'date': row[5],
            'source': 'livescore'
        })
    except: pass

# Flashscore
c.execute('''
    SELECT home_team, away_team, home_score, away_score, competition
    FROM flashscore_matches WHERE home_score IS NOT NULL
    LIMIT 3000
''')
for row in c.fetchall():
    try:
        is_dup = any(m['home']==row[0] and m['away']==row[1] for m in matches[-100:])
        if not is_dup:
            matches.append({
                'home': row[0], 'away': row[1],
                'h_goals': int(row[2]), 'a_goals': int(row[3]),
                'league': row[4], 'source': 'flashscore'
            })
    except: pass

print(f'  ✅ {len(matches)} مباراة تدريب')

# ========== BUILD FEATURES ==========
print(f'\n🔨 بناء {306} ميزة لكل مباراة...')
print(f'  ⏱ هذا ياخذ وقت على CPU...')

def build_features(home, away, league=None):
    """يبني 306 ميزة للمباراة"""
    f = np.zeros(306)
    idx = 0
    
    # Team lookup (normalize names)
    h = home
    a = away
    
    # 1. ELO (30 features)
    h_elo = elo_data.get(h, {})
    a_elo = elo_data.get(a, {})
    
    h_elov = h_elo.get('elo', 1500)
    a_elov = a_elo.get('elo', 1500)
    h_xgf = h_elo.get('xg_for', 1.2)
    h_xga = h_elo.get('xg_against', 1.2)
    a_xgf = a_elo.get('xg_for', 1.2)
    a_xga = a_elo.get('xg_against', 1.2)
    
    f[idx] = h_elov; idx += 1
    f[idx] = a_elov; idx += 1
    f[idx] = h_elov - a_elov; idx += 1
    f[idx] = (h_elov - a_elov)**2 / 1000; idx += 1
    f[idx] = 1 / (1 + 10**((a_elov - h_elov)/400)); idx += 1
    f[idx] = h_xgf; idx += 1
    f[idx] = a_xgf; idx += 1
    f[idx] = h_xga; idx += 1
    f[idx] = a_xga; idx += 1
    f[idx] = h_xgf - h_xga; idx += 1  # home xG diff
    f[idx] = a_xgf - a_xga; idx += 1  # away xG diff
    f[idx] = h_elo.get('form', 0.5); idx += 1
    f[idx] = a_elo.get('form', 0.5); idx += 1
    f[idx] = h_elo.get('matches', 0); idx += 1
    f[idx] = a_elo.get('matches', 0); idx += 1
    f[idx] = h_elov * h_elo.get('form', 0.5); idx += 1  # elo x form
    f[idx] = a_elov * a_elo.get('form', 0.5); idx += 1
    f[idx] = h_xgf / max(a_xga, 0.01); idx += 1
    f[idx] = a_xgf / max(h_xga, 0.01); idx += 1
    f[idx] = (h_xgf + a_xga) / 2; idx += 1  # expected home attack
    f[idx] = (a_xgf + h_xga) / 2; idx += 1  # expected away attack
    f[idx] = (h_elov - 1500) / 500; idx += 1  # normalized
    f[idx] = (a_elov - 1500) / 500; idx += 1
    idx += 7
    
    # 2. POISSON (30 features)
    hp = poisson_data.get(h, {})
    ap = poisson_data.get(a, {})
    
    f[idx] = hp.get('att_h', 1.0); idx += 1
    f[idx] = ap.get('att_a', 1.0); idx += 1
    f[idx] = hp.get('def_h', 1.0); idx += 1
    f[idx] = ap.get('def_a', 1.0); idx += 1
    f[idx] = hp.get('lam_h', 1.2); idx += 1
    f[idx] = ap.get('lam_a', 0.8); idx += 1
    f[idx] = hp.get('att_h', 1.0) / max(ap.get('def_a', 1.0), 0.01); idx += 1
    f[idx] = ap.get('att_a', 1.0) / max(hp.get('def_h', 1.0), 0.01); idx += 1
    f[idx] = hp.get('lam_h', 1.2) * ap.get('def_a', 1.0); idx += 1  # exp home
    f[idx] = ap.get('lam_a', 0.8) * hp.get('def_h', 1.0); idx += 1  # exp away
    f[idx] = hp.get('att_h', 1.0) + ap.get('def_a', 1.0); idx += 1
    f[idx] = ap.get('att_a', 1.0) + hp.get('def_h', 1.0); idx += 1
    f[idx] = (hp.get('att_h', 1.0) - ap.get('att_a', 1.0)); idx += 1
    f[idx] = (hp.get('def_h', 1.0) - ap.get('def_a', 1.0)); idx += 1
    idx += 16
    
    # 3. FORM (30 features)
    hf = form_data.get(h, [])
    af = form_data.get(a, [])
    
    h_gf = sum(f['gf'] for f in hf[:5]) / max(len(hf[:5]), 1)
    h_ga = sum(f['ga'] for f in hf[:5]) / max(len(hf[:5]), 1)
    a_gf = sum(f['gf'] for f in af[:5]) / max(len(af[:5]), 1)
    a_ga = sum(f['ga'] for f in af[:5]) / max(len(af[:5]), 1)
    
    h_wins = sum(1 for f in hf[:5] if f['gf'] > f['ga'])
    a_wins = sum(1 for f in af[:5] if f['gf'] > f['ga'])
    
    f[idx] = h_gf; idx += 1
    f[idx] = h_ga; idx += 1
    f[idx] = a_gf; idx += 1
    f[idx] = a_ga; idx += 1
    f[idx] = h_gf - h_ga; idx += 1
    f[idx] = a_gf - a_ga; idx += 1
    f[idx] = h_wins / max(len(hf[:5]), 1); idx += 1
    f[idx] = a_wins / max(len(af[:5]), 1); idx += 1
    f[idx] = len(hf); idx += 1
    f[idx] = len(af); idx += 1
    f[idx] = h_gf - a_gf; idx += 1
    f[idx] = h_ga - a_ga; idx += 1
    f[idx] = h_wins - a_wins; idx += 1
    idx += 17
    
    # 4. H2H (30 features)
    h2h_key = (h, a)
    h2h_rec = h2h_data.get(h2h_key, {})
    h2h_rec_rev = h2h_data.get((a, h), {})
    
    total_h = h2h_rec.get('total', 0)
    total_a = h2h_rec_rev.get('total', 0)
    f[idx] = total_h + total_a; idx += 1  # total matches
    
    if total_h > 0:
        f[idx] = h2h_rec.get('hw', 0) / total_h; idx += 1
        f[idx] = h2h_rec.get('dr', 0) / total_h; idx += 1
        f[idx] = h2h_rec.get('aw', 0) / total_h; idx += 1
        f[idx] = h2h_rec.get('hg', 0) / max(1, h2h_rec.get('hw', 0) + h2h_rec.get('dr', 0) + h2h_rec.get('aw', 0)); idx += 1
        f[idx] = h2h_rec.get('ag', 0) / max(1, h2h_rec.get('hw', 0) + h2h_rec.get('dr', 0) + h2h_rec.get('aw', 0)); idx += 1
    else:
        idx += 5
    
    if total_a > 0:
        f[idx] = h2h_rec_rev.get('aw', 0) / total_a; idx += 1  # reverse: away wins as host
        f[idx] = h2h_rec_rev.get('dr', 0) / total_a; idx += 1
        f[idx] = h2h_rec_rev.get('hw', 0) / total_a; idx += 1
    else:
        idx += 3
    
    idx += 20
    
    # 5-8. DERIVED FEATURES
    # Poisson expected goals
    exp_h = hp.get('lam_h', 1.2) * (1 / max(ap.get('def_a', 1.0), 0.1))
    exp_a = ap.get('lam_a', 0.8) * (1 / max(hp.get('def_h', 1.0), 0.1))
    exp_h = max(min(exp_h, 4.0), 0.1)
    exp_a = max(min(exp_a, 3.0), 0.1)
    
    # Poisson probs
    def poisson_prob(lam, k):
        return math.exp(-lam) * (lam**k) / math.factorial(k)
    
    # Full score matrix
    for hg in range(6):
        for ag in range(6):
            if idx < 306:
                ph = poisson_prob(exp_h, hg)
                pa = poisson_prob(exp_a, ag)
                f[idx] = ph * pa
                idx += 1
    # 36 probs
    
    # Derived 1X2 from Poisson
    f36 = f[144:180].reshape(6, 6)[:5, :5]
    hw_p = sum(f36[h, a] for h in range(5) for a in range(5) if h > a)
    dr_p = sum(f36[i, i] for i in range(5))
    aw_p = sum(f36[h, a] for h in range(5) for a in range(5) if a > h)
    
    f[idx] = hw_p; idx += 1
    f[idx] = dr_p; idx += 1
    f[idx] = aw_p; idx += 1
    
    tg = [sum(f36[h, a] for h in range(5) for a in range(5) if h + a == g) for g in range(9)]
    f[idx] = sum(tg[1:]); idx += 1  # O0.5
    f[idx] = sum(tg[2:]); idx += 1  # O1.5
    f[idx] = sum(tg[3:]); idx += 1  # O2.5
    f[idx] = sum(tg[4:]); idx += 1  # O3.5
    f[idx] = sum(tg[5:]); idx += 1  # O4.5
    f[idx] = sum(tg[0:1]); idx += 1  # U0.5
    f[idx] = sum(tg[0:2]); idx += 1  # U1.5
    f[idx] = sum(tg[0:3]); idx += 1  # U2.5
    f[idx] = sum(tg[0:4]); idx += 1  # U3.5
    f[idx] = sum(tg[0:5]); idx += 1  # U4.5
    
    # BTTS
    btts_y = sum(f36[h, a] for h in range(1, 5) for a in range(1, 5))
    f[idx] = btts_y; idx += 1
    f[idx] = 1 - btts_y; idx += 1
    
    # DC
    f[idx] = hw_p + dr_p; idx += 1
    f[idx] = hw_p + aw_p; idx += 1
    f[idx] = dr_p + aw_p; idx += 1
    
    # Goal ranges
    f[idx] = sum(tg[0:2]); idx += 1
    f[idx] = sum(tg[2:4]); idx += 1
    f[idx] = sum(tg[4:6]); idx += 1
    f[idx] = sum(tg[6:]); idx += 1
    
    # Pad to 306
    while idx < 306:
        f[idx] = 0
        idx += 1
    
    return f

# Build X, y
X_list = []
y_list = []
leagues_used = 0
skipped = 0

for i, m in enumerate(matches):
    if i % 1000 == 0:
        print(f'  بناء {i}/{len(matches)}...', end='\r')
    
    features = build_features(m['home'], m['away'], m.get('league'))
    
    # Target: score index (0-0=0, 0-1=1, ..., 4-4=24)
    hg = min(m['h_goals'], 4)
    ag = min(m['a_goals'], 4)
    target_idx = hg * 5 + ag
    
    X_list.append(features)
    y_list.append(target_idx)

print(f'\n  ✅ بنينا {len(X_list)} نموذج ميزات!       ')

X = np.array(X_list)
y = np.array(y_list)

print(f'  X shape: {X.shape}, y shape: {y.shape}')
print(f'  عدد الفئات: {len(np.unique(y))}')
print(f'  توزيع النتائج:')
for sc in range(25):
    cnt = (y == sc).sum()
    if cnt > 0:
        h, a = divmod(sc, 5)
        print(f'    {h}-{a}: {cnt} ({cnt/len(y)*100:.1f}%)')

# Save training data
np.savez_compressed(
    os.path.join(OUT, 'training_data.npz'),
    X=X, y=y
)
print(f'\n💾 حفظ بيانات التدريب: {X.shape}')

print(f'\n{"="*70}')
print(f'✅ المرحلة 2 اكتملت! جاهز للتدريب')
print(f'   {len(X)} مباراة | 306 ميزة | 25 فئة')
print(f'{"="*70}')

conn.close()

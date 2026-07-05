#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ultimate Engine - المحرك الأسطوري النهائي للرهانات"""

import sqlite3, math, json, os, sys, pickle, time
import numpy as np
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, '..', 'output')
os.makedirs(OUT, exist_ok=True)

now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
print('='*70)
print('🦅🔥 المحرك الأسطوري النهائي للرهانات 🔥🦅')
print(f'   {now_str}')
print('='*70)

conn = sqlite3.connect(os.path.join(BASE, '..', 'scrape_cache.db'))
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ============ LOAD DATA ============
print('\n📥 [1/5] تحميل البيانات...')

print('   تحميل Elo...')
elo_map = {}
for row in c.execute('SELECT team_name, elo, rolling_xg_for, rolling_xg_against, form_points, matches_played FROM walkforward_state WHERE elo IS NOT NULL'):
    t = row['team_name']
    if t not in elo_map or (row['matches_played'] or 0) > elo_map[t].get('m', 0):
        elo_map[t] = {'e': row['elo'], 'xf': row['rolling_xg_for'] or 1.2, 'xa': row['rolling_xg_against'] or 1.2, 'f': row['form_points'] or 0.5, 'm': row['matches_played'] or 0}
print(f'   ✅ {len(elo_map)} فريق')

print('   تحميل Poisson...')
poisson_map = {}
for row in c.execute('SELECT team_name, attack_strength_home, attack_strength_away, defense_strength_home, defense_strength_away, lambda_home_scored, lambda_away_scored FROM neg_poisson_params'):
    poisson_map[row['team_name']] = {
        'ah': row['attack_strength_home'] or 1.0, 'aa': row['attack_strength_away'] or 1.0,
        'dh': row['defense_strength_home'] or 1.0, 'da': row['defense_strength_away'] or 1.0,
        'lh': row['lambda_home_scored'] or 1.2, 'la': row['lambda_away_scored'] or 0.8
    }
print(f'   ✅ {len(poisson_map)} فريق')

print('   تحميل H2H...')
h2h_map = {}
for row in c.execute('SELECT home_team, away_team, home_wins, draws, away_wins, home_goals_total, away_goals_total FROM neg_h2h_features'):
    h2h_map[(row['home_team'], row['away_team'])] = {
        'hw': row['home_wins'] or 0, 'dr': row['draws'] or 0, 'aw': row['away_wins'] or 0,
        'hg': row['home_goals_total'] or 0.0, 'ag': row['away_goals_total'] or 0.0
    }
print(f'   ✅ {len(h2h_map)} H2H')

print('   تحميل Glicko...')
glicko_map = {}
for row in c.execute('SELECT team_name, glicko_rating FROM glicko_state WHERE glicko_rating IS NOT NULL ORDER BY date DESC'):
    if row['team_name'] not in glicko_map:
        glicko_map[row['team_name']] = row['glicko_rating']
print(f'   ✅ {len(glicko_map)} فريق')

print('   تحميل Club Elo...')
clubelo_map = {}
for row in c.execute('SELECT team, elo FROM source_clubelo_enhanced WHERE elo IS NOT NULL ORDER BY match_date DESC'):
    if row['team'] not in clubelo_map:
        clubelo_map[row['team']] = row['elo']
print(f'   ✅ {len(clubelo_map)} فريق')

print('   تحميل دوريات...')
league_avg = {}
for row in c.execute('SELECT tournament, avg_home_goals, avg_away_goals, avg_total_goals, home_win_pct, draw_pct, away_win_pct FROM neg_league_averages'):
    league_avg[row['tournament']] = {
        'hg': row['avg_home_goals'] or 1.3, 'ag': row['avg_away_goals'] or 1.0,
        'tg': row['avg_total_goals'] or 2.3,
        'hw': row['home_win_pct'] or 0.42, 'dr': row['draw_pct'] or 0.28, 'aw': row['away_win_pct'] or 0.30
    }
print(f'   ✅ {len(league_avg)} دوري')

# ============ FEATURE BUILDER ============
print('\n🔨 [2/5] بناء الميزات...')

def get_best_elo(team):
    if team in clubelo_map: return clubelo_map[team]
    if team in glicko_map: return glicko_map[team] * 0.7 + 800
    if team in elo_map: return elo_map[team]['e']
    return 1500

def poisson_prob(lam, k):
    return math.exp(-lam) * (lam**k) / math.factorial(k)

def build_306(home_team, away_team, league=None):
    f = np.zeros(306)
    
    h_elo = get_best_elo(home_team)
    a_elo = get_best_elo(away_team)
    h_form = elo_map.get(home_team, {}).get('f', 0.5)
    a_form = elo_map.get(away_team, {}).get('f', 0.5)
    h_xgf = elo_map.get(home_team, {}).get('xf', 1.2)
    h_xga = elo_map.get(home_team, {}).get('xa', 1.2)
    a_xgf = elo_map.get(away_team, {}).get('xf', 1.2)
    a_xga = elo_map.get(away_team, {}).get('xa', 1.2)
    
    hp = poisson_map.get(home_team, {})
    ap = poisson_map.get(away_team, {})
    
    elo_diff = h_elo - a_elo
    form_diff = h_form - a_form
    lam_h = max(min(h_xgf / max(a_xga, 0.1), 3.0), 0.2)
    lam_a = max(min(a_xgf / max(h_xga, 0.1), 2.5), 0.2)
    
    h2h_key = (home_team, away_team)
    h2h = h2h_map.get(h2h_key, {})
    h2h_r = h2h_map.get((away_team, home_team), {})
    h2h_total = h2h.get('hw',0) + h2h.get('dr',0) + h2h.get('aw',0)
    
    idx = 0
    
    # 0-24: Basic Elo features
    f[idx] = h_elo; idx += 1
    f[idx] = a_elo; idx += 1
    f[idx] = elo_diff; idx += 1
    f[idx] = h_form; idx += 1
    f[idx] = a_form; idx += 1
    f[idx] = elo_map.get(home_team, {}).get('m', 0); idx += 1
    f[idx] = elo_map.get(away_team, {}).get('m', 0); idx += 1
    f[idx] = 0; idx += 1  # rest
    f[idx] = 0; idx += 1
    f[idx] = elo_diff * h_form; idx += 1
    f[idx] = -elo_diff * a_form; idx += 1
    f[idx] = h_xgf; idx += 1
    f[idx] = a_xgf; idx += 1
    f[idx] = h_form * h_xgf; idx += 1
    f[idx] = a_form * a_xgf; idx += 1
    f[idx] = elo_diff * form_diff; idx += 1
    f[idx] = h_elo - h_xgf * 100; idx += 1
    f[idx] = a_elo - a_xgf * 100; idx += 1
    f[idx] = h_form / max(a_form, 0.01); idx += 1
    f[idx] = elo_diff**2 / 500; idx += 1
    f[idx] = form_diff**2; idx += 1
    now = datetime.now()
    f[idx] = now.month; idx += 1
    f[idx] = now.weekday(); idx += 1
    f[idx] = 0.5; idx += 1  # season
    f[idx] = 0; idx += 1  # weekend
    
    # 25: travel
    try:
        c.execute('SELECT lat, lon FROM team_venue WHERE team_name = ? LIMIT 1', (home_team,))
        hv = c.fetchone()
        c.execute('SELECT lat, lon FROM team_venue WHERE team_name = ? LIMIT 1', (away_team,))
        av = c.fetchone()
        if hv and av:
            dlat = math.radians(float(av['lat']) - float(hv['lat']))
            dlon = math.radians(float(av['lon']) - float(hv['lon']))
            a_sin = math.sin(dlat/2)**2 + math.cos(math.radians(float(hv['lat']))) * math.cos(math.radians(float(av['lat']))) * math.sin(dlon/2)**2
            f[idx] = 6371 * 2 * math.asin(math.sqrt(a_sin))
    except: pass
    idx += 1
    
    # 26-50: Poisson score matrix (5x5)
    for hg in range(5):
        for ag in range(5):
            f[idx] = poisson_prob(lam_h, hg) * poisson_prob(lam_a, ag)
            idx += 1
    
    # 51-63: H2H
    f[idx] = h2h_total; idx += 1
    if h2h_total > 0:
        f[idx] = (h2h.get('hw',0)*3 + h2h.get('dr',0)) / (h2h_total * 3); idx += 1
        f[idx] = (h2h.get('aw',0)*3 + h2h.get('dr',0)) / (h2h_total * 3); idx += 1
        f[idx] = min(h2h_total / 10, 1.0); idx += 1
        f[idx] = h2h.get('hw',0) / h2h_total; idx += 1
        f[idx] = h2h.get('dr',0) / h2h_total; idx += 1
        f[idx] = h2h.get('aw',0) / h2h_total; idx += 1
    else:
        idx += 6
    f[idx] = (h2h.get('hg',0) - h2h.get('ag',0)) / max(h2h_total, 1); idx += 1
    f[idx] = (h2h.get('hg',0) + h2h.get('ag',0)) / max(h2h_total, 1); idx += 1
    idx += 5  # padding to complete 51-63
    
    # 64-94: Player impact, streaks, etc (use defaults)
    for i in range(31):
        f[idx] = 0
        idx += 1
    
    # 95-102: Statsbomb (none)
    idx += 8
    
    # 103-110: Glicko + team strength
    h_g = glicko_map.get(home_team, h_elo * 0.7 + 800)
    a_g = glicko_map.get(away_team, a_elo * 0.7 + 800)
    f[idx] = h_g; idx += 1
    f[idx] = a_g; idx += 1
    f[idx] = h_g - a_g; idx += 1
    f[idx] = 0; idx += 1
    f[idx] = 0; idx += 1
    f[idx] = h_elo - h_g; idx += 1
    f[idx] = a_elo - a_g; idx += 1
    f[idx] = elo_diff; idx += 1
    
    # 111-136: Polynomial features
    f[idx] = elo_diff**3 / 500000; idx += 1
    f[idx] = math.sqrt(abs(elo_diff)) * (1 if elo_diff > 0 else -1); idx += 1
    f[idx] = math.log(abs(elo_diff) + 1) * (1 if elo_diff > 0 else -1); idx += 1
    f[idx] = h_elo**2 / 1000; idx += 1
    f[idx] = a_elo**2 / 1000; idx += 1
    f[idx] = abs(elo_diff)**(1/3) * (1 if elo_diff > 0 else -1); idx += 1
    f[idx] = (h_form / max(a_form, 0.01))**2; idx += 1
    f[idx] = math.sqrt(h_form / max(a_form, 0.01)); idx += 1
    f[idx] = h_form**2; idx += 1
    f[idx] = a_form**2; idx += 1
    f[idx] = form_diff**3; idx += 1
    idx += 15  # padding
    
    # 137-208: Interactions (simplified)
    f[idx] = elo_diff * h_xgf; idx += 1
    f[idx] = -elo_diff * a_xgf; idx += 1
    f[idx] = elo_diff * h_form; idx += 1
    f[idx] = -elo_diff * a_form; idx += 1
    f[idx] = elo_diff; idx += 1
    f[idx] = -elo_diff; idx += 1
    idx += 66  # rest of interactions padded
    
    # 209-224: League context
    lavg = league_avg.get(league, {'hg': 1.3, 'ag': 1.0, 'tg': 2.3, 'hw': 0.42, 'dr': 0.28, 'aw': 0.30})
    f[idx] = lavg['hg']; idx += 1
    f[idx] = lavg['ag']; idx += 1
    f[idx] = lavg['tg']; idx += 1
    f[idx] = lavg['hw']; idx += 1
    f[idx] = lavg['dr']; idx += 1
    f[idx] = lavg['aw']; idx += 1
    f[idx] = 0.5; idx += 1
    f[idx] = lavg['hg']; idx += 1
    f[idx] = lavg['ag']; idx += 1
    idx += 7
    
    # 225-260: Season + team strength
    f[idx] = 20; idx += 1
    f[idx] = 1; idx += 1
    f[idx] = 0; idx += 1
    f[idx] = 30; idx += 1
    idx += 6
    f[idx] = h_form - a_form; idx += 1
    idx += 1
    f[idx] = hp.get('ah', 1.0) * 10; idx += 1
    f[idx] = h_form * 10; idx += 1
    f[idx] = (1 - h_form) * 5; idx += 1
    f[idx] = (1 - h_form) * 5; idx += 1
    f[idx] = h_xgf - h_xga; idx += 1
    f[idx] = ap.get('aa', 1.0) * 10; idx += 1
    f[idx] = a_form * 10; idx += 1
    f[idx] = (1 - a_form) * 5; idx += 1
    f[idx] = a_xgf - a_xga; idx += 1
    f[idx] = (h_elo - 1500) / 500; idx += 1
    f[idx] = h_xgf - h_xga; idx += 1
    
    f[idx] = ap.get('aa', 1.0) * 10; idx += 1
    f[idx] = a_form * 10; idx += 1
    f[idx] = (1 - a_form) * 5; idx += 1
    f[idx] = (1 - a_form) * 5; idx += 1
    f[idx] = a_xgf - a_xga; idx += 1
    f[idx] = a_form; idx += 1
    f[idx] = (a_elo - 1500) / 500; idx += 1
    f[idx] = a_xgf - a_xga; idx += 1
    f[idx] = (h_elo - a_elo) / 500; idx += 1
    
    # 261-270: Streaks
    f[idx] = 1 if h_form > 0.6 else -1 if h_form < 0.4 else 0; idx += 1
    f[idx] = 1 if a_form > 0.6 else -1 if a_form < 0.4 else 0; idx += 1
    f[idx] = abs(h_form - 0.5) * 10; idx += 1
    f[idx] = abs(a_form - 0.5) * 10; idx += 1
    f[idx] = h_form * 10; idx += 1
    f[idx] = a_form * 10; idx += 1
    f[idx] = (1 - h_form) * 10; idx += 1
    f[idx] = (1 - a_form) * 10; idx += 1
    f[idx] = h_form * 5; idx += 1
    f[idx] = a_form * 5; idx += 1
    
    # 271-276: Poisson derived metrics
    cs_h = poisson_prob(lam_a, 0)
    cs_a = poisson_prob(lam_h, 0)
    f[idx] = cs_h; idx += 1
    f[idx] = cs_a; idx += 1
    f[idx] = (1-cs_h)*(1-cs_a); idx += 1
    f[idx] = 1-(1-cs_h)*(1-cs_a); idx += 1
    f[idx] = 1-cs_h-cs_a+cs_h*cs_a; idx += 1
    o25 = 1 - sum(poisson_prob(lam_h, hg) * poisson_prob(lam_a, ag) for hg in range(3) for ag in range(3) if hg+ag <= 2)
    f[idx] = o25; idx += 1
    
    # 277-296: Normalized + interactions
    f[idx] = (elo_diff * h_form) / 500; idx += 1
    f[idx] = (-elo_diff * a_form) / 500; idx += 1
    f[idx] = (h_elo * h_form) / 1000; idx += 1
    f[idx] = (a_elo * a_form) / 1000; idx += 1
    idx += 16  # padding
    
    # Fill remaining
    while idx < 306:
        f[idx] = 0
        idx += 1
    
    return f

print('   ✅ جاهز!')

# ============ LOAD MODEL ============
print('\n📥 [3/5] تحميل Ultimate 306...')
import joblib
model_data = joblib.load(os.path.join(BASE, '..', 'models', 'ultimate_306_ensemble_dict.pkl'))
models_list = model_data['models']
weights = model_data['weights']
temp = model_data.get('temperature', 1.0)
print(f'   ✅ {len(models_list)} موديل | الوزن النشط: {weights}')
exact_val = model_data.get('exact', '?')
exact_str = str(exact_val)
print(f'   ✅ الدقة: {exact_str}%')

# ============ PREDICT FUNCTION ============
def predict_match(home_team, away_team, league=None):
    features = build_306(home_team, away_team, league)
    
    probs_list = []
    for i, m in enumerate(models_list):
        w = weights[i] if i < len(weights) else 0
        if w > 0 and hasattr(m, 'predict_proba'):
            try:
                p = m.predict_proba([features])[0]
                probs_list.append(p * w)
            except: pass
    
    if not probs_list:
        return None
    
    probs = np.sum(probs_list, axis=0)
    probs /= probs.sum()
    
    if temp != 1.0:
        probs = np.power(probs, 1/temp)
        probs /= probs.sum()
    
    scores = probs.reshape(5, 5)
    hw = float(sum(scores[h, a] for h in range(5) for a in range(5) if h > a))
    dr = float(sum(scores[i, i] for i in range(5)))
    aw = float(sum(scores[h, a] for h in range(5) for a in range(5) if a > h))
    
    exact = sorted([(f'{h}-{a}', float(scores[h, a])) for h in range(5) for a in range(5) if scores[h, a] > 0.005],
                   key=lambda x: -x[1])[:5]
    
    tg = [float(sum(scores[h, a] for h in range(5) for a in range(5) if h + a == g)) for g in range(9)]
    btts_y = float(sum(scores[h, a] for h in range(1, 5) for a in range(1, 5)))
    
    return {
        'home': home_team, 'away': away_team, 'league': league or '?',
        'predicted_score': exact[0][0] if exact else '?-?',
        'predicted_prob': exact[0][1] if exact else 0,
        '1x2': {'H': hw, 'D': dr, 'A': aw},
        'exact': [{'s': s[0], 'p': s[1]} for s in exact],
        'ou': {'O2.5': sum(tg[3:]), 'U2.5': sum(tg[:3])},
        'btts': {'Y': btts_y, 'N': 1 - btts_y},
        'dc': {'1X': hw + dr, '12': hw + aw, '2X': dr + aw},
    }

def get_bets(result, min_conf=0.55):
    bets = []
    if result['1x2']['H'] > min_conf:
        bets.append({'type': f'🏠 {result["home"]} يفوز', 'prob': result['1x2']['H']})
    if result['1x2']['A'] > min_conf:
        bets.append({'type': f'✈️ {result["away"]} يفوز', 'prob': result['1x2']['A']})
    if result['ou']['U2.5'] > 0.65:
        bets.append({'type': '📉 تحت 2.5', 'prob': result['ou']['U2.5']})
    if result['ou']['O2.5'] > 0.60:
        bets.append({'type': '📈 فوق 2.5', 'prob': result['ou']['O2.5']})
    if result['btts']['N'] > 0.65:
        bets.append({'type': '🚫 BTTS No', 'prob': result['btts']['N']})
    if result['btts']['Y'] > 0.55:
        bets.append({'type': '✅ BTTS Yes', 'prob': result['btts']['Y']})
    if result['dc']['12'] > 0.85:
        bets.append({'type': '🔄 DC 12', 'prob': result['dc']['12']})
    bets.sort(key=lambda x: -x['prob'])
    return bets

# ============ ANALYZE ALL MATCHES ============
print('\n🔥 [4/5] تحليل المباريات...\n')

matches = [
    ('IK Sirius FK', 'Mjällby AIF', 'Allsvenskan'),
    ('Maardu', 'Tallinna Kalev', 'Esiliiga'),
    ('KI Klaksvik', 'NSI Runavik', 'Premier League'),
    ('Egypt', 'Australia', 'World Championship'),
    ('Argentina', 'Cabo Verde', 'World Championship'),
]

all_results = []
for home, away, league in matches:
    t0 = time.time()
    result = predict_match(home, away, league)
    elapsed = time.time() - t0
    
    if not result:
        print(f'❌ {home} vs {away} → فشل')
        continue
    
    bets = get_bets(result)
    all_results.append({'result': result, 'bets': bets})
    
    print(f'{"="*65}')
    print(f'🎯 {result["home"]} vs {result["away"]}')
    print(f'   🥅 {result["predicted_score"]} ({result["predicted_prob"]*100:.1f}%) | ⏱ {elapsed:.2f}s')
    print(f'   🇪🇪 1X2: {result["1x2"]["H"]*100:.0f}% / {result["1x2"]["D"]*100:.0f}% / {result["1x2"]["A"]*100:.0f}%')
    print(f'   📈 O/U: {result["ou"]["O2.5"]*100:.0f}% / {result["ou"]["U2.5"]*100:.0f}%')
    print(f'   ⚔️ BTTS: {result["btts"]["Y"]*100:.0f}% / {result["btts"]["N"]*100:.0f}%')
    print(f'   🔄 DC: {result["dc"]["12"]*100:.0f}%')
    if bets:
        for b in bets[:4]:
            print(f'   💰 {b["type"]} ({b["prob"]*100:.0f}%)')

# ============ ACCUMULATOR REPORT ============
print(f'\n{"="*65}')
print('🔥🔥🔥 الرهان التراكمي 🔥🔥🔥')
print(f'{"="*65}')

best_accs = []
for size in [2, 3]:
    top_matches = sorted(all_results, key=lambda x: x['bets'][0]['prob'] if x['bets'] else 0, reverse=True)
    for i in range(max(1, len(top_matches) - size + 1)):
        combo = top_matches[i:i+size]
        if len(combo) < size:
            continue
        bets_list = [m['bets'][0] for m in combo if m['bets']]
        if len(bets_list) < size:
            continue
        acc_prob = 1.0
        for b in bets_list:
            acc_prob *= b['prob']
        best_accs.append({'matches': combo, 'bets': bets_list, 'prob': acc_prob, 'size': size})

best_accs.sort(key=lambda x: x['prob'], reverse=True)

for acc in best_accs[:4]:
    tag = '🔥🔥' if acc['prob'] > 0.30 else '✅' if acc['prob'] > 0.15 else '⚠️'
    mult = 1/acc['prob'] if acc['prob'] > 0 else 0
    print(f'\n{tag} {acc["size"]} مباريات | احتمال: {acc["prob"]*100:.1f}% | مضاعف: {mult:.1f}x')
    for j, (m, b) in enumerate(zip(acc['matches'], acc['bets'])):
        r = m['result']
        print(f'   {j+1}. {r["home"]} vs {r["away"]} → {b["type"]}')
    payout = 25 * mult
    print(f'   💰 25 DH × {mult:.1f} = {payout:.0f} DH')

# Save
report = {
    'generated_at': now_str,
    'matches': [{
        'match': f"{r['result']['home']} vs {r['result']['away']}",
        'predicted_score': r['result']['predicted_score'],
        '1x2': r['result']['1x2'],
        'ou': r['result']['ou'],
        'btts': r['result']['btts'],
        'best_bets': [{'type': b['type'], 'confidence': f"{b['prob']*100:.0f}%"} for b in r['bets'][:3]]
    } for r in all_results],
    'accumulators': [{
        'size': a['size'], 'probability': f"{a['prob']*100:.1f}%",
        'payout': f"{25 * 1/max(a['prob'],0.001):.0f} DH",
        'matches': [f"{m['result']['home']} vs {m['result']['away']} -> {b['type']}" for m, b in zip(a['matches'], a['bets'])]
    } for a in best_accs[:4]]
}

with open(os.path.join(OUT, 'ultimate_report.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f'\n💾 {os.path.join(OUT, "ultimate_report.json")}')
print(f'\n{"="*70}')
print('✅✅✅ المحرك الأسطوري جاهز!')
print(f'   {len(all_results)} مباراة | {len(best_accs)} تراكمي')
print(f'{"="*70}')

conn.close()

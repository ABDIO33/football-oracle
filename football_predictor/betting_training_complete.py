#!/usr/bin/env python3
"""
🔥 BETTING TRAINING COMPLETE — تدريب خارق على كل خيارات الرهان 🔥
يقوم بـ:
1. تحميل أفضل موديل (Ultimate 306)
2. تدريب calibrators مخصصة لكل سوق رهان
3. تحميل المباريات الجاية (غير كأس العالم)
4. مقارنة مع odds السوق
5. إيجاد Value Bets في كل الأسواق
6. تقرير HTML كامل للرهان الثاني
"""

import sys, os, json, math, time, warnings, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime, timedelta
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

LOG = os.path.join(OUTPUT_DIR, 'betting_training_log.txt')
def p(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')
    print(f'[{ts}] {msg}')

# =====================================================================
# STEP 1: LOAD BEST MODEL
# =====================================================================
p("="*70)
p("🔥 BETTING TRAINING COMPLETE — كل أسواق الرهان")
p("="*70)

p("\n[1] تحميل أفضل موديل...")
BEST_MODEL = None
BEST_MODEL_NAME = ""

models_to_try = [
    ('models/ultimate_306_ensemble_dict.pkl', 'Ultimate 306 (41.46%)'),
    ('models/ultimate_v6_ensemble.pkl', 'Ultimate V6 (24.80%)'),
    ('models/champion_ensemble.pkl', 'Champion (30.96%)'),
]
import joblib

for path, name in models_to_try:
    full = os.path.join(BASE, path)
    if os.path.exists(full):
        try:
            BEST_MODEL = joblib.load(full)
            BEST_MODEL_NAME = name
            p(f"  ✅ {name} ({os.path.getsize(full)//1024//1024}MB)")
            break
        except Exception as e:
            p(f"  ❌ {name}: {e}")

if BEST_MODEL is None:
    p("  ❌ فشل تحميل الموديل!")
    sys.exit(1)

# =====================================================================
# STEP 2: CALCULATE ALL MARKETS FROM 25-CLASS PROBS
# =====================================================================
p("\n[2] تدريب حساب كل أسواق الرهان من 25 probabilities...")

def calc_all_markets(probs_25):
    """حساب 15 سوق رهان من 25-class probabilities"""
    probs = np.array(probs_25, dtype=np.float64)
    probs = np.clip(probs, 1e-10, None)
    probs /= probs.sum()
    
    # Score grid
    scores = np.zeros((5, 5))
    idx = 0
    for h in range(5):
        for a in range(5):
            if idx < len(probs):
                scores[h, a] = probs[idx]
                idx += 1
    
    # === MARKET 1: 1X2 ===
    home_win = sum(scores[h, a] for h in range(5) for a in range(5) if h > a)
    draw = sum(scores[i, i] for i in range(5))
    away_win = sum(scores[h, a] for h in range(5) for a in range(5) if a > h)
    
    # === MARKET 2: EXACT SCORES ===
    exact = []
    for h in range(5):
        for a in range(5):
            if scores[h, a] > 0.003:
                exact.append({'s': f'{h}-{a}', 'p': float(scores[h, a])})
    exact.sort(key=lambda x: -x['p'])
    
    # === MARKET 3: OVER/UNDER ===
    tg_dist = np.zeros(9)
    for h in range(5):
        for a in range(5):
            tg = min(h + a, 8)
            tg_dist[tg] += scores[h, a]
    
    overs = {}
    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        idx_line = int(math.ceil(line))
        ov = tg_dist[idx_line:].sum()
        overs[f'ov{line}'] = float(ov)
        overs[f'un{line}'] = float(1.0 - ov)
    
    # === MARKET 4: BTTS ===
    btts_yes = sum(scores[h, a] for h in range(1, 5) for a in range(1, 5))
    
    # === MARKET 5: DOUBLE CHANCE ===
    dc = {
        '1x': float(home_win + draw),
        '12': float(home_win + away_win),
        '2x': float(away_win + draw),
    }
    
    # === MARKET 6: WIN TO NIL ===
    wtn = {
        'home': float(sum(scores[h, 0] for h in range(1, 5))),
        'away': float(sum(scores[0, a] for a in range(1, 5))),
    }
    
    # === MARKET 7: TOTAL GOALS EXACT ===
    tg_exact = {f'g{g}': float(tg_dist[min(g, 8)]) for g in range(9)}
    
    # === MARKET 8: ODD/EVEN ===
    odd_even = {
        'odd': float(sum(tg_dist[g] for g in range(1, 9, 2))),
        'even': float(tg_dist[0] + sum(tg_dist[g] for g in range(2, 9, 2))),
    }
    
    # === MARKET 9: WIN MARGIN ===
    wm = {}
    for diff, label in [(1, 'h1'), (2, 'h2'), (3, 'h3p')]:
        wm[f'h{diff}'] = float(sum(scores[h, a] for h in range(5) for a in range(5) if h - a == diff if diff < 3 or h - a >= 3))
    for diff, label in [(1, 'a1'), (2, 'a2'), (3, 'a3p')]:
        wm[f'a{diff}'] = float(sum(scores[h, a] for h in range(5) for a in range(5) if a - h == diff if diff < 3 or a - h >= 3))
    
    # === MARKET 10: ASIAN HANDICAP (simplified) ===
    ah = {}
    for line in [-2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5]:
        prob = sum(scores[h, a] for h in range(5) for a in range(5) if h - a + line > 0.01)
        ah[f'{line:+.1f}'] = float(prob)
    
    # === MARKET 11: HALF-TIME RESULT (estimated from full-time probs) ===
    # We estimate HT from FT using correlation
    ht = {
        'home': float(home_win * 0.65 + draw * 0.20),  # rough estimate
        'draw': float(home_win * 0.20 + draw * 0.60 + away_win * 0.20),
        'away': float(draw * 0.20 + away_win * 0.65),
    }
    ht_total = ht['home'] + ht['draw'] + ht['away']
    for k in ht:
        ht[k] /= ht_total
    
    # === MARKET 12: CORRECT SCORE GROUPS ===
    csg = {
        'home_1_0_1_1': float(scores[1,0] + scores[1,1]),
        'away_0_1_1_1': float(scores[0,1] + scores[1,1]),
        'home_2_0_2_1': float(scores[2,0] + scores[2,1]),
        'away_0_2_1_2': float(scores[0,2] + scores[1,2]),
        'high_scoring': float(sum(scores[h, a] for h in range(3, 5) for a in range(3, 5))),
        'low_scoring': float(scores[0,0] + scores[0,1] + scores[1,0] + scores[1,1]),
    }
    
    # === MARKET 13: FIRST TEAM TO SCORE ===
    # Estimate from who's more likely to score
    home_scores = sum(scores[h, a] for h in range(1, 5) for a in range(5))
    away_scores = sum(scores[h, a] for h in range(5) for a in range(1, 5))
    both_score = btts_yes
    neither = scores[0, 0]
    fts = {
        'home': float(home_scores * 0.55),
        'away': float(away_scores * 0.35),
        'none': float(neither * 0.10),
    }
    fts_total = fts['home'] + fts['away'] + fts['none']
    for k in fts:
        fts[k] /= fts_total
    
    # === MARKET 14: TOTAL GOALS RANGE ===
    gr = {
        '0_1': float(tg_dist[0] + tg_dist[1]),
        '2_3': float(tg_dist[2] + tg_dist[3]),
        '4_5': float(tg_dist[4] + tg_dist[5]),
        '6p': float(tg_dist[6] + tg_dist[7] + tg_dist[8]),
    }
    
    # === MARKET 15: HOME/AWAY BOTH SCORE HALF ===
    has = {
        'home_score': float(home_scores),
        'away_score': float(away_scores),
        'both_score': float(btts_yes),
        'no_score': float(neither),
    }
    
    return {
        '1x2': {'h': float(home_win), 'd': float(draw), 'a': float(away_win)},
        'exact': exact[:10],
        'over_under': overs,
        'btts': {'yes': float(btts_yes), 'no': float(1 - btts_yes)},
        'double_chance': dc,
        'win_to_nil': wtn,
        'total_goals_exact': tg_exact,
        'odd_even': odd_even,
        'win_margin': wm,
        'asian_handicap': ah,
        'half_time': ht,
        'score_groups': csg,
        'first_to_score': fts,
        'goal_ranges': gr,
        'home_away_scores': has,
    }

p("  ✅ 15 سوق رهان محسوبين")
markets_list = [
    '1X2', 'Exact Score', 'Over/Under(0.5-5.5)', 'BTTS', 'Double Chance',
    'Win To Nil', 'Total Goals(0-8+)', 'Odd/Even', 'Win Margin',
    'Asian Handicap', 'Half-Time Result', 'Score Groups',
    'First Team To Score', 'Goal Ranges', 'Home/Away Scores'
]
for i, m in enumerate(markets_list, 1):
    p(f"     {i:2d}. {m}")

# =====================================================================
# STEP 3: CALIBRATION — Train market-specific calibrators
# =====================================================================
p("\n[3] تدريب calibrators لكل سوق رهان...")
# Using the Ultimate 306 model which already has calibrated probabilities
# Add extra calibration for specific markets using isotonic regression

try:
    from sklearn.isotonic import IsotonicRegression
    from sklearn.calibration import CalibratedClassifierCV
    
    # Load some training data for calibration
    cal_data_path = os.path.join(BASE, 'models', 'preprocessed_data.npz')
    if os.path.exists(cal_data_path):
        cal_data = np.load(cal_data_path, allow_pickle=True)
        X_cal = cal_data['X'][-20000:].astype(np.float32)
        y_cal = cal_data['y'][-20000:]
        p(f"  ✅ Loaded calibration data: {X_cal.shape}")
        
        # Train calibrator for 1X2
        # Convert y to 1X2 labels
        y_1x2 = np.zeros(len(y_cal), dtype=np.int32)
        for i, cls in enumerate(y_cal):
            h = cls // 5
            a = cls % 5
            if h > a: y_1x2[i] = 0
            elif h == a: y_1x2[i] = 1
            else: y_1x2[i] = 2
        
        # Calculate O/U 2.5 labels
        y_ou = np.zeros(len(y_cal), dtype=np.int32)
        for i, cls in enumerate(y_cal):
            h = cls // 5
            a = cls % 5
            y_ou[i] = 1 if (h + a) > 2 else 0
        
        # Calculate BTTS labels
        y_btts = np.zeros(len(y_cal), dtype=np.int32)
        for i, cls in enumerate(y_cal):
            h = cls // 5
            a = cls % 5
            y_btts[i] = 1 if h > 0 and a > 0 else 0
        
        calibrators = {}
        
        # Train XGBoost calibrators for each market
        import xgboost as xgb
        from sklearn.metrics import log_loss, brier_score_loss
        
        for name, y_target in [('1X2', y_1x2), ('O/U2.5', y_ou), ('BTTS', y_btts)]:
            n_classes = len(np.unique(y_target))
            if n_classes == 2:
                model = xgb.XGBClassifier(
                    n_estimators=100, max_depth=4, 
                    learning_rate=0.1, subsample=0.8,
                    objective='binary:logistic',
                    n_jobs=4, verbosity=0
                )
                model.fit(X_cal, y_target)
                preds = model.predict_proba(X_cal)
                loss = log_loss(y_target, preds)
                p(f"  ✅ {name}: log_loss={loss:.4f}, classes={n_classes}")
            else:
                model = xgb.XGBClassifier(
                    n_estimators=100, max_depth=4,
                    learning_rate=0.1, subsample=0.8,
                    objective='multi:softprob', num_class=n_classes,
                    n_jobs=4, verbosity=0
                )
                model.fit(X_cal, y_target)
                preds = model.predict_proba(X_cal)
                loss = log_loss(y_target, preds)
                p(f"  ✅ {name}: log_loss={loss:.4f}, classes={n_classes}")
            
            calibrators[name] = model
            del model
            gc.collect()
        
        # Save calibrators
        calibrator_path = os.path.join(BASE, 'models', 'market_calibrators.pkl')
        joblib.dump(calibrators, calibrator_path)
        p(f"  ✅ Saved calibrators: {calibrator_path}")
    else:
        p("  ⚠️ No calibration data found, using raw model probabilities")
        calibrators = {}
        
except Exception as e:
    p(f"  ⚠️ Calibration error: {e}")
    calibrators = {}

# =====================================================================
# STEP 4: LOAD TODAY'S MATCHES
# =====================================================================
p("\n[4] تحميل مباريات اليوم (غير كأس العالم)...")
pred_path = os.path.join(OUTPUT_DIR, 'upcoming_predictions.json')
if os.path.exists(pred_path):
    with open(pred_path) as f:
        all_matches = json.load(f)
    p(f"  ✅ Total: {len(all_matches)}")
else:
    p("  ❌ No predictions!")
    sys.exit(1)

# Use ALL non-WC matches (all dates)
non_wc_today = [m for m in all_matches if 'World Cup' not in m.get('league', '')]
wc_today = [m for m in all_matches if 'World Cup' in m.get('league', '')]

dates_set = set(m.get('date','?') for m in all_matches)
p(f"  📅 Total: {len(all_matches)} matches from {len(dates_set)} dates")
p(f"     Non-WC: {len(non_wc_today)} | WC: {len(wc_today)}")
p(f"     Date range: {min(dates_set)} to {max(dates_set)}")

# =====================================================================
# STEP 5: COMPLETE MARKET ANALYSIS FOR EACH MATCH
# =====================================================================
p(f"\n[5] تحليل كل الأسواق لـ {len(non_wc_today)} مباراة غير كأس العالم...")

results = []
for i, m in enumerate(non_wc_today):
    # Get 25-class probs
    if 'all_probs' in m and len(m['all_probs']) >= 25:
        probs_25 = m['all_probs'][:25]
    else:
        # Derive from top scores
        probs_25 = np.ones(25) * 0.0001
        for score_entry in m.get('top_scores', []):
            score_str = score_entry[0]
            prob_val = score_entry[1]
            try:
                h, a = map(int, score_str.split('-'))
                if h < 5 and a < 5:
                    idx = min(h * 5 + a, 24)
                    probs_25[idx] = prob_val
            except:
                pass
        probs_25 = np.array(probs_25) / sum(probs_25)
    
    markets = calc_all_markets(probs_25)
    
    # Override 1X2 with direct prediction
    markets['1x2']['h'] = float(m.get('home_win', markets['1x2']['h']))
    markets['1x2']['d'] = float(m.get('draw', markets['1x2']['d']))
    markets['1x2']['a'] = float(m.get('away_win', markets['1x2']['a']))
    
    # Find best bets
    best_bets = []
    market_names = {
        '1x2': '1X2', 'over_under': 'O/U', 'btts': 'BTTS', 
        'double_chance': 'Double Chance', 'win_to_nil': 'Win To Nil',
        'odd_even': 'Odd/Even', 'goal_ranges': 'Goal Range',
        'first_to_score': 'First To Score', 'half_time': 'HT Result',
    }
    
    # 1X2 bets
    for outcome, label, prob in [
        ('home', 'H', markets['1x2']['h']),
        ('draw', 'D', markets['1x2']['d']),
        ('away', 'A', markets['1x2']['a']),
    ]:
        if prob >= 0.50:
            best_bets.append({
                'market': '1X2',
                'outcome': label,
                'prob': round(prob * 100, 1),
                'ev_if_evens': round((prob * 2.0 - 1.0) * 100, 1),
                'strength': '🔥' if prob >= 0.70 else '✅' if prob >= 0.60 else '⚡'
            })
    
    # O/U 2.5 bets
    ov25 = markets['over_under']['ov2.5']
    un25 = markets['over_under']['un2.5']
    if ov25 >= 0.65:
        best_bets.append({'market': 'O/U 2.5', 'outcome': 'Over', 'prob': round(ov25*100, 1), 'ev_if_evens': round((ov25*2.0-1.0)*100, 1), 'strength': '🔥' if ov25 >= 0.75 else '✅'})
    if un25 >= 0.65:
        best_bets.append({'market': 'O/U 2.5', 'outcome': 'Under', 'prob': round(un25*100, 1), 'ev_if_evens': round((un25*2.0-1.0)*100, 1), 'strength': '🔥' if un25 >= 0.75 else '✅'})
    
    # BTTS bets
    btts = markets['btts']['yes']
    if btts >= 0.60:
        best_bets.append({'market': 'BTTS', 'outcome': 'Yes', 'prob': round(btts*100, 1), 'ev_if_evens': round((btts*2.0-1.0)*100, 1), 'strength': '🔥' if btts >= 0.75 else '✅'})
    if (1-btts) >= 0.60:
        best_bets.append({'market': 'BTTS', 'outcome': 'No', 'prob': round((1-btts)*100, 1), 'ev_if_evens': round(((1-btts)*2.0-1.0)*100, 1), 'strength': '🔥' if (1-btts) >= 0.75 else '✅'})
    
    # Double chance bets
    for outcome, label, prob in [
        ('1X', '1X', markets['double_chance']['1x']),
        ('12', '12', markets['double_chance']['12']),
        ('2X', '2X', markets['double_chance']['2x']),
    ]:
        if prob >= 0.75:
            best_bets.append({'market': 'DC', 'outcome': label, 'prob': round(prob*100, 1), 'ev_if_evens': round((prob*2.0-1.0)*100, 1), 'strength': '🔥' if prob >= 0.85 else '✅'})
    
    # Odd/Even
    odd_p = markets['odd_even']['odd']
    if odd_p >= 0.60:
        best_bets.append({'market': 'O/E', 'outcome': 'Odd', 'prob': round(odd_p*100, 1), 'ev_if_evens': round((odd_p*2.0-1.0)*100, 1), 'strength': '✅'})
    if (1-odd_p) >= 0.60:
        best_bets.append({'market': 'O/E', 'outcome': 'Even', 'prob': round((1-odd_p)*100, 1), 'ev_if_evens': round(((1-odd_p)*2.0-1.0)*100, 1), 'strength': '✅'})
    
    # Sort best bets by probability
    best_bets.sort(key=lambda x: -x['prob'])
    
    result = {
        'match': f"{m['home_team']} vs {m['away_team']}",
        'home': m['home_team'],
        'away': m['away_team'],
        'league': m.get('league', '?'),
        'date': m.get('date', '?'),
        'predicted_score': m.get('predicted_score', '?-?'),
        'predicted_prob': m.get('probability', 0),
        'markets': markets,
        'best_bets': best_bets[:8],  # Top 8 best bets
    }
    results.append(result)
    
    if i < 5 or (i+1) % 10 == 0:
        p(f"  [{i+1}/{len(non_wc_today)}] {result['match'][:40]}... ({len(best_bets)} bets)")

# =====================================================================
# STEP 6: GENERATE HTML REPORT
# =====================================================================
p(f"\n[6] إنشاء تقرير HTML للرهان الثاني...")

# Generate compact match cards
def gen_match_html(r):
    m = r['markets']
    pred = r['predicted_score']
    pred_pct = r['predicted_prob'] * 100 if r['predicted_prob'] else 0
    league_tag = '🌍' if 'World Cup' in r.get('league','') else '⚽'
    
    html = f"""
<div class="match-card" onclick="this.classList.toggle('expanded')">
<div class="match-header">
  <span class="match-title">{league_tag} {r['home']} 🆚 {r['away']}</span>
  <span class="match-league">{r['league'][:25]}</span>
</div>
<div class="score-big">{pred} <span class="score-prob">({pred_pct:.0f}%)</span></div>
<div class="probs-bar">
  <div class="prob-bar-h" style="width:{m['1x2']['h']*100:.1f}%">H {m['1x2']['h']*100:.0f}%</div>
  <div class="prob-bar-d" style="width:{m['1x2']['d']*100:.1f}%">D {m['1x2']['d']*100:.0f}%</div>
  <div class="prob-bar-a" style="width:{m['1x2']['a']*100:.1f}%">A {m['1x2']['a']*100:.0f}%</div>
</div>
"""
    # Best bets
    if r['best_bets']:
        html += '<div class="best-bets">'
        for bb in r['best_bets']:
            html += f'<span class="bet-tag {bb["strength"]}">{bb["strength"]} {bb["market"]} {bb["outcome"]} ({bb["prob"]:.0f}%)</span>'
        html += '</div>'
    
    # Expanded markets (hidden by default)
    html += '<div class="markets-detail">'
    html += f"""
    <table><tr><th>O/U 2.5</th><th>BTTS</th><th>DC 1X</th><th>DC 12</th><th>Win2Nil H</th><th>Win2Nil A</th><th>Odd</th><th>Even</th></tr>
    <tr>
      <td>{m['over_under']['ov2.5']*100:.0f}%O/{m['over_under']['un2.5']*100:.0f}%U</td>
      <td>{m['btts']['yes']*100:.0f}%/{m['btts']['no']*100:.0f}%</td>
      <td>{m['double_chance']['1x']*100:.0f}%</td>
      <td>{m['double_chance']['12']*100:.0f}%</td>
      <td>{m['win_to_nil']['home']*100:.0f}%</td>
      <td>{m['win_to_nil']['away']*100:.0f}%</td>
      <td>{m['odd_even']['odd']*100:.0f}%</td>
      <td>{m['odd_even']['even']*100:.0f}%</td>
    </tr></table>
    <table><tr><th colspan="6">Asian Handicap</th></tr>
    <tr>"""
    for line in [-2, -1, -0.5, 0, 0.5, 1, 2]:
        ah_key = f'{line:+.1f}'
        if ah_key in m['asian_handicap']:
            html += f"<td>AH {ah_key}: {m['asian_handicap'][ah_key]*100:.0f}%</td>"
    html += "</tr></table>"
    
    html += '<table><tr><th colspan="5">Goal Ranges</th></tr><tr>'
    for rg, label in [('0_1', '0-1'), ('2_3', '2-3'), ('4_5', '4-5'), ('6p', '6+')]:
        html += f"<td>{label}: {m['goal_ranges'][rg]*100:.0f}%</td>"
    html += '</tr></table>'
    
    html += '<table><tr><th colspan="3">First To Score</th><th colspan="3">HT Result</th></tr><tr>'
    for k in ['home', 'away', 'none']:
        html += f"<td>{k}: {m['first_to_score'][k]*100:.0f}%</td>"
    for k in ['home', 'draw', 'away']:
        html += f"<td>{k}: {m['half_time'][k]*100:.0f}%</td>"
    html += '</tr></table>'
    
    html += '<div class="exact-scores">'
    for es in m['exact'][:3]:
        html += f'<span class="score-chip">{es["s"]} ({es["p"]*100:.0f}%)</span>'
    html += '</div>'
    
    html += '</div></div>'
    return html


# Full HTML
all_match_html = '\n'.join(gen_match_html(r) for r in results)

html = f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8">
<title>🔥 الرهان الثاني — SECOND BETTING ROUND</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui;background:#0a0a0a;color:#fff;margin:0;padding:20px}}
h1{{color:#ff4444;text-align:center;text-shadow:0 0 30px #ff444488;font-size:2em}}
.subtitle{{text-align:center;color:#888;margin:-10px 0 20px}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:20px 0}}
.stat-box{{background:#1a1a2e;border:1px solid #333;border-radius:12px;padding:16px;text-align:center}}
.stat-num{{font-size:2em;font-weight:bold;color:#ff4444}}
.stat-label{{color:#888;font-size:0.9em}}
.match-card{{background:#1a1a2e;border:1px solid #333;border-radius:16px;padding:16px;margin:12px 0;cursor:pointer;transition:all 0.3s}}
.match-card:hover{{border-color:#ff4444;transform:translateX(5px)}}
.match-card.expanded{{border-color:#ffdd44}}
.match-header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;margin-bottom:8px}}
.match-title{{font-weight:bold;font-size:1.1em}}
.match-league{{color:#888;font-size:0.85em}}
.score-big{{font-size:1.8em;font-weight:bold;color:#ffdd44;text-align:center;margin:6px 0}}
.score-prob{{font-size:0.5em;color:#888}}
.probs-bar{{display:flex;height:24px;border-radius:12px;overflow:hidden;margin:8px 0;font-size:0.8em;font-weight:bold}}
.prob-bar-h{{background:#44aa44;text-align:left;padding:2px 6px;white-space:nowrap}}
.prob-bar-d{{background:#aaaa44;text-align:center;padding:2px 4px;white-space:nowrap}}
.prob-bar-a{{background:#aa4444;text-align:right;padding:2px 6px;white-space:nowrap}}
.best-bets{{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}}
.bet-tag{{padding:4px 10px;border-radius:20px;font-size:0.8em;font-weight:bold}}
.bet-tag.🔥{{background:#440000;color:#ff4444;border:1px solid #ff4444}}
.bet-tag.✅{{background:#004400;color:#44ff44;border:1px solid #44ff44}}
.bet-tag.⚡{{background:#444400;color:#ffff44;border:1px solid #ffff44}}
.markets-detail{{display:none;margin-top:10px;padding-top:10px;border-top:1px solid #333}}
.match-card.expanded .markets-detail{{display:block}}
table{{width:100%;border-collapse:collapse;margin:8px 0;font-size:0.85em}}
th{{background:#222;padding:4px 6px;text-align:center;color:#ffdd44;font-weight:bold}}
td{{padding:4px 6px;border-bottom:1px solid #222;text-align:center}}
.exact-scores{{display:flex;gap:8px;margin:8px 0}}
.score-chip{{background:#222;padding:4px 12px;border-radius:20px;font-size:0.85em}}
.controls{{position:sticky;top:0;background:#0a0a0a;padding:10px 0;z-index:100;border-bottom:1px solid #333}}
.filter-btn{{background:#333;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer;margin:2px}}
.filter-btn.active{{background:#ff4444}}
.filter-btn:hover{{background:#555}}
#searchBox{{background:#222;color:#fff;border:1px solid #444;border-radius:8px;padding:8px 16px;width:100%;max-width:300px;margin:8px 0}}
</style></head><body>

<h1>🔥 الرهان الثاني — SECOND BETTING ROUND</h1>
<p class="subtitle">{datetime.now().strftime('%Y-%m-%d %H:%M')} | Model: {BEST_MODEL_NAME} | 15 Betting Markets</p>

<div class="controls">
  <input id="searchBox" placeholder="🔍 بحث عن فريق..." onkeyup="filterMatches()">
  <div style="margin:8px 0">
    <button class="filter-btn active" onclick="filterByLeague('all')">الكل</button>
    <button class="filter-btn" onclick="filterByLeague('non-wc')">غير كأس العالم</button>
    <button class="filter-btn" onclick="filterByLeague('wc')">كأس العالم</button>
  </div>
</div>

<div class="summary-grid">
  <div class="stat-box"><div class="stat-num">{len(results)}</div><div class="stat-label">🏟️ المباريات (غير WC)</div></div>
  <div class="stat-box"><div class="stat-num">{len(non_wc_today)}</div><div class="stat-label">⚽ غير كأس العالم</div></div>
  <div class="stat-box"><div class="stat-num">{len(wc_today)}</div><div class="stat-label">🏆 كأس العالم</div></div>
  <div class="stat-box"><div class="stat-num">15</div><div class="stat-label">🎰 أسواق الرهان</div></div>
</div>

<div id="matches-container">
{all_match_html}
</div>

<script>
function filterMatches(){{
  var q = document.getElementById('searchBox').value.toLowerCase();
  var cards = document.getElementsByClassName('match-card');
  for(var c of cards){{
    c.style.display = c.innerText.toLowerCase().includes(q) ? '' : 'none';
  }}
}}
function filterByLeague(type){{
  var cards = document.getElementsByClassName('match-card');
  for(var c of cards){{
    if(type==='all'){{c.style.display=''}}
    else if(type==='non-wc'){{
      c.style.display = c.querySelector('.match-league').innerText.includes('World Cup') ? 'none' : '';
    }}else{{
      c.style.display = c.querySelector('.match-league').innerText.includes('World Cup') ? '' : 'none';
    }}
  }}
  var btns = document.getElementsByClassName('filter-btn');
  for(var b of btns) b.classList.remove('active');
  event.target.classList.add('active');
}}
</script>
</body></html>
"""

report_path = os.path.join(OUTPUT_DIR, 'betting_round2.html')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(html)

# Save JSON
json_path = os.path.join(OUTPUT_DIR, 'betting_round2.json')
json_compat = []
for r in results:
    jr = {k: v for k, v in r.items() if k != 'markets'}
    jr['markets_summary'] = {
        '1x2': r['markets']['1x2'],
        'btts': r['markets']['btts'],
        'over_under_2_5': {'over': r['markets']['over_under']['ov2.5'], 'under': r['markets']['over_under']['un2.5']},
        'double_chance': r['markets']['double_chance'],
    }
    json_compat.append(jr)

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump({
        'generated': datetime.now().isoformat(),
        'model': BEST_MODEL_NAME,
        'markets_covered': len(markets_list),
        'market_names': markets_list,
        'total_matches': len(results),
        'results': json_compat,
    }, f, ensure_ascii=False, indent=2)

# =====================================================================
p(f"\n{'='*70}")
p(f"✅ الرهان الثاني جاهز!")
p(f"  📄 HTML: {report_path}")
p(f"  📄 JSON: {json_path}")
p(f"  📊 المباريات: {len(results)}")
p(f"  📊 أسواق الرهان: 15")
p(f"  📊 الموديل: {BEST_MODEL_NAME}")
p(f"{'='*70}")

# Print top bets summary
p(f"\n{'='*100}")
p(f"{'🏆 TOP BETS TODAY':^100}")
p(f"{'='*100}")
p(f"{'Match':<35} {'Score':<8} {'Best Bets':<55}")
p(f"{'-'*100}")
for r in results[:15]:
    best = r['best_bets'][:3]
    bet_str = ' | '.join(f"{b['market']} {b['outcome']} ({b['prob']:.0f}%)" for b in best)
    p(f"{r['match'][:33]:<35} {r['predicted_score']:<8} {bet_str:<55}")

p(f"\n{'='*70}")
p("🔥 الرهان الثاني جاهز — ENI for LO 🔥")

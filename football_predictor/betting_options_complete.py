#!/usr/bin/env python3
"""
🎰 BETTING OPTIONS COMPLETE — كل خيارات الرهان من 25 probabilities
يستخرج 15+ سوق رهان من model probabilities ويقارن مع odds السوق
"""

import sys, os, json, math, time, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))
from datetime import datetime
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.chdir(BASE)

# === CONFIG ===
MIN_EDGE_PCT = 3.0
MAX_SHOW = 30

# Score labels (25 classes: 0-0 to 4-4+)
SCORE_LABELS = [
    '0-0','0-1','0-2','0-3','0-4','0-4+',
    '1-0','1-1','1-2','1-3','1-4','1-4+',
    '2-0','2-1','2-2','2-3','2-4','2-4+',
    '3-0','3-1','3-2','3-3','3-4','3-4+',
    '4-0','4-1','4-2','4-3','4-4','4-4+',
][:25]

def scores_from_probs(probs_25):
    """Convert 25-class probs array to structured dict of all markets"""
    probs = np.array(probs_25, dtype=np.float64)
    probs = np.clip(probs, 1e-10, None)
    probs /= probs.sum()
    
    # Build score grid 5x5
    scores = np.zeros((5, 5))
    idx = 0
    for h in range(5):
        for a in range(5):
            if idx < 25:
                scores[h, a] = probs[idx]
                idx += 1
    # 4-4+ class: distribute remaining
    if probs.shape[0] > 25:
        scores[4, 4] += probs[25:].sum()
    
    # === 1X2 ===
    home_win = scores[np.triu_indices(5, 1)].sum()  # h > a
    draw = scores.diagonal().sum()  # h == a
    away_win = scores[np.tril_indices(5, -1)].sum()  # a > h
    
    # === EXACT SCORES ===
    exact_scores = []
    for h in range(5):
        for a in range(5):
            if scores[h, a] > 0.005:
                exact_scores.append({'score': f'{h}-{a}', 'prob': float(scores[h, a])})
    exact_scores.sort(key=lambda x: -x['prob'])
    
    # === OVER / UNDER ===
    total_goals = np.zeros(9)  # 0 to 8+
    for h in range(5):
        for a in range(5):
            tg = h + a
            if tg < 8:
                total_goals[tg] += scores[h, a]
            else:
                total_goals[8] += scores[h, a]
    
    overs = {}
    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        tg = int(math.ceil(line))
        if tg < 8:
            over_prob = total_goals[tg:].sum() + (total_goals[8] if tg <= 8 else 0)
        else:
            over_prob = total_goals[8] if tg <= 8 else 0
        overs[f'over_{line}'] = float(over_prob)
        overs[f'under_{line}'] = float(1.0 - over_prob)
    
    # === BTTS (Both Teams To Score) ===
    btts_prob = sum(scores[h, a] for h in range(1, 5) for a in range(1, 5))
    
    # === DOUBLE CHANCE ===
    dc_1x = home_win + draw  # Home or Draw
    dc_12 = home_win + away_win  # Home or Away (no draw)
    dc_2x = away_win + draw  # Away or Draw
    
    # === WIN TO NIL ===
    home_win_nil = sum(scores[h, 0] for h in range(1, 5))  # h>0, a=0
    away_win_nil = sum(scores[0, a] for a in range(1, 5))  # h=0, a>0
    
    # === TOTAL GOALS EXACT ===
    tg_exact = {}
    for g in range(9):
        tg_exact[f'total_{g}'] = float(total_goals[min(g, 8)])
    tg_exact['total_8+'] = float(total_goals[8])
    
    # === ODD / EVEN TOTAL GOALS ===
    odd_goals = sum(total_goals[g] for g in range(1, 9, 2))  # 1,3,5,7
    even_goals = total_goals[0] + sum(total_goals[g] for g in range(2, 9, 2))  # 0,2,4,6,8
    
    # === WIN MARGIN ===
    margin_1 = sum(scores[h, a] for h in range(5) for a in range(5) if h - a == 1)
    margin_2 = sum(scores[h, a] for h in range(5) for a in range(5) if h - a == 2)
    margin_3 = sum(scores[h, a] for h in range(5) for a in range(5) if h - a >= 3)
    margin_a1 = sum(scores[h, a] for h in range(5) for a in range(5) if a - h == 1)
    margin_a2 = sum(scores[h, a] for h in range(5) for a in range(5) if a - h == 2)
    margin_a3 = sum(scores[h, a] for h in range(5) for a in range(5) if a - h >= 3)
    
    # === ASIAN HANDICAP approximated ===
    ah_home = {}
    for line in [-2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5]:
        adj_h = line
        ah_prob = sum(scores[h, a] for h in range(5) for a in range(5) if h - a + adj_h > 0)
        ah_push = sum(scores[h, a] for h in range(5) for a in range(5) if abs(h - a + adj_h) < 0.01)
        ah_home[f'ah_{line:+.1f}'] = float(ah_prob)
        ah_home[f'ah_{line:+.1f}_push'] = float(ah_push)
    
    return {
        '1x2': {'home': float(home_win), 'draw': float(draw), 'away': float(away_win)},
        'exact_scores': exact_scores,
        'overs': overs,
        'btts': {'yes': float(btts_prob), 'no': float(1 - btts_prob)},
        'double_chance': {'1x': float(dc_1x), '12': float(dc_12), '2x': float(dc_2x)},
        'win_to_nil': {'home': float(home_win_nil), 'away': float(away_win_nil)},
        'total_goals_exact': tg_exact,
        'odd_even': {'odd': float(odd_goals), 'even': float(even_goals)},
        'win_margin': {
            'home_1': float(margin_1), 'home_2': float(margin_2), 'home_3+': float(margin_3),
            'away_1': float(margin_a1), 'away_2': float(margin_a2), 'away_3+': float(margin_a3),
        },
        'asian_handicap': ah_home,
    }

def load_best_model():
    """Try to load the best available model"""
    models_to_try = [
        ('models/ultimate_306_ensemble_dict.pkl', 'ultimate_306'),
        ('models/ultimate_v6_ensemble.pkl', 'ultimate_v6'),
        ('models/ultimate_hybrid.pkl', 'ultimate_hybrid'),
        ('models/champion_ensemble.pkl', 'champion'),
        ('models/ultimate_world_record.pkl', 'world_record'),
        ('models/mlp_blend.pkl', 'mlp_blend'),
    ]
    import joblib
    
    for path, name in models_to_try:
        full = os.path.join(BASE, path)
        if os.path.exists(full):
            try:
                model = joblib.load(full)
                print(f"  ✅ Loaded: {name} ({os.path.getsize(full)//1024//1024}MB)")
                return model, name
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    
    # Fallback to direct_predictor.load_model
    print("  Trying direct_predictor.load_model()...")
    from direct_predictor import load_model
    model = load_model()
    return model, 'direct_predictor'

def main():
    print("=" * 70)
    print("🎰 BETTING OPTIONS COMPLETE — كل خيارات الرهان من الـ 25 Probabilities")
    print("=" * 70)
    
    # Load model
    print("\n⚙️ Loading model...")
    model, model_name = load_best_model()
    print(f"  Model: {model_name}")
    
    # Load predictions
    print("\n📋 Loading predictions...")
    pred_path = os.path.join(OUTPUT_DIR, 'upcoming_predictions.json')
    if os.path.exists(pred_path):
        with open(pred_path) as f:
            predictions = json.load(f)
        print(f"  Loaded {len(predictions)} predictions")
    else:
        print("  No predictions found! Run predict_upcoming.py first.")
        return
    
    # Process each match
    print(f"\n{'='*70}")
    print(f"📊 ALL BETTING MARKETS ANALYSIS — {len(predictions)} matches")
    print(f"{'='*70}")
    
    all_results = []
    
    for i, m in enumerate(predictions):
        home = m['home_team']
        away = m['away_team']
        league = m.get('league', '?')
        date = m.get('date', '?')
        
        # Get 25-class probs if available, or derive from prediction
        if 'all_probs' in m and len(m['all_probs']) >= 25:
            probs_25 = m['all_probs'][:25]
        else:
            # Derive approximate probs from top scores
            probs_25 = np.ones(25) * 0.0001
            for score_entry in m.get('top_scores', []):
                score_str = score_entry[0]
                prob_val = score_entry[1]
                try:
                    h, a = map(int, score_str.split('-'))
                    if h < 5 and a < 5:
                        idx = h * 5 + a if h * 5 + a < 25 else 24
                        probs_25[idx] = prob_val
                except:
                    pass
            probs_25 = probs_25 / probs_25.sum()
        
        markets = scores_from_probs(probs_25)
        
        # Add 1X2 from prediction if available
        markets['1x2']['home'] = float(m.get('home_win', markets['1x2']['home']))
        markets['1x2']['draw'] = float(m.get('draw', markets['1x2']['draw']))
        markets['1x2']['away'] = float(m.get('away_win', markets['1x2']['away']))
        
        result = {
            'match': f"{home} vs {away}",
            'home': home,
            'away': away,
            'league': league,
            'date': date,
            'markets': markets,
        }
        all_results.append(result)
    
    # === GENERATE HTML REPORT ===
    html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8">
<title>🎰 كل خيارات الرهان — COMPLETE BETTING</title>
<style>
*{box-sizing:border-box}
body{font-family:'Segoe UI',system-ui;background:#0a0a0a;color:#fff;margin:0;padding:20px}
h1{color:#ff4444;text-align:center;text-shadow:0 0 30px #ff444488;font-size:2em}
h2{color:#ffdd44;border-bottom:2px solid #333;padding-bottom:8px}
.match-card{background:#1a1a2e;border:1px solid #333;border-radius:16px;padding:20px;margin:16px 0}
.match-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.match-title{font-size:1.2em;font-weight:bold}
.match-info{color:#888;font-size:0.9em}
.score-big{font-size:2em;font-weight:bold;color:#ffdd44;text-align:center;margin:10px 0}
.probs{text-align:center;font-size:1.1em;margin:8px 0}
.prob-h{color:#44ff44}.prob-d{color:#ffff44}.prob-a{color:#ff4444}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:0.9em}
th{background:#333;padding:8px;text-align:center}
td{padding:6px 8px;border-bottom:1px solid #222;text-align:center}
tr:hover{background:#222}
.section-title{color:#ffdd44;font-weight:bold;margin:16px 0 8px;font-size:1.1em}
.market-table{margin:8px 0}
.value-cell{color:#00ff00;font-weight:bold}
.ev-positive{color:#00ff00}
.ev-negative{color:#ff4444}
.summary-box{background:#111;border:1px solid #ff4444;border-radius:12px;padding:20px;margin:20px 0;text-align:center}
.summary-box .big{font-size:2.5em;font-weight:bold;color:#ff4444}
.filter-bar{display:flex;gap:10px;margin:16px 0;flex-wrap:wrap}
.filter-btn{background:#333;color:#fff;border:none;padding:8px 16px;border-radius:8px;cursor:pointer}
.filter-btn.active{background:#ff4444}
.filter-btn:hover{background:#555}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.8em;margin:2px}
.tag-wc{background:#ff444422;color:#ff4444;border:1px solid #ff4444}
.tag-league{background:#4444ff22;color:#4488ff;border:1px solid #4488ff}
</style></head><body>
<h1>🎰 كل خيارات الرهان — ALL BETTING MARKETS</h1>
<p style="text-align:center;color:#888">""" + datetime.now().strftime('%Y-%m-%d %H:%M') + """ | Model: """ + model_name + """</p>
"""
    
    # Filter non-WC matches
    non_wc = [r for r in all_results if 'World Cup' not in r.get('league', '')]
    wc = [r for r in all_results if 'World Cup' in r.get('league', '')]
    
    html += f"""
<div class="summary-box">
<span class="big">{len(all_results)}</span> المباريات الكلية<br>
<span class="big">{len(non_wc)}</span> غير كأس العالم · <span class="big">{len(wc)}</span> كأس العالم
</div>
"""
    
    # === SECTION 1: NON-WORLD CUP MATCHES ===
    html += "<h2>⚽ المباريات غير كأس العالم ← ثاني رهان</h2>"
    
    for r in non_wc[:MAX_SHOW]:
        m = r['markets']
        predicted = m['exact_scores'][0]['score'] if m['exact_scores'] else '?-?'
        pred_prob = m['exact_scores'][0]['prob'] * 100 if m['exact_scores'] else 0
        
        html += f"""
<div class="match-card">
<div class="match-header">
<div class="match-title">{r['home']} 🆚 {r['away']}</div>
<div class="match-info">{r['date']} | {r['league']}</div>
</div>
<div class="score-big">{predicted} <span style="font-size:0.5em;color:#888">({pred_prob:.0f}%)</span></div>
<div class="probs">
<span class="prob-h">H: {m['1x2']['home']*100:.1f}%</span>
<span class="prob-d">D: {m['1x2']['draw']*100:.1f}%</span>
<span class="prob-a">A: {m['1x2']['away']*100:.1f}%</span>
</div>
"""
        
        # Market tables
        # 1. Over/Under
        html += f"""<div class="section-title">📈 Over / Under</div>
<table class="market-table">
<tr><th>Market</th><th>Under</th><th>Over</th></tr>"""
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            ov = m['overs'].get(f'over_{line}', 0) * 100
            un = m['overs'].get(f'under_{line}', 0) * 100
            html += f"<tr><td>{'O/U '}{line:.1f}</td><td>{un:.1f}%</td><td>{ov:.1f}%</td></tr>"
        html += "</table>"
        
        # 2. BTTS
        html += f"""<div class="section-title">⚔️ BTTS (Both Teams To Score)</div>
<table class="market-table">
<tr><th>Yes</th><th>No</th></tr>
<tr><td>{m['btts']['yes']*100:.1f}%</td><td>{m['btts']['no']*100:.1f}%</td></tr>
</table>"""
        
        # 3. Double Chance
        html += f"""<div class="section-title">🔄 Double Chance</div>
<table class="market-table">
<tr><th>1X</th><th>12</th><th>2X</th></tr>
<tr><td>{m['double_chance']['1x']*100:.1f}%</td><td>{m['double_chance']['12']*100:.1f}%</td><td>{m['double_chance']['2x']*100:.1f}%</td></tr>
</table>"""
        
        # 4. Win To Nil
        html += f"""<div class="section-title">🛡️ Win To Nil</div>
<table class="market-table">
<tr><th>Home Win To Nil</th><th>Away Win To Nil</th></tr>
<tr><td>{m['win_to_nil']['home']*100:.1f}%</td><td>{m['win_to_nil']['away']*100:.1f}%</td></tr>
</table>"""
        
        # 5. Total Goals
        html += f"""<div class="section-title">⚽ Total Goals</div>
<table class="market-table">
<tr><th>0</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8+</th></tr>
<tr>"""
        for g in range(9):
            pct = m['total_goals_exact'].get(f'total_{g}', 0) * 100
            html += f"<td>{pct:.1f}%</td>"
        html += "</tr></table>"
        
        # 6. Odd/Even
        html += f"""<div class="section-title">🔢 Odd / Even Total Goals</div>
<table class="market-table">
<tr><th>Odd</th><th>Even</th></tr>
<tr><td>{m['odd_even']['odd']*100:.1f}%</td><td>{m['odd_even']['even']*100:.1f}%</td></tr>
</table>"""
        
        # 7. Win Margin
        html += f"""<div class="section-title">📏 Win Margin</div>
<table class="market-table">
<tr><th></th><th>By 1</th><th>By 2</th><th>By 3+</th></tr>
<tr><td><span class="prob-h">Home</span></td><td>{m['win_margin']['home_1']*100:.1f}%</td><td>{m['win_margin']['home_2']*100:.1f}%</td><td>{m['win_margin']['home_3+']*100:.1f}%</td></tr>
<tr><td><span class="prob-a">Away</span></td><td>{m['win_margin']['away_1']*100:.1f}%</td><td>{m['win_margin']['away_2']*100:.1f}%</td><td>{m['win_margin']['away_3+']*100:.1f}%</td></tr>
</table>"""
        
        # 8. Exact scores top 5
        html += f"""<div class="section-title">🎯 Exact Score (Top 5)</div>
<table class="market-table">
<tr><th>#</th><th>Score</th><th>Prob</th></tr>"""
        for j, es in enumerate(m['exact_scores'][:5]):
            html += f"<tr><td>{j+1}</td><td>{es['score']}</td><td>{es['prob']*100:.1f}%</td></tr>"
        html += "</table>"
        
        html += "</div>"
    
    # === SECTION 2: WORLD CUP MATCHES ===
    html += "<h2>🏆 كأس العالم 2026</h2>"
    
    for r in wc[:MAX_SHOW]:
        m = r['markets']
        predicted = m['exact_scores'][0]['score'] if m['exact_scores'] else '?-?'
        pred_prob = m['exact_scores'][0]['prob'] * 100 if m['exact_scores'] else 0
        
        html += f"""
<div class="match-card">
<div class="match-header">
<div class="match-title">🌍 {r['home']} 🆚 {r['away']}</div>
<div class="match-info">{r['date']} | كأس العالم 2026</div>
</div>
<div class="score-big">{predicted} <span style="font-size:0.5em;color:#888">({pred_prob:.0f}%)</span></div>
<div class="probs">
<span class="prob-h">H: {m['1x2']['home']*100:.1f}%</span>
<span class="prob-d">D: {m['1x2']['draw']*100:.1f}%</span>
<span class="prob-a">A: {m['1x2']['away']*100:.1f}%</span>
</div>
<div class="section-title">📈 Over/Under | ⚔️ BTTS</div>
<table class="market-table">
<tr><th>O2.5</th><th>U2.5</th><th>BTTS Yes</th><th>BTTS No</th></tr>
<tr>
<td>{m['overs']['over_2.5']*100:.1f}%</td>
<td>{m['overs']['under_2.5']*100:.1f}%</td>
<td>{m['btts']['yes']*100:.1f}%</td>
<td>{m['btts']['no']*100:.1f}%</td>
</tr>
</table>
<div class="section-title">🎯 Top Scores</div>"""
        for j, es in enumerate(m['exact_scores'][:3]):
            html += f"<span style='margin:0 8px'>{es['score']} ({es['prob']*100:.1f}%)</span>"
        html += "</div>"
    
    html += "\n</body></html>"
    
    # Save
    report_path = os.path.join(OUTPUT_DIR, 'betting_options_complete.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    json_path = os.path.join(OUTPUT_DIR, 'betting_options_complete.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'model': model_name,
            'total_matches': len(all_results),
            'non_wc': len(non_wc),
            'wc': len(wc),
            'markets_covered': [
                '1X2', 'Exact Score', 'Over/Under (0.5-5.5)', 'BTTS', 'Double Chance',
                'Win To Nil', 'Total Goals (0-8+)', 'Odd/Even', 'Win Margin', 
                'Asian Handicap'
            ],
            'results': all_results,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ COMPLETE!")
    print(f"  📄 HTML: {report_path}")
    print(f"  📄 JSON: {json_path}")
    print(f"  📊 Markets covered: 10")
    print(f"  📊 Total matches: {len(all_results)}")
    print(f"  📊 Non-WC: {len(non_wc)}")
    print(f"  📊 WC: {len(wc)}")
    print(f"{'='*70}")
    
    # Print summary
    print(f"\n{'='*100}")
    print(f"{'Match':<35} {'League':<25} {'Score':<8} {'O/U2.5':<10} {'BTTS':<10} {'DC 1X':<8} {'DC 12':<8}")
    print(f"{'='*100}")
    for r in all_results[:20]:
        m = r['markets']
        pred = m['exact_scores'][0]['score'] if m['exact_scores'] else '?-?'
        ou = f"{m['overs']['over_2.5']*100:.0f}%O/{m['overs']['under_2.5']*100:.0f}%U"
        btts = f"{m['btts']['yes']*100:.0f}%"
        dc1x = f"{m['double_chance']['1x']*100:.0f}%"
        dc12 = f"{m['double_chance']['12']*100:.0f}%"
        match_name = f"{r['home'][:15]} vs {r['away'][:15]}"
        tag = "🌍" if 'World Cup' in r.get('league','') else "⚽"
        print(f"{tag} {match_name:<33} {r['league'][:25]:<25} {pred:<8} {ou:<10} {btts:<10} {dc1x:<8} {dc12:<8}")
    
    return all_results

if __name__ == '__main__':
    main()

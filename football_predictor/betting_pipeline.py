"""
48h AUTONOMOUS PIPELINE — Phase 1: Betting Predictor
Fetches upcoming matches, predicts with v3_model, outputs recommendations
"""
import sys, os, json, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
import numpy as np

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
OUT_DIR = os.path.join(os.path.dirname(__file__), 'models')

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}] {msg}')
    with open(os.path.join(OUT_DIR, 'betting_log.txt'), 'a') as f:
        f.write(f'[{ts}] {msg}\n')

log('='*60)
log('BETTING PREDICTOR — v3_model (25.89% exact)')
log('='*60)

# Load model
log('\n[1] Loading v3_model...')
try:
    sys.path.insert(0, os.path.dirname(__file__))
    from direct_predictor import load_real_model, build_feature_vector, predict_match
    model = load_real_model()
    if model is None:
        log('ERROR: No model loaded!')
        exit(1)
    log(f'  Model loaded: {type(model).__name__}')
except Exception as e:
    log(f'ERROR loading model: {e}')
    exit(1)

# Load upcoming matches from DB
log('\n[2] Loading upcoming matches...')
conn = sqlite3.connect(DB)
upcoming = conn.execute('''
    SELECT event_id, home_team, away_team, commence_time, league, odds_json
    FROM odds_upcoming
''').fetchall()
conn.close()
log(f'  {len(upcoming)} upcoming matches')

# Team name resolution function
def resolve_team(name):
    """Try to find team in DB, return SofaScore name."""
    conn2 = sqlite3.connect(DB)
    # Direct match
    r = conn2.execute('SELECT DISTINCT home_team FROM sofa_historical_results WHERE home_team = ? LIMIT 1', (name,)).fetchone()
    if r: conn2.close(); return name
    # Try via mapping
    r = conn2.execute('SELECT sofa_name FROM team_name_mapping WHERE fd_name = ? AND confidence >= 0.85 LIMIT 1', (name.lower().strip(),)).fetchone()
    if r: conn2.close(); return r[0]
    # Fuzzy: find partial match
    r = conn2.execute('SELECT DISTINCT home_team FROM sofa_historical_results WHERE home_team LIKE ? LIMIT 1', ('%' + name + '%',)).fetchone()
    if r: conn2.close(); return r[0]
    conn2.close()
    return name

predictions = []
for match in upcoming:
    eid, ht, at, ct, league, odds_json = match
    match_date = datetime.fromtimestamp(ct).strftime('%Y-%m-%d')
    match_time = datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M')
    
    ht_r = resolve_team(ht)
    at_r = resolve_team(at)
    
    log(f'\n  {ht_r} vs {at_r} ({match_date})')
    
    try:
        result = predict_match(ht_r, at_r, match_date)
    except Exception as e:
        log(f'    predict_match ERROR: {e}')
        continue
    
    if result is None:
        log(f'    SKIP: No prediction')
        continue
    
    # Parse prediction
    score_probs = result['score_probs']
    top_scores_raw = result.get('top_scores', [])
    top_scores = [(int(s.split('-')[0]), int(s.split('-')[1]), p) for s, p in top_scores_raw]
    
    # Compute 1X2 probs from score_probs
    prob_h = sum(p for (s, p) in score_probs.items() if int(s.split('-')[0]) > int(s.split('-')[1]))
    prob_d = sum(p for (s, p) in score_probs.items() if int(s.split('-')[0]) == int(s.split('-')[1]))
    prob_a = sum(p for (s, p) in score_probs.items() if int(s.split('-')[0]) < int(s.split('-')[1]))
    
    # Parse best odds from JSON
    try:
        odds_data = json.loads(odds_json)
        best_h = 1.0; best_d = 1.0; best_a = 1.0
        for bookie in odds_data:
            for market in bookie.get('markets', []):
                if market['key'] == 'h2h':
                    for outcome in market['outcomes']:
                        name = outcome['name']
                        price = outcome['price']
                        if name == ht:
                            best_h = max(best_h, price)
                        elif name == at:
                            best_a = max(best_a, price)
                        elif name == 'Draw':
                            best_d = max(best_d, price)
    except:
        best_h = best_d = best_a = 0
    
    # Kelly criterion
    kelly_h = (prob_h * best_h - 1) / (best_h - 1) if best_h > 1 else 0
    kelly_d = (prob_d * best_d - 1) / (best_d - 1) if best_d > 1 else 0
    kelly_a = (prob_a * best_a - 1) / (best_a - 1) if best_a > 1 else 0
    
    # Expected value
    ev_h = prob_h * best_h - 1
    ev_d = prob_d * best_d - 1
    ev_a = prob_a * best_a - 1
    
    top_score_str = ', '.join([f'{s[0]}-{s[1]} ({s[2]*100:.1f}%)' for s in top_scores[:3]])
    log(f'    Top scores: {top_score_str}')
    log(f'    1X2: {prob_h*100:.1f}% / {prob_d*100:.1f}% / {prob_a*100:.1f}%')
    log(f'    Best odds: {best_h:.2f} / {best_d:.2f} / {best_a:.2f}')
    log(f'    EV: {ev_h*100:+.1f}% / {ev_d*100:+.1f}% / {ev_a*100:+.1f}%')
    
    predictions.append({
        'match': f'{ht_r} vs {at_r}',
        'date': match_date,
        'league': league,
        'probs': {'h': round(prob_h, 4), 'd': round(prob_d, 4), 'a': round(prob_a, 4)},
        'top_scores': top_scores[:5] if top_scores else [],
        'odds': {'h': best_h, 'd': best_d, 'a': best_a},
        'ev': {'h': round(ev_h, 4), 'd': round(ev_d, 4), 'a': round(ev_a, 4)},
        'kelly': {'h': round(kelly_h, 4), 'd': round(kelly_d, 4), 'a': round(kelly_a, 4)},
    })

# Generate recommendations
log('\n' + '='*60)
log('BETTING RECOMMENDATIONS')
log('='*60)

bets = []
for p in predictions:
    for outcome in ['h', 'd', 'a']:
        ev = p['ev'][outcome]
        kelly = p['kelly'][outcome]
        odds = p['odds'][outcome]
        prob = p['probs'][outcome]
        if ev > 0.05 and kelly > 0.01 and odds > 1.5:
            label = {'h': 'HOME', 'd': 'DRAW', 'a': 'AWAY'}[outcome]
            bets.append({
                'match': p['match'],
                'date': p['date'],
                'bet': label,
                'prob': prob,
                'odds': odds,
                'ev': ev,
                'kelly': kelly,
                'stake': min(kelly * 0.25, 0.05),  # fractional Kelly
                'top_scores': p['top_scores'][:3] if p['top_scores'] else [],
            })
            log(f"\n  {p['date']} | {p['match']}")
            log(f"  BET {label} @ {odds:.2f} | prob={prob*100:.1f}% | EV={ev*100:+.1f}%")
            log(f"  Kelly={kelly*100:.1f}% | Stake={min(kelly*0.25,0.05)*100:.1f}% of bankroll")
            if p['top_scores']:
                log(f"  Top scores: {', '.join([f'{s[0]}-{s[1]} ({s[2]*100:.1f}%)' for s in p['top_scores'][:3]])}")

# Save predictions
output = {
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'model': 'v3_model.pkl (25.89% exact)',
    'total_matches': len(predictions),
    'recommended_bets': len(bets),
    'predictions': predictions,
    'bets': bets,
}
with open(os.path.join(OUT_DIR, 'betting_predictions.json'), 'w') as f:
    json.dump(output, f, indent=2, default=str)

log(f'\n{"="*60}')
log(f'SUMMARY')
log(f'  Matches analyzed: {len(predictions)}')
log(f'  Bets recommended: {len(bets)}')
if bets:
    log(f'\n  TOP BETS:')
    bets_sorted = sorted(bets, key=lambda x: -x['ev'])
    for b in bets_sorted[:5]:
        log(f'    {b["date"]} | {b["match"]} | {b["bet"]} @ {b["odds"]:.2f} | EV={b["ev"]*100:+.1f}%')
log(f'\n  Saved to models/betting_predictions.json')
log(f'='*60)

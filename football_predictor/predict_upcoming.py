"""
predict_upcoming.py — Run ensemble on all upcoming matches from The Odds API
"""
import sys, os, json, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
from direct_predictor import predict_match, load_model
from datetime import datetime as dt

def load_upcoming():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT event_id, home_team, away_team, commence_time, league FROM odds_upcoming ORDER BY commence_time")
    rows = cur.fetchall()
    conn.close()
    return rows

# Load model once
print("Loading model...")
model = load_model()
print(f"Model loaded: {type(model).__name__}")

matches = load_upcoming()
print(f"\nUpcoming matches: {len(matches)}")

results = []
for i, (eid, home, away, ct, league) in enumerate(matches):
    date_str = dt.fromtimestamp(ct).strftime("%Y-%m-%d") if ct else dt.now().strftime("%Y-%m-%d")
    
    try:
        pred = predict_match(home, away, date_str)
        if pred:
            result = {
                'home_team': home,
                'away_team': away,
                'date': date_str,
                'league': league,
                'predicted_score': pred['predicted_score'],
                'probability': pred.get('predicted_prob', 0),
                'home_win': pred['probs_1x2']['home'],
                'draw': pred['probs_1x2']['draw'],
                'away_win': pred['probs_1x2']['away'],
                'home_xg': pred['expected_goals']['home'],
                'away_xg': pred['expected_goals']['away'],
                'top_scores': pred.get('top_scores', [])[:5],
            }
            results.append(result)
        else:
            results.append({
                'home_team': home, 'away_team': away, 'date': date_str,
                'league': league, 'error': 'No prediction (missing data)'
            })
    except Exception as e:
        results.append({
            'home_team': home, 'away_team': away, 'date': date_str,
            'league': league, 'error': str(e)
        })
    
    if (i+1) % 20 == 0:
        print(f"  [{i+1}/{len(matches)}] {sum(1 for r in results if 'error' not in r)} predicted")

# Save
output_dir = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(output_dir, exist_ok=True)
output_path = os.path.join(output_dir, 'upcoming_predictions.json')
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\nSaved {len(results)} predictions to {output_path}")

# Summary
success = [r for r in results if 'error' not in r]
print(f"\nSuccessful: {len(success)}/{len(matches)}")

# Top confident picks
sorted_results = sorted(success, key=lambda r: r['probability'], reverse=True)
print("\n=== TOP 10 MOST CONFIDENT PREDICTIONS ===")
for r in sorted_results[:10]:
    print(f"{r['home_team']:30s} vs {r['away_team']:30s} | {r['predicted_score']:5s} ({r['probability']:.1%}) | 1X2: {r['home_win']:.0%}/{r['draw']:.0%}/{r['away_win']:.0%}")

# Top value bets (compare home_win with implied odds from bookmakers)
print("\n=== WORLD CUP MATCHES ===")
wc = [r for r in success if 'World Cup' in r.get('league', '')]
for r in wc[:10]:
    print(f"{r['home_team']:30s} vs {r['away_team']:30s} | {r['predicted_score']:5s} ({r['probability']:.1%}) | xG: {r['home_xg']:.2f}-{r['away_xg']:.2f}")

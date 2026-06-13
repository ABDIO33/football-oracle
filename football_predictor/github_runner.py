"""GitHub Actions runner — runs predictions on schedule, outputs HTML + JSON"""
import os, json, sys
from datetime import datetime

os.chdir(os.path.dirname(__file__))
sys.path.insert(0, '.')

import evaluation
from prediction_engine import get_daily_matches, analyze_match_deep, rate_matches

os.makedirs('output', exist_ok=True)

# Initialize evaluation DB
evaluation.init_evaluation_db()

def build_html(predictions, metrics=None):
    rows = ''
    for p in predictions:
        m = p.get('match', {})
        pred = p.get('prediction', {})
        ht = m.get('home_team', '?')
        at = m.get('away_team', '?')
        score = pred.get('most_likely_score', '?-?')
        conf = pred.get('analysis', {}).get('confidence', '-')
        hw = pred.get('home_win_prob', 0)
        dw = pred.get('draw_prob', 0)
        aw = pred.get('away_win_prob', 0)
        top3 = pred.get('top_scores', [])[:3]
        ts = '<br>'.join([f"{s['score']} {s['prob']}%" for s in top3]) if top3 else '-'
        btts = pred.get('btts_yes', 0)
        ov = pred.get('over_2_5', 0)
        rejected = pred.get('auto_rejected', False)
        badge = '🔴 REJECTED' if rejected else f'🟢 {conf}'
        rows += f"""
        <tr>
            <td>{ht} vs {at}</td>
            <td>{score}</td>
            <td>{badge}</td>
            <td>{hw:.0f}% / {dw:.0f}% / {aw:.0f}%</td>
            <td>{ts}</td>
            <td>{btts:.0f}%</td>
            <td>{ov:.0f}%</td>
        </tr>"""
    
    metrics_html = ''
    if metrics:
        metrics_html = f'''
        <div style="background:#1a1a2e;padding:15px;border-radius:8px;margin:20px 0;text-align:center">
            <h2 style="color:#f7931e;margin-top:0">📊 Evaluation Metrics</h2>
            <p>Total Resolved: {metrics["total_resolved"]} | 
            1X2 Accuracy: <b>{metrics["1x2_accuracy"]}%</b> | 
            Brier Score: {metrics["brier_score"]} | 
            Exact Score (Top 1): {metrics["exact_score_top1_hit_rate"]}%</p>
        </div>'''
    
    total = len(predictions)
    rejected_count = sum(1 for p in predictions if p.get('prediction', {}).get('auto_rejected'))
    
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Football Oracle — Predictions</title>
<style>
body {{ font-family: Arial; margin: 20px; background: #111; color: #eee; }}
h1 {{ color: #f7931e; text-align: center; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #f7931e; color: #111; padding: 10px; }}
td {{ padding: 8px; border-bottom: 1px solid #333; text-align: center; }}
tr:hover {{ background: #222; }}
.updated {{ text-align: center; color: #888; margin-top: 10px; }}
.summary {{ display: flex; justify-content: center; gap: 20px; margin: 20px 0; }}
.card {{ background: #1a1a2e; padding: 15px; border-radius: 8px; text-align: center; min-width: 120px; }}
.card h3 {{ margin: 0; color: #f7931e; }}
.card p {{ margin: 5px 0; font-size: 24px; font-weight: bold; }}
</style></head><body>
<h1>⚽ Football Oracle</h1>
<p class="updated">Last update: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}</p>
<div class="summary">
    <div class="card"><h3>📅 Matches</h3><p>{total}</p></div>
    <div class="card"><h3>✅ Live</h3><p>{total - rejected_count}</p></div>
    <div class="card"><h3>🚫 Rejected</h3><p>{rejected_count}</p></div>
</div>
{metrics_html}
<table><thead><tr>
<th>Match</th><th>Predicted Score</th><th>Confidence</th><th>1X2</th><th>Top 3 Scores</th><th>BTTS</th><th>O2.5</th>
</tr></thead><tbody>{rows}</tbody></table>
</body></html>"""

def main():
    # Resolve pending predictions from previous runs
    try:
        n = evaluation.resolve_predictions()
        if n > 0:
            print(f"[Eval] Resolved {n} predictions")
    except:
        pass
    
    # Get today's matches and predict
    today = datetime.now().strftime('%Y-%m-%d')
    matches = get_daily_matches(today)
    
    if not matches:
        print("[Runner] No matches found today")
        metrics = evaluation.compute_metrics()
        with open('output/index.html', 'w') as f:
            f.write(build_html([], metrics))
        return
    
    print(f"[Runner] Found {len(matches)} matches for {today}")
    best = rate_matches(matches)
    
    # Save predictions as JSON
    with open('output/predictions.json', 'w') as f:
        json.dump(best, f, default=str, indent=2)
    
    # Build HTML page with metrics
    metrics = evaluation.compute_metrics()
    html = build_html(best, metrics)
    with open('output/index.html', 'w') as f:
        f.write(html)
    
    print(f"[Runner] Saved {len(best)} predictions to output/")
    
    if metrics:
        print(f"[Metrics] 1X2={metrics['1x2_accuracy']}% | Brier={metrics['brier_score']} | N={metrics['total_resolved']}")

if __name__ == '__main__':
    main()

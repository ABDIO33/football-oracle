
import sys, os, json, datetime, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ['PYTHONIOENCODING'] = 'utf-8'

from direct_predictor import predict_match
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def fetch_matches():
    import requests
    API_KEY = os.environ.get('BSD_API_KEY') or "f5651c96742c834b5e7e5e0760dcfb3b9bdc205c"
    BASE = 'https://sports.bzzoiro.com/api'
    HEADERS = {'Authorization': f'Token {API_KEY}'}
    today = datetime.date.today().isoformat()
    events = []
    for offset in range(0, 500, 100):
        url = f"{BASE}/events/?limit=100&offset={offset}&date_from={today}&date_to={today}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            data = r.json()
            batch = data.get('results', [])
            events.extend(batch)
            if not data.get('next'):
                break
        except:
            break
        time.sleep(0.1)
    with_odds = [e for e in events if e.get('odds_home') and e.get('odds_away')]
    return with_odds

def predict_matches(events):
    results = []
    for ev in events:
        home = ev.get('home_team', '')
        away = ev.get('away_team', '')
        date = ev.get('event_date', '')[:10]
        odds_h = ev.get('odds_home')
        odds_d = ev.get('odds_draw')
        odds_a = ev.get('odds_away')
        if odds_h and odds_d and odds_a:
            odds = (float(odds_h), float(odds_d), float(odds_a))
        else:
            odds = None
        pred = predict_match(home, away, date, odds_b365=odds, odds_avg=odds)
        if pred:
            pred['home'] = home
            pred['away'] = away
            pred['date'] = date
            pred['odds_home'] = odds_h
            pred['odds_draw'] = odds_d
            pred['odds_away'] = odds_a
            results.append(pred)
    return results

def generate_html(results):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        '<!DOCTYPE html><html dir="ltr"><head>',
        '<meta charset="utf-8"><title>Football Oracle — Predictions</title>',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<style>',
        'body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;max-width:900px;margin:20px auto;padding:0 16px;background:#0d1117;color:#e6edf3}',
        'h1{color:#58a6ff;border-bottom:2px solid #30363d;padding-bottom:8px}',
        '.match{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin:12px 0}',
        '.match-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:14px;color:#8b949e}',
        '.teams{font-size:18px;font-weight:600;margin:8px 0}',
        '.score{color:#58a6ff;font-size:16px;font-weight:600}',
        '.probs{display:flex;gap:12px;margin:8px 0;flex-wrap:wrap}',
        '.prob-bar{flex:1;min-width:80px}',
        '.prob-bar .label{font-size:12px;color:#8b949e}',
        '.bar{height:20px;border-radius:4px;background:#30363d;overflow:hidden}',
        '.bar-fill{height:100%;border-radius:4px;transition:width 0.3s}',
        '.home .bar-fill{background:#238636}',
        '.draw .bar-fill{background:#1f6feb}',
        '.away .bar-fill{background:#da3633}',
        '.top-scores{font-size:13px;color:#8b949e;margin-top:6px}',
        '.top-scores span{margin-right:12px}',
        '.odds{font-size:12px;color:#8b949e;margin-top:4px}',
        '.footer{text-align:center;color:#484f58;font-size:12px;margin:30px 0}',
        '.tag{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;margin-left:8px}',
        '.tag-new{background:#238636;color:#fff}',
        '</style></head><body>',
        f'<h1>⚽ Football Oracle — Daily Predictions</h1>',
        f'<p style="color:#8b949e">Generated: {now} &middot; Model: XGB(20%)+M3+Cal+Stack &middot; <span class="tag tag-new">24.82% Exact</span></p>',
    ]
    if not results:
        lines.append('<p style="color:#da3633">No matches found for today.</p>')
    for r in results:
        top = r.get('top_scores', [])
        probs = r.get('probs_1x2', {})
        xg = r.get('expected_goals', {})
        pred_score = r.get('predicted_score', '?-?')
        pred_prob = r.get('predicted_prob', 0)
        odds_h = r.get('odds_home', '—')
        odds_d = r.get('odds_draw', '—')
        odds_a = r.get('odds_away', '—')
        lines.extend([
            '<div class="match">',
            f'<div class="match-header"><span>{r["home"]} vs {r["away"]}</span><span class="score">🎯 {pred_score} ({pred_prob*100:.1f}%)</span></div>',
            f'<div class="teams">{r["home"]} — {r["away"]}</div>',
            '<div class="probs">',
            f'<div class="prob-bar home"><div class="label">Home {probs.get("home",0)*100:.1f}%</div><div class="bar"><div class="bar-fill" style="width:{probs.get("home",0)*100:.0f}%"></div></div></div>',
            f'<div class="prob-bar draw"><div class="label">Draw {probs.get("draw",0)*100:.1f}%</div><div class="bar"><div class="bar-fill" style="width:{probs.get("draw",0)*100:.0f}%"></div></div></div>',
            f'<div class="prob-bar away"><div class="label">Away {probs.get("away",0)*100:.1f}%</div><div class="bar"><div class="bar-fill" style="width:{probs.get("away",0)*100:.0f}%"></div></div></div>',
            '</div>',
            f'<div class="odds">Odds: {odds_h} / {odds_d} / {odds_a} &middot; xG: {xg.get("home",0):.2f} — {xg.get("away",0):.2f}</div>',
            '<div class="top-scores">Top: ' + ' '.join(f'<span><b>{s}</b> {p*100:.1f}%</span>' for s, p in top[:5]) + '</div>',
            '</div>'
        ])
    lines.append(f'<div class="footer">Football Oracle — Built with BSD API + 89 features + Calibrated Stacking Ensemble</div>')
    lines.append('</body></html>')
    html = '\n'.join(lines)
    path = os.path.join(OUTPUT_DIR, 'predictions_dashboard.html')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Dashboard saved: {path}")
    return path

def main():
    print("[Dashboard] Fetching today's matches...")
    events = fetch_matches()
    print(f"[Dashboard] Found {len(events)} matches")
    if not events:
        print("[Dashboard] No matches found. Generating empty dashboard.")
        generate_html([])
        return
    results = predict_matches(events)
    print(f"[Dashboard] Predicted {len(results)}/{len(events)} matches")
    path = generate_html(results)
    print(f"[Dashboard] Done: {path}")

if __name__ == '__main__':
    main()

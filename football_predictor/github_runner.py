"""GitHub Actions runner — runs predictions on schedule, outputs HTML + JSON + dashboard"""
import os, json, sys, traceback
from datetime import datetime, timedelta

os.chdir(os.path.dirname(__file__))
sys.path.insert(0, '.')

import evaluation
try:
    import calibration
except ImportError:
    calibration = None
try:
    import model_trainer as mt
except ImportError:
    mt = None
from prediction_engine import get_daily_matches, analyze_match_deep, rate_matches

os.makedirs('output', exist_ok=True)

def build_page(predictions, metrics=None):
    total = len(predictions)
    rejected_count = sum(1 for p in predictions if p.get('prediction', {}).get('auto_rejected'))
    live_count = total - rejected_count
    high_conf = sum(1 for p in predictions if p.get('prediction', {}).get('analysis', {}).get('confidence') == 'HIGH')
    med_conf = sum(1 for p in predictions if p.get('prediction', {}).get('analysis', {}).get('confidence') == 'MEDIUM')

    rows = ''
    for p in predictions:
        m = p.get('match', {})
        pred = p.get('prediction', {})
        ht = m.get('home_team', '?')
        at = m.get('away_team', '?')
        comp = m.get('competition', '')
        score = pred.get('most_likely_score', '?-?')
        conf = pred.get('analysis', {}).get('confidence', '-')
        hw = pred.get('home_win_prob', 0)
        dw = pred.get('draw_prob', 0)
        aw = pred.get('away_win_prob', 0)
        top3 = pred.get('top_scores', [])[:3]
        ts = '<br>'.join([f"{s['score']} ({s['prob']}%)" for s in top3]) if top3 else '-'
        btts = pred.get('btts_yes', 0)
        ov = pred.get('over_2_5', 0)
        rejected = pred.get('auto_rejected', False)
        best_bet = pred.get('best_bet_info', {}).get('primary', '')
        expected_goals = f"{pred.get('expected_goals_home', '?'):.2f} - {pred.get('expected_goals_away', '?'):.2f}"

        if rejected:
            badge = '<span class="badge badge-rejected">🚫 REJECTED</span>'
            risk_factors = pred.get('rejection_reasons', [])
            rf_html = '<br>'.join([f'⚠️ {r}' for r in risk_factors[:3]])
            conf = rf_html
        elif conf == 'HIGH':
            badge = f'<span class="badge badge-high">HIGH {conf}</span>'
        elif conf == 'MEDIUM':
            badge = f'<span class="badge badge-med">MED {conf}</span>'
        else:
            badge = f'<span class="badge badge-low">{conf}</span>'

        prob_bar_h = hw * 0.6
        prob_bar_d = dw * 0.6
        prob_bar_a = aw * 0.6

        rows += f"""<tr class="{'rejected-row' if rejected else ''}">
            <td class="match-cell">
                <div class="team-name home">{ht}</div>
                <div class="vs">vs</div>
                <div class="team-name away">{at}</div>
                <div class="comp-name">{comp}</div>
            </td>
            <td class="score-cell">{score}</td>
            <td class="badge-cell">{badge}</td>
            <td class="prob-cell">
                <div class="prob-bar"><div class="prob-fill home-fill" style="width:{prob_bar_h:.1f}%"></div></div>
                <span class="prob-text">H {hw:.0f}%</span>
                <div class="prob-bar"><div class="prob-fill draw-fill" style="width:{prob_bar_d:.1f}%"></div></div>
                <span class="prob-text">D {dw:.0f}%</span>
                <div class="prob-bar"><div class="prob-fill away-fill" style="width:{prob_bar_a:.1f}%"></div></div>
                <span class="prob-text">A {aw:.0f}%</span>
            </td>
            <td>{ts}</td>
            <td>{best_bet}</td>
            <td>{expected_goals}</td>
        </tr>"""

    metrics_html = ''
    if metrics:
        acc_color = '#4CAF50' if metrics.get('1x2_accuracy', 0) > 60 else '#FFC107' if metrics.get('1x2_accuracy', 0) > 45 else '#F44336'
        metrics_html = f'''
        <div class="metrics-bar">
            <div class="metric-card">
                <div class="metric-value">{metrics["total_resolved"]}</div>
                <div class="metric-label">Resolved</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color:{acc_color}">{metrics["1x2_accuracy"]}%</div>
                <div class="metric-label">1X2 Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{metrics["exact_score_top1_hit_rate"]}%</div>
                <div class="metric-label">Exact Score</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{metrics["brier_score"]}</div>
                <div class="metric-label">Brier Score</div>
            </div>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Football Oracle — Predictions</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚽</text></svg>">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a1a; color: #e0e0e0; min-height: 100vh; }}
.header {{ background: linear-gradient(135deg, #1a1a3e 0%, #0d0d2b 100%); padding: 25px 20px; text-align: center; border-bottom: 2px solid #f7931e; }}
.header h1 {{ color: #f7931e; font-size: 28px; letter-spacing: 1px; }}
.header p {{ color: #888; font-size: 13px; margin-top: 5px; }}
.summary {{ display: flex; justify-content: center; gap: 15px; padding: 20px; flex-wrap: wrap; }}
.summary-card {{ background: #1a1a2e; padding: 15px 25px; border-radius: 10px; text-align: center; min-width: 100px; border: 1px solid #2a2a4e; }}
.summary-card h3 {{ color: #f7931e; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.summary-card p {{ font-size: 28px; font-weight: bold; margin-top: 5px; }}
.metrics-bar {{ display: flex; justify-content: center; gap: 15px; padding: 10px 20px 20px; flex-wrap: wrap; }}
.metric-card {{ background: linear-gradient(135deg, #1a2a1e 0%, #0d1a0d 100%); padding: 12px 20px; border-radius: 8px; text-align: center; min-width: 100px; border: 1px solid #2a4a2e; }}
.metric-value {{ font-size: 22px; font-weight: bold; color: #4CAF50; }}
.metric-label {{ font-size: 11px; color: #aaa; text-transform: uppercase; letter-spacing: 1px; margin-top: 3px; }}
.tabs {{ display: flex; justify-content: center; gap: 0; margin: 20px; }}
.tab-btn {{ padding: 10px 24px; background: #1a1a2e; border: 1px solid #2a2a4e; color: #aaa; cursor: pointer; font-size: 13px; transition: all 0.2s; }}
.tab-btn:first-child {{ border-radius: 8px 0 0 8px; }}
.tab-btn:last-child {{ border-radius: 0 8px 8px 0; }}
.tab-btn.active {{ background: #f7931e; color: #111; border-color: #f7931e; font-weight: bold; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 0 15px; }}
.table-wrap {{ overflow-x: auto; background: #111122; border-radius: 10px; border: 1px solid #2a2a4e; margin: 10px 0 30px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 800px; }}
th {{ background: #1a1a3e; color: #f7931e; padding: 12px 10px; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; text-align: center; border-bottom: 2px solid #f7931e; white-space: nowrap; }}
td {{ padding: 10px; border-bottom: 1px solid #1a1a2e; text-align: center; font-size: 13px; vertical-align: middle; }}
tr:hover {{ background: #1a1a2e; }}
tr.rejected-row {{ opacity: 0.5; background: #1a0a0a; }}
.match-cell {{ text-align: center; }}
.team-name {{ font-weight: bold; font-size: 14px; }}
.team-name.home {{ color: #4CAF50; }}
.team-name.away {{ color: #F44336; }}
.vs {{ color: #666; font-size: 11px; margin: 2px 0; }}
.comp-name {{ color: #888; font-size: 10px; margin-top: 3px; }}
.score-cell {{ font-size: 20px; font-weight: bold; color: #fff; }}
.badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
.badge-high {{ background: #1b5e20; color: #a5d6a7; }}
.badge-med {{ background: #e65100; color: #ffcc80; }}
.badge-low {{ background: #b71c1c; color: #ef9a9a; }}
.badge-rejected {{ background: #880e4f; color: #f48fb1; }}
.prob-cell {{ font-size: 12px; line-height: 1.6; }}
.prob-bar {{ height: 4px; background: #333; border-radius: 2px; margin: 2px 0; overflow: hidden; }}
.prob-fill {{ height: 100%; border-radius: 2px; transition: width 0.3s; }}
.home-fill {{ background: #4CAF50; }}
.draw-fill {{ background: #FFC107; }}
.away-fill {{ background: #F44336; }}
.prob-text {{ display: inline-block; min-width: 40px; }}
.status-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }}
.status-green {{ background: #4CAF50; }}
.status-yellow {{ background: #FFC107; }}
.status-red {{ background: #F44336; }}
.footer {{ text-align: center; padding: 20px; color: #555; font-size: 12px; }}
@media (max-width: 768px) {{
    .summary {{ gap: 8px; }}
    .summary-card {{ min-width: 70px; padding: 10px 15px; }}
    .summary-card p {{ font-size: 20px; }}
    td {{ font-size: 11px; padding: 6px; }}
    .score-cell {{ font-size: 16px; }}
}}
</style>
</head>
<body>
<div class="header">
    <h1>⚽ Football Oracle</h1>
    <p>AI-Powered Match Predictions | Updated {datetime.now().strftime('%Y-%m-%d %I:%M %p UTC')}</p>
</div>
<div class="summary">
    <div class="summary-card"><h3>📅 Matches</h3><p>{total}</p></div>
    <div class="summary-card"><h3>✅ Live</h3><p>{live_count}</p></div>
    <div class="summary-card"><h3>🔴 Rejected</h3><p>{rejected_count}</p></div>
    <div class="summary-card" style="border-color:#1b5e20;"><h3>✨ High Conf</h3><p style="color:#4CAF50;">{high_conf}</p></div>
    <div class="summary-card" style="border-color:#e65100;"><h3>🔶 Med Conf</h3><p style="color:#FFC107;">{med_conf}</p></div>
</div>
{metrics_html}
<div class="container">
<div class="table-wrap">
<table>
<thead><tr>
    <th>Match</th>
    <th>Prediction</th>
    <th>Confidence</th>
    <th>1 ⚪ X ⚪ 2</th>
    <th>Top Scores</th>
    <th>Best Bet</th>
    <th>xG</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
</div>
</div>
<div class="footer">
    <p>Football Oracle v2.0 — Data from API-Football, Football-Data.org, AgentRouter AI</p>
    <p>Predictions are for informational purposes only. Please gamble responsibly.</p>
</div>
</body>
</html>"""

def collect_historical_results(days_back=3):
    """Collect finished matches from SofaScore for recent days."""
    import time, sqlite3
    try:
        from curl_cffi import requests as curl_requests
        sofa_headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
            'Accept': 'application/json', 'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/', 'x-requested-with': '721637',
        }
        db_path = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
        db = sqlite3.connect(db_path)
        cur = db.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sofa_historical_results (
                id INTEGER PRIMARY KEY, home_team TEXT, away_team TEXT,
                home_score INTEGER, away_score INTEGER, tournament TEXT,
                unique_tournament_id INTEGER, season_id INTEGER,
                start_timestamp INTEGER, status_type TEXT, date TEXT, UNIQUE(id))
        """)
        total = 0
        for i in range(days_back, 0, -1):
            dt = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            time.sleep(0.35)
            r = curl_requests.get(
                f'https://www.sofascore.com/api/v1/sport/football/scheduled-events/{dt}',
                headers=sofa_headers, impersonate='chrome120', timeout=15)
            if r.status_code != 200:
                continue
            for e in r.json().get('events', []):
                if e.get('status', {}).get('type') != 'finished':
                    continue
                hs = (e.get('homeScore') or {}).get('display')
                aws = (e.get('awayScore') or {}).get('display')
                if hs is None or aws is None:
                    continue
                cur.execute("""
                    INSERT OR IGNORE INTO sofa_historical_results
                    (id, home_team, away_team, home_score, away_score,
                     tournament, unique_tournament_id, season_id,
                     start_timestamp, status_type, date)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, (e.get('id'),
                      (e.get('homeTeam') or {}).get('name', ''),
                      (e.get('awayTeam') or {}).get('name', ''),
                      int(hs), int(aws),
                      (e.get('tournament') or {}).get('name', ''),
                      (e.get('tournament') or {}).get('uniqueTournament', {}).get('id'),
                      (e.get('season') or {}).get('id'),
                      e.get('startTimestamp', 0), 'finished', dt))
                total += 1
            db.commit()
        db.close()
        if total:
            print(f"[HIST] Collected {total} finished matches (last {days_back} days)")
        return total
    except Exception as e:
        print(f"[HIST] Collect error: {e}")
        return 0

def main():
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    ts = now.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] Football Oracle Runner starting...")
    odds_remaining = 0
    try:
        import odds_api_scraper as oas
        odds_remaining = oas.get_remaining_requests()
        print(f"[ODDS] API: {odds_remaining} requests remaining this month")
    except Exception as e:
        print(f"[ODDS] Not available: {e}")

    # Step 0: Collect historical results from SofaScore
    collect_historical_results(days_back=3)

    # Step 1: Retrain model params weekly (Monday <6 UTC)
    try:
        if mt and now.weekday() == 0 and now.hour < 6:
            print("[...] Retraining model on Understat data...")
            mt.train_and_save()
            print("[✓] Model retrained")
    except Exception as e:
        print(f"[!] Retrain error: {e}")

    # Step 2: Resolve pending predictions
    try:
        n = evaluation.resolve_predictions()
        if n > 0:
            print(f"[✓] Resolved {n} pending predictions")
    except Exception as e:
        print(f"[!] resolve error: {e}")

    # Step 3: Get daily matches
    try:
        matches = get_daily_matches(today)
    except Exception as e:
        print(f"[!] get_daily_matches error: {e}")
        matches = []

    if not matches:
        print(f"[!] No matches found for {today}")
        metrics = evaluation.compute_metrics()
        html = build_page([], metrics)
        with open('output/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        with open('output/predictions.json', 'w') as f:
            json.dump([], f)
        print("[✓] Empty page written to output/")
        return

    print(f"[✓] Found {len(matches)} matches for {today}")

    # Step 4: Rate matches
    try:
        best = rate_matches(matches)
        print(f"[✓] Analyzed {len(best)} matches")
    except Exception as e:
        print(f"[!] rate_matches error: {e}")
        traceback.print_exc()
        best = []

    # Step 4: Save predictions
    with open('output/predictions.json', 'w', encoding='utf-8') as f:
        json.dump(best, f, default=str, indent=2, ensure_ascii=False)

    # Step 5: Build HTML
    try:
        metrics = evaluation.compute_metrics()
        html = build_page(best, metrics)
        with open('output/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception as e:
        print(f"[!] HTML build error: {e}")
        fallback_html = f"<html><body><h1>Football Oracle</h1><p>Error: {e}</p></body></html>"
        with open('output/index.html', 'w') as f:
            f.write(fallback_html)

    print(f"[✓] Saved {len(best)} predictions to output/")

    # Step 6: Print summary
    if metrics:
        print(f"[📊] Last {metrics['total_resolved']} resolved | 1X2={metrics['1x2_accuracy']}% | Brier={metrics['brier_score']} | Exact Top1={metrics['exact_score_top1_hit_rate']}%")
    else:
        print("[📊] Not enough resolved predictions yet (<5)")
    # Calibration report
    if calibration is not None:
        try:
            print(calibration.calibration_report())
        except:
            pass

if __name__ == '__main__':
    main()
import sqlite3, os, json, time, threading, numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

CACHE_DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

_EVAL_DB = os.path.join(os.path.dirname(__file__), 'evaluation.db')

def _get_conn():
    conn = sqlite3.connect(_EVAL_DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_evaluation_db():
    conn = _get_conn()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS eval_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT UNIQUE,
            match_date TEXT,
            home_team TEXT,
            away_team TEXT,
            prediction_json TEXT,
            actual_home_score INTEGER,
            actual_away_score INTEGER,
            actual_result TEXT,
            status TEXT DEFAULT 'pending',
            created_at REAL DEFAULT (strftime('%s','now')),
            resolved_at REAL
        );
        CREATE INDEX IF NOT EXISTS idx_eval_status ON eval_predictions(status);
    ''')
    conn.commit(); conn.close()

def log_prediction(home_team, away_team, prediction_dict, match_date=None):
    if match_date is None:
        match_date = datetime.now().strftime('%Y-%m-%d')
    match_id = f"{home_team}_{away_team}_{match_date}"
    match_id = match_id.lower().replace(' ', '_').replace("'", '').replace('&', 'n')
    pred_data = {
        'home_win_prob': prediction_dict.get('home_win_prob'),
        'draw_prob': prediction_dict.get('draw_prob'),
        'away_win_prob': prediction_dict.get('away_win_prob'),
        'most_likely_score': prediction_dict.get('most_likely_score'),
        'exact_score_prob': prediction_dict.get('exact_score_prob'),
        'top_scores': prediction_dict.get('top_scores', [])[:5],
        'over_2_5': prediction_dict.get('over_2_5'),
        'under_2_5': prediction_dict.get('under_2_5'),
        'btts_yes': prediction_dict.get('btts_yes'),
        'expected_goals_home': prediction_dict.get('expected_goals_home'),
        'expected_goals_away': prediction_dict.get('expected_goals_away'),
    }
    try:
        conn = _get_conn()
        conn.execute('INSERT OR IGNORE INTO eval_predictions (match_id, match_date, home_team, away_team, prediction_json, status) VALUES (?,?,?,?,?,?)',
                     (match_id, match_date, home_team, away_team, json.dumps(pred_data, default=str), 'pending'))
        conn.commit(); conn.close()
        return True
    except:
        return False

def resolve_predictions():
    now = datetime.now()
    cutoff = (now - timedelta(hours=3)).strftime('%Y-%m-%d')
    try:
        conn = _get_conn()
        cur = conn.execute("SELECT id, match_date, home_team, away_team FROM eval_predictions WHERE status='pending' AND match_date <= ?", (cutoff,))
        rows = cur.fetchall()
        resolved = 0
        for row in rows:
            pid, mdate, home, away = row
            actual = _fetch_result(home, away, mdate)
            if actual:
                hs, aws, res = actual
                conn.execute("UPDATE eval_predictions SET actual_home_score=?, actual_away_score=?, actual_result=?, status='resolved', resolved_at=strftime('%s','now') WHERE id=?",
                             (hs, aws, res, pid))
                resolved += 1
        conn.commit(); conn.close()
        return resolved
    except:
        return 0

def _norm(t):
    return t.lower().replace("'", "").replace(".", "").replace("-", " ").strip()

def _fetch_result(home_team, away_team, match_date):
    try:
        # Step 1: Check local DB cache (sofa_historical_results)
        if os.path.exists(CACHE_DB):
            cache_conn = sqlite3.connect(CACHE_DB)
            cache_cur = cache_conn.cursor()
            hn, an = _norm(home_team), _norm(away_team)
            cache_cur.execute(
                "SELECT home_team, away_team, home_score, away_score FROM sofa_historical_results WHERE date=?",
                (match_date,))
            for row in cache_cur.fetchall():
                db_home, db_away, db_hs, db_aws = row
                db_hn, db_an = _norm(db_home), _norm(db_away)
                if (hn == db_hn or hn in db_hn or db_hn in hn) and (an == db_an or an in db_an or db_an in an):
                    cache_conn.close()
                    res = 'H' if db_hs > db_aws else ('A' if db_aws > db_hs else 'D')
                    return (db_hs, db_aws, res)
            cache_conn.close()
        # Step 2: Fetch from SofaScore scheduled-events for that date
        from curl_cffi import requests as curl_requests
        sofa_headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 9 Pro) AppleWebKit/537.36 Chrome/120.0.6099.230 Mobile Safari/537.36',
            'Accept': 'application/json', 'Origin': 'https://www.sofascore.com',
            'Referer': 'https://www.sofascore.com/', 'x-requested-with': '721637',
        }
        time.sleep(0.35)
        r = curl_requests.get(
            f'https://www.sofascore.com/api/v1/sport/football/scheduled-events/{match_date}',
            headers=sofa_headers, impersonate='chrome120', timeout=15)
        if r.status_code == 200:
            for e in r.json().get('events', []):
                if e.get('status', {}).get('type') != 'finished':
                    continue
                hs = (e.get('homeScore') or {}).get('display')
                aws = (e.get('awayScore') or {}).get('display')
                if hs is None or aws is None:
                    continue
                e_home = _norm((e.get('homeTeam') or {}).get('name', ''))
                e_away = _norm((e.get('awayTeam') or {}).get('name', ''))
                if (hn == e_home or hn in e_home or e_home in hn) and (an == e_away or an in e_away or e_away in an):
                    res = 'H' if hs > aws else ('A' if aws > hs else 'D')
                    return (int(hs), int(aws), res)
    except:
        pass
    return None

def compute_metrics(last_n_days=30):
    try:
        conn = _get_conn()
        cutoff = (datetime.now() - timedelta(days=last_n_days)).strftime('%Y-%m-%d')
        cur = conn.execute("SELECT prediction_json, actual_home_score, actual_away_score, actual_result FROM eval_predictions WHERE status='resolved' AND match_date >= ?", (cutoff,))
        rows = cur.fetchall(); conn.close()
        if len(rows) < 5:
            return None
        brier_scores, rps_scores, log_losses = [], [], []
        exact_hit_1 = exact_hit_3 = acc_1x2 = 0
        total = len(rows)
        for row in rows:
            pred = json.loads(row[0])
            ah, aa, ar = row[1], row[2], row[3]
            hp = float(pred.get('home_win_prob', 33.33)) / 100
            dp = float(pred.get('draw_prob', 33.33)) / 100
            ap = float(pred.get('away_win_prob', 33.33)) / 100
            actual_h = 1 if ar == 'H' else 0
            actual_d = 1 if ar == 'D' else 0
            actual_a = 1 if ar == 'A' else 0
            brier_scores.append(((hp - actual_h)**2 + (dp - actual_d)**2 + (ap - actual_a)**2) / 3)
            cum_p = [hp, hp+dp, 1.0]
            cum_a = [actual_h, actual_h+actual_d, 1.0]
            rps_scores.append(sum((cum_p[i] - cum_a[i])**2 for i in range(2)) / 2)
            log_losses.append(-np.log(max(1e-15, {'H': hp, 'D': dp, 'A': ap}.get(ar, 0.33))))
            actual_score = f"{ah}-{aa}"
            top_scores = pred.get('top_scores', [])
            if top_scores and top_scores[0].get('score') == actual_score:
                exact_hit_1 += 1
            if actual_score in [s.get('score', '') for s in top_scores[:3]]:
                exact_hit_3 += 1
            pred_res = max({'H': hp, 'D': dp, 'A': ap}, key=lambda k: {'H': hp, 'D': dp, 'A': ap}[k])
            if pred_res == ar:
                acc_1x2 += 1
        return {
            'total_resolved': total,
            'brier_score': round(float(np.mean(brier_scores)), 4),
            'rps_score': round(float(np.mean(rps_scores)), 4),
            'log_loss': round(float(np.mean(log_losses)), 4),
            'exact_score_top1_hit_rate': round(exact_hit_1 / total * 100, 2),
            'exact_score_top3_hit_rate': round(exact_hit_3 / total * 100, 2),
            '1x2_accuracy': round(acc_1x2 / total * 100, 2),
        }
    except:
        return None

def print_metrics_report():
    metrics = compute_metrics(30)
    if metrics:
        print(f"[Eval] Last 30d (N={metrics['total_resolved']}): Brier={metrics['brier_score']} | RPS={metrics['rps_score']} | 1X2 acc={metrics['1x2_accuracy']}% | Exact-1={metrics['exact_score_top1_hit_rate']}% | Exact-3={metrics['exact_score_top3_hit_rate']}%")
    else:
        print("[Eval] Not enough resolved predictions yet (<5)")

def _eval_loop():
    while True:
        try:
            n = resolve_predictions()
            if n > 0:
                print(f"[Eval] Resolved {n} predictions"); print_metrics_report()
        except:
            pass
        time.sleep(10800)  # 3 hours

def start_evaluation_thread():
    t = threading.Thread(target=_eval_loop, daemon=True)
    t.start()
    return t

if __name__ == '__main__':
    init_evaluation_db()
    print_metrics_report()

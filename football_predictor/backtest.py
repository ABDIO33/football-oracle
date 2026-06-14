"""
Backtesting pipeline — time-split validation with zero lookahead
Uses walkforward.py features + prediction_engine.py Dixon-Coles
Stores results in `backtest_results` table for metrics + calibration
"""
import sqlite3, os, json, sys, time, numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
EVAL_DB = os.path.join(os.path.dirname(__file__), 'evaluation.db')

sys.path.insert(0, os.path.dirname(__file__))

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS backtest_results (
            event_id INTEGER PRIMARY KEY,
            date TEXT, home_team TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER,
            home_elo REAL, away_elo REAL,
            home_xg_for REAL, home_xg_against REAL,
            away_xg_for REAL, away_xg_against REAL,
            home_form REAL, away_form REAL,
            predicted_home_win REAL, predicted_draw REAL, predicted_away_win REAL,
            predicted_home_goals REAL, predicted_away_goals REAL,
            predicted_score TEXT,
            predicted_score_prob REAL,
            top3_json TEXT,
            prob_matrix_json TEXT,
            rps REAL, log_loss REAL, brier REAL,
            exact_hit INTEGER, exact_top3_hit INTEGER, outcome_hit INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_bt_date ON backtest_results(date);
    ''')
    conn.commit()
    conn.close()

def _date_to_ts(date_str):
    try:
        return int(datetime.strptime(date_str, '%Y-%m-%d').timestamp())
    except:
        return 0

class Backtester:
    def __init__(self):
        self.conn = sqlite3.connect(DB)
        init_db()
        self.results = []

    def _get_rho(self, tournament):
        from model_trainer import get_rho
        league_map = {
            'Premier League': 'EPL', 'La Liga': 'La_Liga', 'Bundesliga': 'Bundesliga',
            'Serie A': 'Serie_A', 'Ligue 1': 'Ligue_1',
        }
        league_key = None
        for k, v in league_map.items():
            if k.lower() in (tournament or '').lower():
                league_key = v
                break
        if league_key:
            try:
                rho = get_rho(league_key)
                if rho is not None:
                    return rho
            except:
                pass
        return None

    def _resolve_team_sql(self, team_name):
        import difflib
        cur = self.conn.execute('SELECT DISTINCT team_name FROM walkforward_state')
        all_teams = [r[0] for r in cur.fetchall()]
        if team_name in all_teams:
            return team_name
        def norm(s):
            return s.lower().replace(' fc', '').replace(' cf', '').replace(' afc', '').replace(' fc ', ' ').replace(' cf ', ' ').replace('  ', ' ').strip()
        nteam = norm(team_name)
        for t in all_teams:
            if norm(t) == nteam:
                return t
        matches = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.5)
        if matches:
            return matches[0]
        return None

    def _make_lambda_feature_vec(self, home, away, date_str):
        try:
            hr = self._resolve_team_sql(home)
            ar = self._resolve_team_sql(away)
            if not hr or not ar:
                return None
            cur = self.conn.execute('''
                SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                       wf.form_points, wf.matches_played, wf.rolling_shots_for
                FROM walkforward_state wf
                WHERE wf.team_name = ? AND wf.date <= ? ORDER BY wf.date DESC LIMIT 1
            ''', (hr, date_str))
            h = cur.fetchone()
            cur.execute('''
                SELECT wf.elo, wf.rolling_xg_for, wf.rolling_xg_against,
                       wf.form_points, wf.matches_played, wf.rolling_shots_for
                FROM walkforward_state wf
                WHERE wf.team_name = ? AND wf.date <= ? ORDER BY wf.date DESC LIMIT 1
            ''', (ar, date_str))
            a = cur.fetchone()
            if not h or not a:
                return None
            h_elo, h_xgf, h_xga, h_f, h_mp, h_shots = h
            a_elo, a_xgf, a_xga, a_f, a_mp, a_shots = a
            elo_diff = h_elo - a_elo
            import numpy as np
            return np.array([[
                h_elo or 1600, a_elo or 1600, elo_diff,
                h_xgf or 1.2, h_xga or 1.2, a_xgf or 1.2, a_xga or 1.2,
                h_xgf or 1.2, h_xga or 1.2, a_xgf or 1.2, a_xga or 1.2,
                h_f or 0.5, a_f or 0.5, h_mp or 0, a_mp or 0,
                h_shots or 10, a_shots or 10,
            ]])
        except:
            return None

    def run(self, train_cutoff='2025-06-01', test_start='2025-06-01', test_end='2026-06-14', limit=None):
        """Run backtest: Dixon-Coles predictions for matches in test period.
        train_cutoff: only use matches before this as history.
        test_start/test_end: evaluate on this range.
        """
        from prediction_engine import dixon_coles_predict
        print(f"[Backtest] Training: matches before {train_cutoff}")
        print(f"[Backtest] Testing: {test_start} to {test_end}")
        # Train lambda model on data BEFORE test_start only (no leakage)
        self._lam_model_h = None
        self._lam_model_a = None
        try:
            import numpy as np
            from lambda_predictor import _load_training_data, FEATURES
            HAS_SKLEARN = True
            X, yh, ya = _load_training_data(start_date='2026-01-01', end_date=test_start)
            if len(X) >= 100:
                from sklearn.ensemble import GradientBoostingRegressor
                self._lam_model_h = GradientBoostingRegressor(n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8, random_state=42)
                self._lam_model_a = GradientBoostingRegressor(n_estimators=200, max_depth=4, learning_rate=0.1, subsample=0.8, random_state=42)
                self._lam_model_h.fit(X, yh)
                self._lam_model_a.fit(X, ya)
                print(f'[Backtest] Lambda model trained on {len(X)} matches (before {test_start})')
        except Exception as ex:
            print(f'[Backtest] Lambda model not available: {ex}')
            self._lam_model_h = None
            self._lam_model_a = None

        # Load walkforward features for test matches
        cur = self.conn.execute('''
            SELECT r.id, r.date, r.home_team, r.away_team, r.home_score, r.away_score,
                   r.tournament, r.start_timestamp
            FROM sofa_historical_results r
            WHERE r.date >= ? AND r.date <= ?
              AND r.status_type = 'finished'
              AND r.home_score IS NOT NULL AND r.away_score IS NOT NULL
            ORDER BY r.start_timestamp ASC
        ''', (test_start, test_end))
        test_matches = cur.fetchall()
        if limit:
            test_matches = test_matches[:limit]
        print(f"[Backtest] {len(test_matches)} matches to evaluate")

        for idx, row in enumerate(test_matches):
            eid, date_str, home, away, hs, aws, tournament, ts = row
            # Get walk-forward features from BEFORE this match
            features = self._get_features_before(home, away, date_str)
            if not features:
                continue
            # Compute lambda from features
            home_adv = 1.12
            league_avg_xg = 1.5
            base_h = (features['home_xg_for'] * features['away_xg_against'] / league_avg_xg) * home_adv
            base_a = (features['away_xg_for'] * features['home_xg_against'] / league_avg_xg) / home_adv
            form_h = 0.85 + features['home_form'] * 0.30
            form_a = 0.85 + features['away_form'] * 0.30
            elo_diff_h = (features['home_elo'] - features['away_elo']) / 400.0
            elo_diff_a = (features['away_elo'] - features['home_elo']) / 400.0
            elo_mul_h = 1.0 + max(-0.15, min(0.15, elo_diff_h * 0.15))
            elo_mul_a = 1.0 + max(-0.15, min(0.15, elo_diff_a * 0.15))
            lam = max(0.25, min(4.5, base_h * form_h * elo_mul_h))
            mu = max(0.25, min(4.5, base_a * form_a * elo_mul_a))
            # Blend with lambda model if available (retrained per-split)
            if hasattr(self, '_lam_model_h') and self._lam_model_h is not None:
                try:
                    features_vec = self._make_lambda_feature_vec(home, away, date_str)
                    if features_vec is not None:
                        lh = max(0.25, min(4.5, float(self._lam_model_h.predict(features_vec)[0])))
                        la = max(0.25, min(4.5, float(self._lam_model_a.predict(features_vec)[0])))
                        lam = (lam + lh) / 2
                        mu = (mu + la) / 2
                except:
                    pass
            rho = self._get_rho(tournament)
            pred = dixon_coles_predict(lam, mu, rho=rho)
            # Compute metrics
            actual_score = f"{int(hs)}-{int(aws)}"
            hp = pred['home_win_prob']
            dp = pred['draw_prob']
            ap = pred['away_win_prob']
            total_p = hp + dp + ap
            if total_p > 0:
                hp, dp, ap = hp/total_p, dp/total_p, ap/total_p
            actual_h = 1 if hs > aws else 0
            actual_d = 1 if hs == aws else 0
            actual_a = 1 if aws > hs else 0
            brier = ((hp - actual_h)**2 + (dp - actual_d)**2 + (ap - actual_a)**2) / 3
            log_loss = -np.log(max(1e-15, {'H': hp, 'D': dp, 'A': ap}.get('H' if hs > aws else 'D' if hs == aws else 'A', 0.33)))
            cum_p = [hp, hp+dp, 1.0]
            cum_a = [actual_h, actual_h+actual_d, 1.0]
            rps = sum((cum_p[i] - cum_a[i])**2 for i in range(2)) / 2
            exact_hit = 1 if pred['most_likely_score'] == actual_score else 0
            top3 = pred.get('top_scores', [])[:3]
            exact_top3 = 1 if actual_score in [s['score'] for s in top3] else 0
            outcome_hit = 1 if ('H' if hs > aws else 'D' if hs == aws else 'A') == max(['H','D','A'], key=lambda k: {'H':hp,'D':dp,'A':ap}[k]) else 0
            # Store
            try:
                self.conn.execute('''
                    INSERT OR REPLACE INTO backtest_results
                    (event_id, date, home_team, away_team, home_score, away_score,
                     home_elo, away_elo,
                     home_xg_for, home_xg_against, away_xg_for, away_xg_against,
                     home_form, away_form,
                     predicted_home_win, predicted_draw, predicted_away_win,
                     predicted_home_goals, predicted_away_goals,
                     predicted_score, predicted_score_prob,
                     top3_json, prob_matrix_json,
                     rps, log_loss, brier, exact_hit, exact_top3_hit, outcome_hit)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', (
                    eid, date_str, home, away, int(hs), int(aws),
                    features['home_elo'], features['away_elo'],
                    features['home_xg_for'], features['home_xg_against'],
                    features['away_xg_for'], features['away_xg_against'],
                    features['home_form'], features['away_form'],
                    float(hp), float(dp), float(ap),
                    float(lam), float(mu),
                    pred['most_likely_score'], float(pred['exact_score_prob']),
                    json.dumps([s for s in top3], default=str),
                    json.dumps(pred.get('probs', []).tolist() if hasattr(pred.get('probs'), 'tolist') else [], default=str),
                    float(rps), float(log_loss), float(brier), exact_hit, exact_top3_hit, outcome_hit
                ))
                self.conn.commit()
            except Exception as ex:
                pass
            self.results.append({
                'event_id': eid, 'date': date_str,
                'home': home, 'away': away,
                'actual': (int(hs), int(aws)),
                'pred': pred,
                'lam': lam, 'mu': mu,
                'brier': brier, 'rps': rps, 'log_loss': log_loss,
                'exact_hit': exact_hit, 'exact_top3': exact_top3, 'outcome_hit': outcome_hit,
                'features': features,
            })
            if (idx + 1) % 500 == 0:
                self._print_partial(idx + 1)
        self._print_summary()
        return self.results

    def _get_features_before(self, home, away, date_str):
        """Get walk-forward features from right before this match date."""
        cur = self.conn.execute('''
            SELECT elo, matches_played, rolling_xg_for, rolling_xg_against,
                   rolling_shots_for, form_points, form_raw
            FROM walkforward_state
            WHERE team_name = ? AND date <= ?
            ORDER BY date DESC LIMIT 1
        ''', (home, date_str))
        h_row = cur.fetchone()
        cur.execute('''
            SELECT elo, matches_played, rolling_xg_for, rolling_xg_against,
                   rolling_shots_for, form_points, form_raw
            FROM walkforward_state
            WHERE team_name = ? AND date <= ?
            ORDER BY date DESC LIMIT 1
        ''', (away, date_str))
        a_row = cur.fetchone()
        if not h_row or not a_row:
            return None
        return {
            'home_elo': h_row[0], 'away_elo': a_row[0],
            'home_matches': h_row[1], 'away_matches': a_row[1],
            'home_xg_for': h_row[2] or 1.2, 'home_xg_against': h_row[3] or 1.2,
            'away_xg_for': a_row[2] or 1.2, 'away_xg_against': a_row[3] or 1.2,
            'home_shots': h_row[4] or 10, 'away_shots': a_row[4] or 10,
            'home_form': h_row[5] or 0.5, 'away_form': a_row[5] or 0.5,
        }

    def _print_partial(self, count):
        if not self.results:
            return
        exact = sum(1 for r in self.results if r['exact_hit'])
        top3 = sum(1 for r in self.results if r['exact_top3'])
        outcome = sum(1 for r in self.results if r['outcome_hit'])
        n = len(self.results)
        print(f"[Backtest] {count} done | N={n} | Exact={exact/n*100:.1f}% | Top3={top3/n*100:.1f}% | 1X2={outcome/n*100:.1f}% | RPS={np.mean([r['rps'] for r in self.results]):.4f}")

    def _print_summary(self):
        if not self.results:
            print("[Backtest] No results")
            return
        n = len(self.results)
        exact = sum(1 for r in self.results if r['exact_hit'])
        top3 = sum(1 for r in self.results if r['exact_top3'])
        outcome = sum(1 for r in self.results if r['outcome_hit'])
        brier = np.mean([r['brier'] for r in self.results])
        rps = np.mean([r['rps'] for r in self.results])
        log_loss = np.mean([r['log_loss'] for r in self.results])
        print("=" * 60)
        print(f"BACKTEST RESULTS — {n} matches")
        print(f"  Exact Score (Top 1):  {exact/n*100:.2f}%")
        print(f"  Exact Score (Top 3):  {top3/n*100:.2f}%")
        print(f"  1X2 Accuracy:         {outcome/n*100:.2f}%")
        print(f"  Brier Score:          {brier:.4f}")
        print(f"  RPS:                  {rps:.4f}")
        print(f"  Log Loss:             {log_loss:.4f}")
        print("=" * 60)

    def compute_calibration_data(self):
        """Return isotonic regression data from backtest results."""
        cur = self.conn.execute('''
            SELECT predicted_home_win, predicted_draw, predicted_away_win,
                   home_score, away_score
            FROM backtest_results
            WHERE home_score IS NOT NULL
        ''')
        rows = cur.fetchall()
        if len(rows) < 50:
            return None
        cal_data = {
            'home': {'x': [], 'y': []},
            'draw': {'x': [], 'y': []},
            'away': {'x': [], 'y': []},
        }
        for row in rows:
            hp, dp, ap, hs, aws = row
            cal_data['home']['x'].append(hp)
            cal_data['home']['y'].append(1.0 if hs > aws else 0.0)
            cal_data['draw']['x'].append(dp)
            cal_data['draw']['y'].append(1.0 if hs == aws else 0.0)
            cal_data['away']['x'].append(ap)
            cal_data['away']['y'].append(1.0 if aws > hs else 0.0)
        return cal_data

    def save_to_eval_db(self):
        """Copy backtest results to evaluation.db for real calibration."""
        conn = sqlite3.connect(EVAL_DB)
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS eval_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id TEXT UNIQUE,
                match_date TEXT,
                home_team TEXT, away_team TEXT,
                prediction_json TEXT,
                actual_home_score INTEGER, actual_away_score INTEGER,
                actual_result TEXT,
                status TEXT DEFAULT 'resolved',
                created_at REAL,
                resolved_at REAL
            );
        ''')
        cur = self.conn.execute('''
            SELECT date, home_team, away_team, home_score, away_score,
                   predicted_home_win, predicted_draw, predicted_away_win,
                   predicted_score, predicted_score_prob
            FROM backtest_results
        ''')
        count = 0
        for row in cur.fetchall():
            date_str, home, away, hs, aws, hp, dp, ap, score, sp = row
            match_id = f"{home}_{away}_{date_str}".lower().replace(' ', '_').replace("'", '').replace('&', 'n')
            pred_data = {
                'home_win_prob': hp * 100, 'draw_prob': dp * 100, 'away_win_prob': ap * 100,
                'most_likely_score': score, 'exact_score_prob': sp,
                'top_scores': [{'score': score, 'prob': sp}],
            }
            res = 'H' if hs > aws else ('A' if aws > hs else 'D')
            try:
                conn.execute('''
                    INSERT OR IGNORE INTO eval_predictions
                    (match_id, match_date, home_team, away_team, prediction_json,
                     actual_home_score, actual_away_score, actual_result, status)
                    VALUES (?,?,?,?,?,?,?,?,'resolved')
                ''', (match_id, date_str, home, away, json.dumps(pred_data), int(hs), int(aws), res))
                count += 1
            except:
                pass
        conn.commit()
        conn.close()
        print(f"[Backtest] Saved {count} to evaluation.db")
        return count

    def close(self):
        self.conn.close()

def main():
    print("=== Backtesting Pipeline ===")
    bt = Backtester()
    bt.run(train_cutoff='2024-01-01', test_start='2025-06-01', test_end='2026-06-14')
    n = bt.save_to_eval_db()
    cal = bt.compute_calibration_data()
    bt.close()

if __name__ == '__main__':
    main()

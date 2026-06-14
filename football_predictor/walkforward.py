"""
Walk-forward Elo + rolling stats — chronological processing, zero lookahead
Every match's features only use data from matches BEFORE its date.
Stores snapshots in `walkforward_state` table for deterministic backtesting.
"""
import sqlite3, os, json
from datetime import datetime
from collections import defaultdict

DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')

K_FACTOR = 20
INITIAL_ELO = 1600
HOME_ELO_ADV = 70
DECAY_HALF_LIFE_DAYS = 400
DECAY_RATE = 0.693 / DECAY_HALF_LIFE_DAYS

def init_db():
    conn = sqlite3.connect(DB)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS walkforward_state (
            team_name TEXT NOT NULL,
            date TEXT NOT NULL,
            elo REAL,
            matches_played INTEGER,
            rolling_xg_for REAL,
            rolling_xg_against REAL,
            rolling_shots_for REAL,
            rolling_shots_against REAL,
            form_points REAL,
            form_raw TEXT,
            PRIMARY KEY (team_name, date)
        );
        CREATE TABLE IF NOT EXISTS walkforward_progress (
            event_id INTEGER PRIMARY KEY,
            processed_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_wf_team ON walkforward_state(team_name);
        CREATE INDEX IF NOT EXISTS idx_wf_date ON walkforward_state(date);
    ''')
    conn.commit()
    conn.close()

def expected_score(rating_a, rating_b):
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))

class WalkForwardProcessor:
    def __init__(self):
        self.elo = {}  # team_name -> current elo
        self.matches_played = defaultdict(int)
        self.rolling_stats = {}  # team_name -> {xg_for, xg_against, shots_for, shots_against, form}
        self.conn = sqlite3.connect(DB)
        init_db()
        self._load_state()

    def _load_state(self):
        cur = self.conn.execute('SELECT team_name, date, elo, matches_played, rolling_xg_for, rolling_xg_against, rolling_shots_for, rolling_shots_against, form_points, form_raw FROM walkforward_state WHERE date = (SELECT MAX(date) FROM walkforward_state)')
        for row in cur.fetchall():
            name = row[0]
            self.elo[name] = row[2]
            self.matches_played[name] = row[3]
            self.rolling_stats[name] = {
                'xg_for': row[4], 'xg_against': row[5],
                'shots_for': row[6], 'shots_against': row[7],
                'form_points': row[8], 'form_raw': row[9] or '',
            }

    def get_elo(self, team, date):
        """Get Elo for team BEFORE this date — zero lookahead."""
        cur = self.conn.execute('SELECT elo, matches_played FROM walkforward_state WHERE team_name = ? AND date <= ? ORDER BY date DESC LIMIT 1', (team, date))
        row = cur.fetchone()
        if row:
            return row[0], row[1]
        return self.elo.get(team, INITIAL_ELO), self.matches_played.get(team, 0)

    def get_rolling(self, team, date, window=10):
        """Get rolling stats for team using only matches before date."""
        result = {'xg_for': 1.2, 'xg_against': 1.2, 'xg_for_last5': 1.2, 'xg_against_last5': 1.2,
                  'shots_for': 10, 'shots_against': 10,
                  'form': 0.5, 'form_str': '', 'matches_in_window': 0}
        try:
            cur = self.conn.execute('''
                SELECT r.home_team, r.away_team, r.home_score, r.away_score,
                       s.home_xg, s.away_xg, s.home_shots, s.away_shots,
                       r.start_timestamp
                FROM sofa_historical_results r
                LEFT JOIN sofa_match_stats s ON r.id = s.event_id
                WHERE (r.home_team = ? OR r.away_team = ?)
                  AND r.start_timestamp < ?
                  AND r.status_type = 'finished'
                ORDER BY r.start_timestamp DESC
                LIMIT ?
            ''', (team, team, self._date_to_ts(date), window))
            rows = cur.fetchall()
            if not rows:
                return result
            is_home = [r[0] == team for r in rows]
            total_gf = sum(r[2] if ih else r[3] for r, ih in zip(rows, is_home))
            total_ga = sum(r[3] if ih else r[2] for r, ih in zip(rows, is_home))
            total_xgf = sum((r[4] if r[4] is not None else r[2]) if ih else (r[5] if r[5] is not None else r[3]) for r, ih in zip(rows, is_home))
            total_xga = sum((r[5] if r[5] is not None else r[3]) if ih else (r[4] if r[4] is not None else r[2]) for r, ih in zip(rows, is_home))
            total_shots = sum((r[6] if r[6] is not None else 10) if ih else (r[7] if r[7] is not None else 10) for r, ih in zip(rows, is_home))
            wins = sum(1 for r, ih in zip(rows, is_home) if (r[2] > r[3] if ih else r[3] > r[2]))
            draws = sum(1 for r, ih in zip(rows, is_home) if r[2] == r[3])
            n = len(rows)
            result['xg_for'] = total_xgf / n if n else 1.2
            result['xg_against'] = total_xga / n if n else 1.2
            result['shots_for'] = total_shots / n if n else 10
            result['form'] = (wins * 3 + draws) / (n * 3) if n else 0.5
            result['form_str'] = ''.join('W' if (r[2] > r[3] if ih else r[3] > r[2]) else 'D' if r[2] == r[3] else 'L' for r, ih in zip(rows, is_home))
            result['matches_in_window'] = n
            result['goals_for'] = total_gf / n
            result['goals_against'] = total_ga / n
            # Last 5
            rows5 = rows[:min(5, len(rows))]
            is_home5 = is_home[:min(5, len(rows))]
            total_gf5 = sum(r[2] if ih else r[3] for r, ih in zip(rows5, is_home5))
            total_ga5 = sum(r[3] if ih else r[2] for r, ih in zip(rows5, is_home5))
            n5 = len(rows5)
            result['xg_for_last5'] = total_gf5 / n5 if n5 else result['xg_for']
            result['xg_against_last5'] = total_ga5 / n5 if n5 else result['xg_against']
        except:
            pass
        return result

    def compute_features(self, home_team, away_team, match_date, neutral=False):
        """Compute ALL features for a match using only data before match_date."""
        home_elo, home_mp = self.get_elo(home_team, match_date)
        away_elo, away_mp = self.get_elo(away_team, match_date)
        home_roll = self.get_rolling(home_team, match_date)
        away_roll = self.get_rolling(away_team, match_date)
        elo_diff = home_elo - away_elo
        home_adv = 0 if neutral else HOME_ELO_ADV
        expected_h = 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo - home_adv) / 400.0))
        expected_a = 1.0 - expected_h
        return {
            'home_elo': home_elo, 'away_elo': away_elo,
            'home_elo_adv': home_elo + home_adv, 'away_elo_adv': away_elo,
            'elo_diff': elo_diff,
            'home_matches_played': home_mp, 'away_matches_played': away_mp,
            'home_xg_for': home_roll['xg_for'], 'home_xg_against': home_roll['xg_against'],
            'away_xg_for': away_roll['xg_for'], 'away_xg_against': away_roll['xg_against'],
            'home_xg_for_last5': home_roll['xg_for_last5'], 'home_xg_against_last5': home_roll['xg_against_last5'],
            'away_xg_for_last5': away_roll['xg_for_last5'], 'away_xg_against_last5': away_roll['xg_against_last5'],
            'home_shots_for': home_roll['shots_for'], 'away_shots_for': away_roll['shots_for'],
            'home_form': home_roll['form'], 'away_form': away_roll['form'],
            'home_form_str': home_roll['form_str'], 'away_form_str': away_roll['form_str'],
            'expected_home': expected_h, 'expected_away': expected_a,
            'neutral': neutral,
        }

    def process_match(self, home_team, away_team, home_goals, away_goals, ts, date_str, neutral=False):
        """Process a finished match: compute features before, update Elo after."""
        features = self.compute_features(home_team, away_team, date_str, neutral)
        # Update Elo
        home_adv = 0 if neutral else HOME_ELO_ADV
        exp_h = expected_score(self.elo.get(home_team, INITIAL_ELO) + home_adv, self.elo.get(away_team, INITIAL_ELO))
        exp_a = 1.0 - exp_h
        if home_goals > away_goals:
            act_h, act_a = 1.0, 0.0
        elif home_goals == away_goals:
            act_h, act_a = 0.5, 0.5
        else:
            act_h, act_a = 0.0, 1.0
        home_elo_old = self.elo.get(home_team, INITIAL_ELO)
        away_elo_old = self.elo.get(away_team, INITIAL_ELO)
        self.elo[home_team] = home_elo_old + K_FACTOR * (act_h - exp_h)
        self.elo[away_team] = away_elo_old + K_FACTOR * (act_a - exp_a)
        self.matches_played[home_team] += 1
        self.matches_played[away_team] += 1
        # Save state snapshot AFTER updating
        for team, elo_new in [(home_team, self.elo[home_team]), (away_team, self.elo[away_team])]:
            roll = self.get_rolling(team, date_str, 20)
            form_raw = self.rolling_stats.get(team, {}).get('form_raw', '')
            if team == home_team:
                form_raw = (form_raw + ('W' if home_goals > away_goals else 'D' if home_goals == away_goals else 'L'))[-20:]
            else:
                form_raw = (form_raw + ('W' if away_goals > home_goals else 'D' if away_goals == home_goals else 'L'))[-20:]
            self.conn.execute('''
                INSERT OR REPLACE INTO walkforward_state
                (team_name, date, elo, matches_played,
                 rolling_xg_for, rolling_xg_against,
                 rolling_shots_for, rolling_shots_against,
                 form_points, form_raw)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            ''', (team, date_str, elo_new, self.matches_played[team],
                  roll['xg_for'], roll['xg_against'],
                  roll['shots_for'], 0,
                  roll['form'], form_raw))
        self.conn.commit()
        return features

    def run_historical(self, start_date=None, end_date=None):
        """Process ALL historical matches chronologically."""
        query = '''SELECT id, home_team, away_team, home_score, away_score,
                          start_timestamp, date
                   FROM sofa_historical_results
                   WHERE status_type = 'finished' AND home_score IS NOT NULL AND away_score IS NOT NULL
                   ORDER BY start_timestamp ASC'''
        cur = self.conn.execute(query)
        rows = cur.fetchall()
        total = len(rows)
        processed = 0
        skipped = 0
        for row in rows:
            eid, home, away, hs, aws, ts, date_str = row
            if start_date and date_str < start_date:
                continue
            if end_date and date_str > end_date:
                continue
            cur2 = self.conn.execute('SELECT 1 FROM walkforward_progress WHERE event_id = ?', (eid,))
            if cur2.fetchone():
                skipped += 1
                continue
            try:
                self.process_match(home, away, int(hs), int(aws), ts, date_str)
                self.conn.execute('INSERT OR REPLACE INTO walkforward_progress VALUES (?, ?)', (eid, datetime.now().isoformat()))
                self.conn.commit()
                processed += 1
            except Exception as ex:
                print(f"[WF] Error processing {home} vs {away} ({date_str}): {ex}")
            if processed % 1000 == 0:
                print(f"[WF] {processed}/{total} matches processed ({skipped} skipped)")
        print(f"[WF] Done. {processed} new, {total} total matches. {skipped} already processed.")
        return processed

    def close(self):
        self.conn.close()

def main():
    print("=== Walk-Forward Elo + Rolling Stats ===")
    wf = WalkForwardProcessor()
    wf.run_historical()
    wf.close()

if __name__ == '__main__':
    main()

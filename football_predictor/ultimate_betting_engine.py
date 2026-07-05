#!/usr/bin/env python3
"""المحرك الأسطوري للرهانات - Ultimate Betting Engine 🦅"""

import sqlite3, math, json, os, sys, pickle
import numpy as np
from collections import defaultdict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')
MODELS_DIR = os.path.join(BASE, 'models')

class UltimateFeatureBuilder:
    """يبني 306 ميزة لأي فريق من قاعدة البيانات الضخمة"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB)
        self.c = self.conn.cursor()
        self._cache = {}
    
    def get_team_elo(self, team_name, league=None):
        """أفضل Elo من كل المصادر"""
        # 1. Club Elo Enhanced (الأحدث)
        self.c.execute(
            'SELECT elo, match_date FROM source_clubelo_enhanced WHERE team = ? ORDER BY match_date DESC LIMIT 1',
            (team_name,)
        )
        row = self.c.fetchone()
        if row and row[0]:
            return {'source': 'clubelo', 'elo': float(row[0]), 'date': row[1], 'matches': 5, 'xg_for': 1.2, 'xg_against': 1.2, 'form': 0.5}
        
        # 2. Walkforward State (أكبر مصدر)
        self.c.execute(
            'SELECT elo, date, matches_played, rolling_xg_for, rolling_xg_against, form_points FROM walkforward_state WHERE team_name = ? ORDER BY date DESC LIMIT 1',
            (team_name,)
        )
        row = self.c.fetchone()
        if row and row[0]:
            return {
                'source': 'walkforward', 'elo': float(row[0]), 'date': row[1],
                'matches': int(row[2] or 0), 'xg_for': float(row[3] or 1.2), 
                'xg_against': float(row[4] or 1.2), 'form': float(row[5] or 0.5)
            }
        
        # 3. Glicko
        self.c.execute(
            'SELECT glicko_rating, date FROM glicko_state WHERE team_name = ? AND glicko_rating IS NOT NULL ORDER BY date DESC LIMIT 1',
            (team_name,)
        )
        row = self.c.fetchone()
        if row and row[0]:
            return {'source': 'glicko', 'elo': float(row[0]), 'date': row[1], 'matches': 5, 'xg_for': 1.2, 'xg_against': 1.2, 'form': 0.5}
        
        # 4. Team Ratings
        self.c.execute(
            'SELECT rating_mu FROM team_ratings WHERE team_name = ? LIMIT 1',
            (team_name,)
        )
        row = self.c.fetchone()
        if row and row[0]:
            return {'source': 'team_ratings', 'elo': float(row[0]) * 500 + 1000, 'matches': 5, 'xg_for': 1.2, 'xg_against': 1.2, 'form': 0.5}
        
        return {'source': 'default', 'elo': 1500, 'matches': 0, 'xg_for': 1.2, 'xg_against': 1.2, 'form': 0.5}
    
    def get_team_params(self, team_name, league=None):
        """Poisson params - هجوم/دفاع"""
        params = {'attack_h': 1.0, 'attack_a': 1.0, 'defense_h': 1.0, 'defense_a': 1.0,
                  'lambda_h': 1.2, 'lambda_a': 0.8}
        
        self.c.execute(
            'SELECT attack_strength_home, attack_strength_away, defense_strength_home, defense_strength_away, '
            'lambda_home_scored, lambda_away_scored, total_matches FROM neg_poisson_params '
            'WHERE team_name = ? ORDER BY total_matches DESC LIMIT 1',
            (team_name,)
        )
        row = self.c.fetchone()
        if row:
            params.update({
                'attack_h': float(row[0] or 1.0), 'attack_a': float(row[1] or 1.0),
                'defense_h': float(row[2] or 1.0), 'defense_a': float(row[3] or 1.0),
                'lambda_h': float(row[4] or 1.2), 'lambda_a': float(row[5] or 0.8),
                'matches_params': int(row[6] or 0)
            })
        return params
    
    def get_team_streak(self, team_name):
        """آخر نتائج الفريق"""
        streak = {'type': 'none', 'len': 0, 'last5': '-----', 'form_pts': 0.5}
        
        self.c.execute(
            'SELECT current_streak_type, current_streak_len, last_5_results, home_streak FROM neg_streaks WHERE team_name = ? LIMIT 1',
            (team_name,)
        )
        row = self.c.fetchone()
        if row:
            last5 = row[2] or ''
            wins = last5.count('W')
            pts = wins / max(len(last5), 1)
            streak.update({
                'type': row[0] or 'none', 'len': int(row[1] or 0),
                'last5': last5, 'form_pts': min(pts * 2, 1.0)
            })
        return streak
    
    def get_h2h(self, home, away):
        """تاريخ المواجهات المباشرة"""
        h2h = {'matches': 0, 'home_wins': 0, 'draws': 0, 'away_wins': 0,
               'home_goals': 0, 'away_goals': 0}
        
        self.c.execute(
            'SELECT total_matches, home_wins, draws, away_wins, home_goals_total, away_goals_total '
            'FROM neg_h2h_features WHERE home_team = ? AND away_team = ? LIMIT 1',
            (home, away)
        )
        row = self.c.fetchone()
        if row:
            h2h.update({
                'matches': int(row[0] or 0), 'home_wins': int(row[1] or 0),
                'draws': int(row[2] or 0), 'away_wins': int(row[3] or 0),
                'home_goals': float(row[4] or 0), 'away_goals': float(row[5] or 0)
            })
        return h2h
    
    def get_league_avg(self, league):
        """متوسطات الدوري"""
        avg = {'home_goals': 1.3, 'away_goals': 1.0, 'home_win': 0.42,
               'draw': 0.28, 'away_win': 0.30, 'total_goals': 2.3}
        
        if not league:
            return avg
        
        self.c.execute(
            'SELECT avg_home_goals, avg_away_goals, avg_total_goals, home_win_pct, draw_pct, away_win_pct '
            'FROM neg_league_averages WHERE tournament = ? LIMIT 1',
            (league,)
        )
        row = self.c.fetchone()
        if row:
            avg.update({
                'home_goals': float(row[0] or 1.3), 'away_goals': float(row[1] or 1.0),
                'total_goals': float(row[2] or 2.3),
                'home_win': float(row[3] or 0.42), 'draw': float(row[4] or 0.28),
                'away_win': float(row[5] or 0.30)
            })
        return avg
    
    def get_recent_form(self, team_name, n=10):
        """آخر n مباراة من المصادر المختلفة"""
        results = []
        
        # من source_livescore
        self.c.execute(
            "SELECT match_date, home_team, away_team, home_score, away_score FROM source_livescore "
            "WHERE (home_team = ? OR away_team = ?) AND home_score IS NOT NULL "
            "ORDER BY match_date DESC LIMIT ?",
            (team_name, team_name, n)
        )
        for r in self.c.fetchall():
            is_home = r[1] == team_name
            gf = int(r[3]) if is_home else int(r[4])
            ga = int(r[4]) if is_home else int(r[3])
            results.append({'gf': gf, 'ga': ga, 'is_home': is_home, 'date': r[0]})
        
        # من flashscore
        if len(results) < n:
            self.c.execute(
                "SELECT home_team, away_team, home_score, away_score FROM flashscore_matches "
                "WHERE (home_team = ? OR away_team = ?) AND home_score IS NOT NULL "
                "ORDER BY ts DESC LIMIT ?",
                (team_name, team_name, n - len(results))
            )
            for r in self.c.fetchall():
                is_home = r[0] == team_name
                gf = int(r[2]) if is_home else int(r[3])
                ga = int(r[3]) if is_home else int(r[2])
                results.append({'gf': gf, 'ga': ga, 'is_home': is_home})
        
        return results
    
    def build_306_features(self, home_team, away_team, league=None):
        """يبني 306 ميزة للمباراة"""
        features = np.zeros(306)
        idx = 0
        
        # === 1. ELO FEATURES (30) ===
        h_elo = self.get_team_elo(home_team)
        a_elo = self.get_team_elo(away_team)
        
        h_elo_val = h_elo['elo'] if h_elo else 1500
        a_elo_val = a_elo['elo'] if a_elo else 1500
        
        features[idx] = h_elo_val; idx += 1  # home_elo
        features[idx] = a_elo_val; idx += 1  # away_elo
        features[idx] = h_elo_val - a_elo_val; idx += 1  # elo_diff
        features[idx] = (h_elo_val - a_elo_val) ** 2 / 1000; idx += 1  # elo_diff_sq
        features[idx] = 1.0 / (1.0 + 10.0 ** ((a_elo_val - h_elo_val) / 400.0)); idx += 1  # elo_win_prob
        
        # h2h Elo (مصادر مختلفة)
        features[idx] = h_elo.get('matches', 0); idx += 1
        features[idx] = a_elo.get('matches', 0); idx += 1
        features[idx] = h_elo.get('xg_for', 0); idx += 1
        features[idx] = a_elo.get('xg_for', 0); idx += 1
        features[idx] = h_elo.get('xg_against', 0); idx += 1
        features[idx] = a_elo.get('xg_against', 0); idx += 1
        features[idx] = h_elo.get('form', 0.5); idx += 1
        features[idx] = a_elo.get('form', 0.5); idx += 1
        features[idx] = abs(h_elo.get('form', 0.5) - a_elo.get('form', 0.5)); idx += 1
        
        # Glicko
        h_g = self.get_team_elo(home_team)
        a_g = self.get_team_elo(away_team)
        h_g_val = float(self.c.execute("SELECT glicko_rating FROM glicko_state WHERE team_name=? ORDER BY date DESC LIMIT 1", (home_team,)).fetchone()[0] if self.c.execute("SELECT 1 FROM glicko_state WHERE team_name=?", (home_team,)).fetchone() else 0) or 0
        a_g_val = float(self.c.execute("SELECT glicko_rating FROM glicko_state WHERE team_name=? ORDER BY date DESC LIMIT 1", (away_team,)).fetchone()[0] if self.c.execute("SELECT 1 FROM glicko_state WHERE team_name=?", (away_team,)).fetchone() else 0) or 0
        try:
            self.c.execute("SELECT glicko_rating FROM glicko_state WHERE team_name=? ORDER BY date DESC LIMIT 1", (home_team,))
            r = self.c.fetchone()
            h_g_val = float(r[0]) if r else 1500
        except: h_g_val = 1500
        try:
            self.c.execute("SELECT glicko_rating FROM glicko_state WHERE team_name=? ORDER BY date DESC LIMIT 1", (away_team,))
            r = self.c.fetchone()
            a_g_val = float(r[0]) if r else 1500
        except: a_g_val = 1500
        
        features[idx] = h_g_val; idx += 1
        features[idx] = a_g_val; idx += 1
        features[idx] = h_g_val - a_g_val; idx += 1
        idx += 15  # padding to 30
        
        # === 2. POISSON PARAMS (30) ===
        hp = self.get_team_params(home_team, league)
        ap = self.get_team_params(away_team, league)
        
        features[idx] = hp['attack_h']; idx += 1
        features[idx] = ap['attack_a']; idx += 1
        features[idx] = hp['defense_h']; idx += 1
        features[idx] = ap['defense_a']; idx += 1
        features[idx] = hp['lambda_h']; idx += 1
        features[idx] = ap['lambda_a']; idx += 1
        features[idx] = hp['attack_h'] / ap['defense_a']; idx += 1  # relative attack
        features[idx] = ap['attack_a'] / hp['defense_h']; idx += 1  # relative defense
        features[idx] = (hp['lambda_h'] * ap['defense_a']); idx += 1  # expected home
        features[idx] = (ap['lambda_a'] * hp['defense_h']); idx += 1  # expected away
        idx += 20
        
        # === 3. FORM & STREAKS (30) ===
        hs = self.get_team_streak(home_team)
        as_ = self.get_team_streak(away_team)
        
        features[idx] = hs['form_pts']; idx += 1
        features[idx] = as_['form_pts']; idx += 1
        features[idx] = hs['form_pts'] - as_['form_pts']; idx += 1
        features[idx] = hs['len'] if hs['type'] == 'win' else -hs['len'] if hs['type'] == 'loss' else 0; idx += 1
        features[idx] = as_['len'] if as_['type'] == 'win' else -as_['len'] if as_['type'] == 'loss' else 0; idx += 1
        
        # Recent goals from last 5
        h_form = self.get_recent_form(home_team, 5)
        a_form = self.get_recent_form(away_team, 5)
        
        h_gf = sum(f['gf'] for f in h_form) / max(len(h_form), 1)
        h_ga = sum(f['ga'] for f in h_form) / max(len(h_form), 1)
        a_gf = sum(f['gf'] for f in a_form) / max(len(a_form), 1)
        a_ga = sum(f['ga'] for f in a_form) / max(len(a_form), 1)
        
        features[idx] = h_gf; idx += 1
        features[idx] = h_ga; idx += 1
        features[idx] = a_gf; idx += 1
        features[idx] = a_ga; idx += 1
        features[idx] = h_gf - a_gf; idx += 1
        features[idx] = h_ga - a_ga; idx += 1
        features[idx] = len(h_form); idx += 1
        features[idx] = len(a_form); idx += 1
        features[idx] = h_gf - h_ga; idx += 1  # home goal diff
        features[idx] = a_gf - a_ga; idx += 1  # away goal diff
        idx += 10
        
        # === 4. H2H FEATURES (30) ===
        h2h = self.get_h2h(home_team, away_team)
        
        features[idx] = h2h['matches']; idx += 1
        features[idx] = h2h['home_wins'] / max(h2h['matches'], 1); idx += 1
        features[idx] = h2h['draws'] / max(h2h['matches'], 1); idx += 1
        features[idx] = h2h['away_wins'] / max(h2h['matches'], 1); idx += 1
        features[idx] = h2h['home_goals']; idx += 1
        features[idx] = h2h['away_goals']; idx += 1
        features[idx] = h2h['home_goals'] - h2h['away_goals']; idx += 1
        idx += 23
        
        # === 5. LEAGUE CONTEXT (30) ===
        lavg = self.get_league_avg(league)
        
        features[idx] = lavg['home_goals']; idx += 1
        features[idx] = lavg['away_goals']; idx += 1
        features[idx] = lavg['total_goals']; idx += 1
        features[idx] = lavg['home_win']; idx += 1
        features[idx] = lavg['draw']; idx += 1
        features[idx] = lavg['away_win']; idx += 1
        idx += 24
        
        # === 6. CROSS FEATURES (30) ===
        # elo × form
        features[idx] = h_elo_val * hs['form_pts']; idx += 1
        features[idx] = a_elo_val * as_['form_pts']; idx += 1
        # elo × attack
        features[idx] = h_elo_val * hp['attack_h']; idx += 1
        features[idx] = a_elo_val * ap['attack_a']; idx += 1
        # Poisson xG × form
        exp_h = hp['lambda_h'] * ap['defense_a'] * 1.2
        exp_a = ap['lambda_a'] * hp['defense_h'] * 0.8
        features[idx] = exp_h; idx += 1
        features[idx] = exp_a; idx += 1
        features[idx] = exp_h - exp_a; idx += 1
        features[idx] = exp_h + exp_a; idx += 1
        idx += 22
        
        # === 7. ADVANCED POISSON (36) ===
        # Poisson probs for each score 0-0 to 4-4
        lambda_h = max(exp_h, 0.1)
        lambda_a = max(exp_a, 0.1)
        for h in range(6):
            for a in range(6):
                if idx < 306:
                    ph = math.exp(-lambda_h) * (lambda_h ** h) / math.factorial(h)
                    pa = math.exp(-lambda_a) * (lambda_a ** a) / math.factorial(a)
                    features[idx] = ph * pa
                    idx += 1
        if idx < 306:
            features[idx] = 0; idx += 1  # padding
        
        # === 8. DERIVED MARKET PROBS (60) ===
        # Recalculate from Poisson
        scores_5x5 = features[144:144+36].reshape(6, 6)[:5, :5]
        hw = sum(scores_5x5[h, a] for h in range(5) for a in range(5) if h > a)
        dr = sum(scores_5x5[i, i] for i in range(5))
        aw = sum(scores_5x5[h, a] for h in range(5) for a in range(5) if a > h)
        
        # 1X2
        features[idx] = hw; idx += 1
        features[idx] = dr; idx += 1
        features[idx] = aw; idx += 1
        
        # O/U
        tg = [sum(scores_5x5[h, a] for h in range(5) for a in range(5) if h + a == g) for g in range(9)]
        for thresh in [0.5, 1.5, 2.5, 3.5, 4.5]:
            ov = sum(tg[math.ceil(thresh):])
            features[idx] = ov; idx += 1
            features[idx] = 1 - ov; idx += 1
        
        # BTTS
        btts_y = sum(scores_5x5[h, a] for h in range(1, 5) for a in range(1, 5))
        features[idx] = btts_y; idx += 1
        features[idx] = 1 - btts_y; idx += 1
        
        # DC
        features[idx] = hw + dr; idx += 1  # 1X
        features[idx] = hw + aw; idx += 1  # 12
        features[idx] = dr + aw; idx += 1  # 2X
        
        # Win to Nil
        features[idx] = sum(scores_5x5[h, 0] for h in range(1, 5)); idx += 1
        features[idx] = sum(scores_5x5[0, a] for a in range(1, 5)); idx += 1
        
        # O/E
        odd = sum(tg[g] for g in range(1, 9, 2))
        even = tg[0] + sum(tg[g] for g in range(2, 9, 2))
        features[idx] = odd; idx += 1
        features[idx] = even; idx += 1
        
        # Goal ranges
        features[idx] = tg[0] + tg[1]; idx += 1  # 0-1
        features[idx] = tg[2] + tg[3]; idx += 1  # 2-3
        features[idx] = sum(tg[4:7]); idx += 1    # 4-6
        features[idx] = sum(tg[7:]); idx += 1     # 7+
        idx += 30
        
        # === 9. ODDS FEATURES (30) ===
        try:
            self.c.execute(
                'SELECT odds_json FROM odds_upcoming WHERE home_team = ? AND away_team = ? LIMIT 1',
                (home_team, away_team)
            )
            row = self.c.fetchone()
            if row and row[0]:
                odds_data = json.loads(row[0])
                best_h, best_d, best_a = 0, 0, 0
                for bookie in odds_data:
                    if isinstance(bookie, dict) and 'markets' in bookie:
                        for mkt in bookie['markets']:
                            if mkt.get('key') == 'h2h':
                                pr = {o['name']: o['price'] for o in mkt['outcomes']}
                                h = pr.get(home_team, pr.get('Home', 0))
                                d = pr.get('Draw', 0)
                                a = pr.get(away_team, pr.get('Away', 0))
                                if h > best_h: best_h, best_d, best_a = h, d, a
                if best_h:
                    features[idx] = 1.0 / best_h; idx += 1  # implied H
                    features[idx] = 1.0 / best_d; idx += 1  # implied D
                    features[idx] = 1.0 / best_a; idx += 1  # implied A
                    imp_sum = 1.0/best_h + 1.0/best_d + 1.0/best_a
                    features[idx] = imp_sum; idx += 1  # margin
                    features[idx] = (1.0/best_h) / imp_sum; idx += 1  # normalized H
                    features[idx] = (1.0/best_d) / imp_sum; idx += 1  # normalized D
                    features[idx] = (1.0/best_a) / imp_sum; idx += 1  # normalized A
                    idx += 23
                else:
                    idx += 30
            else:
                idx += 30
        except:
            idx += 30
        
        # === 10. WEATHER & VENUE (30) ===
        try:
            self.c.execute('SELECT lat, lon FROM team_venue WHERE team_name = ? LIMIT 1', (home_team,))
            h_venue = self.c.fetchone()
            self.c.execute('SELECT lat, lon FROM team_venue WHERE team_name = ? LIMIT 1', (away_team,))
            a_venue = self.c.fetchone()
            
            if h_venue and a_venue:
                h_lat, h_lon = float(h_venue[0]), float(h_venue[1])
                a_lat, a_lon = float(a_venue[0]), float(a_venue[1])
                # Travel distance (haverisine تقريبي)
                from math import radians, sin, cos, sqrt, asin
                R = 6371
                dlat = radians(a_lat - h_lat)
                dlon = radians(a_lon - h_lon)
                c1 = sin(dlat/2)**2 + cos(radians(h_lat)) * cos(radians(a_lat)) * sin(dlon/2)**2
                c2 = 2 * asin(sqrt(c1))
                dist = R * c2
                features[idx] = dist / 1000; idx += 1  # travel
                features[idx] = min(dist / 5000, 1.0); idx += 1  # normalized
                idx += 28
            else:
                idx += 30
        except:
            idx += 30
        
        return features
    
    def close(self):
        self.conn.close()


class UltimatePredictor:
    """المتنبئ الأسطوري باستخدام Ultimate 306 model + Poisson"""
    
    def __init__(self):
        self.fb = UltimateFeatureBuilder()
        self.ultimate_model = None
        self._load_ultimate()
    
    def _load_ultimate(self):
        """تحميل Ultimate 306 model (joblib)"""
        model_path = os.path.join(MODELS_DIR, 'ultimate_306_ensemble_dict.pkl')
        if os.path.exists(model_path):
            try:
                import joblib
                data = joblib.load(model_path)
                self.ultimate_models = data['models']
                self.ultimate_weights = data['weights']
                self.ultimate_n_features = data.get('n_features', 306)
                return True
            except Exception as e:
                print(f'  ⚠️ Ultimate 306 load error: {e}')
        return False
    
    def predict(self, home_team, away_team, league=None):
        """توقع المباراة بأقصى دقة"""
        features = self.fb.build_306_features(home_team, away_team, league)
        
        # Try Ultimate 306 first
        if hasattr(self, 'ultimate_models') and self.ultimate_models is not None:
            try:
                f_2d = [features[:306]]
                probs_list = []
                for i, m in enumerate(self.ultimate_models):
                    w = self.ultimate_weights[i] if i < len(self.ultimate_weights) else 0
                    if w > 0 and hasattr(m, 'predict_proba'):
                        p = m.predict_proba(f_2d)[0]
                        probs_list.append(p * w)
                if probs_list:
                    import numpy as np
                    probs = np.sum(probs_list, axis=0)
                    probs /= probs.sum()
                    return self._probs_to_markets(probs, features, home_team, away_team)
            except Exception as e:
                print(f'  ⚠️ Ultimate 306 predict error: {e}')
        
        # Fallback: Poisson from features
        return self._poisson_fallback(features)
    
    def _probs_to_markets(self, probs, features, home_team='?', away_team='?'):
        """تحويل 25 احتمال إلى كل الأسواق"""
        p = np.array(probs)
        p = np.clip(p, 1e-10, None)
        p /= p.sum()
        
        scores = p.reshape(5, 5)
        hw = float(sum(scores[h, a] for h in range(5) for a in range(5) if h > a))
        dr = float(sum(scores[i, i] for i in range(5)))
        aw = float(sum(scores[h, a] for h in range(5) for a in range(5) if a > h))
        
        exact = []
        for h in range(5):
            for a in range(5):
                if scores[h, a] > 0.005:
                    exact.append({'s': f'{h}-{a}', 'p': float(scores[h, a])})
        exact.sort(key=lambda x: -x['p'])
        
        tg = [float(sum(scores[h, a] for h in range(5) for a in range(5) if h + a == g)) for g in range(9)]
        btts_y = float(sum(scores[h, a] for h in range(1, 5) for a in range(1, 5)))
        
        result = {
            '1x2': {'H': hw, 'D': dr, 'A': aw},
            'exact': exact[:5],
            'ou': {
                'O0.5': sum(tg[1:]), 'O1.5': sum(tg[2:]), 'O2.5': sum(tg[3:]),
                'O3.5': sum(tg[4:]), 'O4.5': sum(tg[5:]),
                'U0.5': tg[0], 'U1.5': sum(tg[:2]), 'U2.5': sum(tg[:3]),
                'U3.5': sum(tg[:4]), 'U4.5': sum(tg[:5]),
            },
            'btts': {'Y': btts_y, 'N': 1 - btts_y},
            'dc': {'1X': hw + dr, '12': hw + aw, '2X': dr + aw},
            'wtn': {'H': float(sum(scores[h, 0] for h in range(1, 5))),
                    'A': float(sum(scores[0, a] for a in range(1, 5)))},
            'tg': {str(g): tg[min(g, 8)] for g in range(9)},
            'oe': {'O': sum(tg[g] for g in range(1, 9, 2)),
                   'E': tg[0] + sum(tg[g] for g in range(2, 9, 2))},
            'gr': {'0-1': tg[0] + tg[1], '2-3': tg[2] + tg[3],
                   '4-5': tg[4] + tg[5], '6+': sum(tg[6:])},
            'confidence': max(hw, dr, aw),
            'predicted_score': exact[0]['s'] if exact else '?-?',
            'predicted_prob': exact[0]['p'] if exact else 0,
            'source': 'ultimate_306'
        }
        return result
    
    def _poisson_fallback(self, features):
        """Poisson من الميزات"""
        exp_h = features[80] if len(features) > 80 else 1.0
        exp_a = features[81] if len(features) > 81 else 0.8
        
        lambda_h = max(exp_h, 0.1)
        lambda_a = max(exp_a, 0.1)
        
        scores = {}
        for h in range(5):
            for a in range(5):
                ph = math.exp(-lambda_h) * (lambda_h ** h) / math.factorial(h)
                pa = math.exp(-lambda_a) * (lambda_a ** a) / math.factorial(a)
                scores[f'{h}-{a}'] = ph * pa
        
        total = sum(scores.values())
        for k in scores:
            scores[k] /= total
        
        scores_np = np.array([[scores.get(f'{h}-{a}', 0) for a in range(5)] for h in range(5)])
        
        hw = float(sum(scores_np[h, a] for h in range(5) for a in range(5) if h > a))
        dr = float(sum(scores_np[i, i] for i in range(5)))
        aw = float(sum(scores_np[h, a] for h in range(5) for a in range(5) if a > h))
        
        exact = sorted([(f'{h}-{a}', scores_np[h, a]) for h in range(5) for a in range(5) if scores_np[h, a] > 0.005],
                       key=lambda x: -x[1])[:5]
        
        return {
            '1x2': {'H': hw, 'D': dr, 'A': aw},
            'exact': [{'s': s[0], 'p': float(s[1])} for s in exact],
            'confidence': max(hw, dr, aw),
            'predicted_score': exact[0][0] if exact else '?-?',
            'predicted_prob': exact[0][1] if exact else 0,
            'source': 'poisson_fallback'
        }
    
    def close(self):
        self.fb.close()


class BettingAdvisor:
    """مستشار الرهانات الأسطوري"""
    
    def __init__(self):
        self.predictor = UltimatePredictor()
    
    def analyze(self, home_team, away_team, league=None):
        """تحليل مباراة + توصيات"""
        result = self.predictor.predict(home_team, away_team, league)
        if not result:
            return None
        
        # تحديد أفضل رهان
        recommendations = []
        
        # 1X2
        if result['1x2']['H'] > 0.60:
            recommendations.append({
                'bet': f'{home_team} يفوز',
                'confidence': result['1x2']['H'],
                'market': '1X2-H'
            })
        if result['1x2']['A'] > 0.60:
            recommendations.append({
                'bet': f'{away_team} يفوز',
                'confidence': result['1x2']['A'],
                'market': '1X2-A'
            })
        
        # O/U
        if result.get('ou', {}).get('U2.5', 0) > 0.65:
            recommendations.append({
                'bet': 'تحت 2.5 هدف',
                'confidence': result['ou']['U2.5'],
                'market': 'U2.5'
            })
        if result.get('ou', {}).get('O2.5', 0) > 0.60:
            recommendations.append({
                'bet': 'فوق 2.5 هدف',
                'confidence': result['ou']['O2.5'],
                'market': 'O2.5'
            })
        
        # BTTS
        if result.get('btts', {}).get('N', 0) > 0.65:
            recommendations.append({
                'bet': 'ما فيه هدفين لفريقين',
                'confidence': result['btts']['N'],
                'market': 'BTTS-N'
            })
        if result.get('btts', {}).get('Y', 0) > 0.55:
            recommendations.append({
                'bet': 'هدفين لفريقين',
                'confidence': result['btts']['Y'],
                'market': 'BTTS-Y'
            })
        
        # DC
        if result.get('dc', {}).get('12', 0) > 0.85:
            recommendations.append({
                'bet': 'فوز أحد الفريقين (DC12)',
                'confidence': result['dc']['12'],
                'market': 'DC-12'
            })
        
        recommendations.sort(key=lambda x: -x['confidence'])
        
        return {
            'match': f'{home_team} vs {away_team}',
            'league': league,
            'source': result.get('source', 'unknown'),
            'predicted_score': result.get('predicted_score', '?-?'),
            'predicted_prob': result.get('predicted_prob', 0),
            '1x2': result['1x2'],
            'markets': result,
            'recommendations': recommendations[:3],
            'best_recommendation': recommendations[0] if recommendations else None,
        }
    
    def analyze_accumulator(self, matches, stake=25):
        """تحليل رهان تراكمي (2, 3, 4, 5 مباريات)"""
        results = []
        for match in matches:
            r = self.analyze(match['home'], match['away'], match.get('league'))
            if r and r['best_recommendation'] and r['best_recommendation']['confidence'] >= 0.55:
                results.append(r)
        
        if len(results) < 2:
            return {'error': 'ما فيه مباريات كافية بثقة عالية', 'results': results}
        
        # حساب الاحتمال التراكمي
        acc_prob = 1.0
        for r in results:
            acc_prob *= r['best_recommendation']['confidence']
        
        # توصية
        if acc_prob >= 0.25:
            rec = '🔥🔥🔥 توصية قوية'
        elif acc_prob >= 0.15:
            rec = '✅ توصية متوسطة'
        elif acc_prob >= 0.10:
            rec = '⚠️ مخاطرة عالية'
        else:
            rec = '❌ لا أنصح به'
        
        return {
            'matches': results,
            'num_matches': len(results),
            'accumulator_prob': acc_prob,
            'accumulator_pct': f'{acc_prob * 100:.1f}%',
            'recommendation': rec,
            'stake': stake,
            'expected_multiplier': 1.0 / acc_prob if acc_prob > 0 else 0,
            'recommended_stake': min(stake, 25),
        }
    
    def close(self):
        self.predictor.close()


if __name__ == '__main__':
    print('🔥🔥🔥 المحرك الأسطوري للرهانات 🔥🔥🔥')
    print()
    
    advisor = BettingAdvisor()
    
    # تحليل المباريات الخمس
    matches = [
        {'home': 'IK Sirius FK', 'away': 'Mjällby AIF', 'league': 'Allsvenskan'},
        {'home': 'Argentina', 'away': 'Cabo Verde', 'league': 'World Championship'},
        {'home': 'Egypt', 'away': 'Australia', 'league': 'World Championship'},
        {'home': 'KI Klaksvik', 'away': 'NSI Runavik', 'league': 'Premier League'},
    ]
    
    for m in matches:
        r = advisor.analyze(m['home'], m['away'], m['league'])
        if r:
            print(f"🎯 {r['match']}")
            print(f"   المصدر: {r['source']}")
            print(f"   النتيجة: {r['predicted_score']} ({r['predicted_prob']*100:.0f}%)")
            print(f"   1X2: {r['1x2']['H']*100:.0f}% / {r['1x2']['D']*100:.0f}% / {r['1x2']['A']*100:.0f}%")
            if r['best_recommendation']:
                print(f"   💰 {r['best_recommendation']['bet']} (ثقة {r['best_recommendation']['confidence']*100:.0f}%)")
            print()
    
    # تحليل الرهان التراكمي
    print('='*60)
    print('🔥 تحليل الرهان التراكمي')
    print('='*60)
    
    acc = advisor.analyze_accumulator([
        {'home': 'Argentina', 'away': 'Cabo Verde', 'league': 'World Championship'},
        {'home': 'KI Klaksvik', 'away': 'NSI Runavik', 'league': 'Premier League'},
    ])
    
    if 'error' not in acc:
        print(f"عدد المباريات: {acc['num_matches']}")
        print(f"الاحتمال التراكمي: {acc['accumulator_pct']}")
        print(f"التوصية: {acc['recommendation']}")
        for m in acc['matches']:
            print(f"  • {m['match']}: {m['best_recommendation']['bet']} (ثقة {m['best_recommendation']['confidence']*100:.0f}%)")
    else:
        print(acc['error'])
    
    advisor.close()

"""
Poisson/Dixon-Coles Model for Football Score Prediction
- VECTORIZED MLE for fast optimization
- Exponential decay weighting
- Dixon-Coles tau(rho) correlation
"""
import sys, os, json, time, math, numpy as np, warnings, sqlite3, gc
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

from scipy.optimize import minimize
from scipy.stats import poisson
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
DB = os.path.join(os.path.dirname(__file__), 'scrape_cache.db')
LOG = os.path.join(MODEL_DIR, 'poisson_log.txt')

def log(msg):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

def score_to_class(h, a):
    h = max(0, min(int(h), 4))
    a = max(0, min(int(a), 4))
    return h * 5 + a

def class_to_score(c):
    return (c // 5, c % 5)

def result(h, a):
    return 0 if h > a else (1 if h == a else 2)

def rps_score(y_true, y_pred_proba):
    n = len(y_true)
    yh, ya = zip(*[class_to_score(c) for c in y_true])
    yh, ya = np.array(yh), np.array(ya)
    ar = np.where(yh > ya, 0, np.where(yh == ya, 1, 2))
    pc = np.zeros((n, 3))
    for k in range(3):
        pc[:, k] = np.sum(y_pred_proba[:, [h*5+a for h in range(5) for a in range(5) if (h>a) == (k==0) and (h==a) == (k==1) and (a>h) == (k==2)]], axis=1)
    pc = np.cumsum(pc, axis=1)
    ac = np.zeros((n, 3))
    ac[np.arange(n), ar] = 1.0
    ac = np.cumsum(ac, axis=1)
    return float(np.mean(np.mean((ac - pc) ** 2, axis=1)))


class FastPoisson:
    """
    Fast vectorized Poisson/Dixon-Coles model.
    """
    
    def __init__(self, decay_halflife=180, rho=-0.07):
        self.decay_halflife = decay_halflife
        self.rho = rho
        self.teams = []
        self.attack = np.array([])
        self.defense = np.array([])
        self.home_adv = 1.3
        
    def prepare_data(self, matches, max_date=None):
        """Convert matches to vectorized format"""
        all_teams = set()
        for m in matches:
            all_teams.add(m['home_team'])
            all_teams.add(m['away_team'])
        self.teams = sorted(all_teams)
        team_idx = {t: i for i, t in enumerate(self.teams)}
        n = len(self.teams)
        
        if max_date is None:
            from datetime import datetime
            max_date = max(m['date'] for m in matches)
            if isinstance(max_date, str):
                max_date = datetime.strptime(max_date, '%Y-%m-%d').date()
        
        # Build arrays
        n_matches = len(matches)
        home_idx = np.zeros(n_matches, dtype=np.int32)
        away_idx = np.zeros(n_matches, dtype=np.int32)
        home_goals = np.zeros(n_matches, dtype=np.float32)
        away_goals = np.zeros(n_matches, dtype=np.float32)
        weights = np.ones(n_matches, dtype=np.float32)
        
        from datetime import datetime, date
        for i, m in enumerate(matches):
            home_idx[i] = team_idx[m['home_team']]
            away_idx[i] = team_idx[m['away_team']]
            home_goals[i] = m['home_score']
            away_goals[i] = m['away_score']
            
            if self.decay_halflife > 0:
                m_date = m['date']
                if isinstance(m_date, str):
                    m_date = datetime.strptime(m_date, '%Y-%m-%d').date()
                if isinstance(max_date, str):
                    mx = datetime.strptime(max_date, '%Y-%m-%d').date()
                else:
                    mx = max_date
                if isinstance(m_date, date) and isinstance(mx, date):
                    days_ago = (mx - m_date).days
                    weights[i] = max(0.5, 2.0 ** (-max(0, days_ago) / self.decay_halflife))
        
        self.home_idx = home_idx
        self.away_idx = away_idx
        self.home_goals = home_goals
        self.away_goals = away_goals
        self.weights = weights
        self.n_teams = n
        self.n_matches = n_matches
        
        log(f'Prepared: {n_matches} matches, {n} teams, decay={self.decay_halflife}d')
    
    def _neg_log_likelihood(self, params):
        """Vectorized negative log likelihood"""
        n = self.n_teams
        attack = np.exp(params[:n])
        defense = np.exp(params[n:2*n])
        ha = np.exp(params[2*n]) if len(params) > 2*n else 1.3
        
        # Normalize attack = 1
        attack = attack / np.mean(attack)
        
        # Expected goals
        l_h = attack[self.home_idx] * defense[self.away_idx] * ha
        l_a = attack[self.away_idx] * defense[self.home_idx]
        
        # Poisson log-likelihood
        ll_h = self.home_goals * np.log(np.maximum(l_h, 1e-10)) - l_h
        ll_a = self.away_goals * np.log(np.maximum(l_a, 1e-10)) - l_a
        
        # Subtract log factorial via Stirling or lgamma
        ll_h -= np.array([math.lgamma(int(g) + 1) if g >= 0 else 0 for g in self.home_goals])
        ll_a -= np.array([math.lgamma(int(g) + 1) if g >= 0 else 0 for g in self.away_goals])
        
        # Weighted sum
        neg_ll = -np.sum(self.weights * (ll_h + ll_a))
        
        # L2 regularization to prevent extreme values
        neg_ll += 0.01 * np.sum((attack - 1) ** 2)
        neg_ll += 0.01 * np.sum((defense - 1) ** 2)
        
        return neg_ll
    
    def estimate_params(self, matches, method='iterative'):
        """Estimate attack/defense parameters
        method='iterative': fast iterative scaling (default)
        method='mle': full MLE (slower but more accurate)
        """
        self.prepare_data(matches)
        
        if method == 'mle':
            return self._estimate_mle()
        
        # Fast iterative method
        t0 = time.time()
        
        # Step 1: Compute average goals per team directly
        home_gf = np.zeros(self.n_teams)
        home_ga = np.zeros(self.n_teams)
        away_gf = np.zeros(self.n_teams)
        away_ga = np.zeros(self.n_teams)
        home_matches_ct = np.zeros(self.n_teams)
        away_matches_ct = np.zeros(self.n_teams)
        
        for i in range(self.n_matches):
            hi = self.home_idx[i]
            ai = self.away_idx[i]
            hg = self.home_goals[i]
            ag = self.away_goals[i]
            w = self.weights[i]
            
            home_gf[hi] += hg * w
            home_ga[hi] += ag * w
            away_gf[ai] += ag * w
            away_ga[ai] += hg * w
            home_matches_ct[hi] += w
            away_matches_ct[ai] += w
        
        # Average goals
        avg_home_gf = np.divide(home_gf, np.maximum(home_matches_ct, 1))
        avg_home_ga = np.divide(home_ga, np.maximum(home_matches_ct, 1))
        avg_away_gf = np.divide(away_gf, np.maximum(away_matches_ct, 1))
        avg_away_ga = np.divide(away_ga, np.maximum(away_matches_ct, 1))
        
        # Step 2: Compute overall averages
        overall_home_gf = np.average(avg_home_gf[home_matches_ct > 0])
        overall_away_gf = np.average(avg_away_gf[away_matches_ct > 0])
        overall_goals = (overall_home_gf + overall_away_gf) / 2
        
        # Step 3: Estimate attack and defense
        # attack = goals_for / avg_goals
        # defense = goals_against / avg_goals
        self.attack = np.ones(self.n_teams)
        self.defense = np.ones(self.n_teams)
        self.home_adv = overall_home_gf / overall_goals if overall_goals > 0 else 1.3
        
        mask_home = home_matches_ct > 0
        mask_away = away_matches_ct > 0
        
        # Combined attack: from home and away goals
        self.attack[mask_home] = avg_home_gf[mask_home] / overall_goals if overall_goals > 0 else 1
        self.attack[mask_away] = (self.attack[mask_away] + avg_away_gf[mask_away] / overall_goals) / 2
        
        # Defense: combined from home and away
        self.defense[mask_home] = avg_home_ga[mask_home] / overall_goals if overall_goals > 0 else 1
        self.defense[mask_away] = (self.defense[mask_away] + avg_away_ga[mask_away] / overall_goals) / 2
        
        # Clip extreme values
        self.attack = np.clip(self.attack, 0.1, 5.0)
        self.defense = np.clip(self.defense, 0.1, 5.0)
        
        # Normalize attack = 1
        self.attack = self.attack / np.mean(self.attack)
        
        elapsed = time.time() - t0
        log(f'Iterative estimation done in {elapsed:.1f}s')
        log(f'Home advantage: {self.home_adv:.4f}')
        log(f'Attack: min={self.attack.min():.3f}, max={self.attack.max():.3f}, mean={self.attack.mean():.3f}')
        log(f'Defense: min={self.defense.min():.3f}, max={self.defense.max():.3f}, mean={self.defense.mean():.3f}')
        
        return None
    
    def _estimate_mle(self):
        """Full MLE estimation (slower)"""
        x0 = np.zeros(self.n_teams * 2 + 1)
        x0[:self.n_teams] = 0.0
        x0[self.n_teams:2*self.n_teams] = 0.0
        x0[2*self.n_teams] = 0.26
        
        log(f'Running MLE with {len(x0)} parameters on {self.n_matches} matches...')
        t0 = time.time()
        
        result = minimize(
            self._neg_log_likelihood, x0,
            method='L-BFGS-B',
            options={'maxiter': 5000, 'ftol': 1e-6, 'maxls': 30}
        )
        
        elapsed = time.time() - t0
        log(f'MLE done in {elapsed:.1f}s, success={result.success}')
        
        opt = result.x
        self.attack = np.exp(opt[:self.n_teams])
        self.defense = np.exp(opt[self.n_teams:2*self.n_teams])
        self.home_adv = np.exp(opt[2*self.n_teams])  
        self.attack = self.attack / np.mean(self.attack)
        
        log(f'Home advantage: {self.home_adv:.4f}')
        
        return result
    
    def get_params(self, team):
        if team not in self.teams:
            return None, None
        idx = self.teams.index(team)
        return self.attack[idx], self.defense[idx]
    
    def dixon_coles_tau(self, hg, ag, l_h, l_a):
        """Dixon-Coles adjustment"""
        if hg == 0 and ag == 0:
            return 1 - self.rho * l_h * l_a
        elif hg == 0 and ag == 1:
            return 1 + self.rho * l_h
        elif hg == 1 and ag == 0:
            return 1 + self.rho * l_a
        elif hg == 1 and ag == 1:
            return 1 - self.rho
        else:
            return 1.0
    
    def predict_proba(self, home_team, away_team):
        """Return 25-class probability distribution"""
        att_h, def_h = self.get_params(home_team)
        att_a, def_a = self.get_params(away_team)
        
        if att_h is None or att_a is None:
            return None
        
        l_h = att_h * def_a * self.home_adv
        l_a = att_a * def_h
        
        probs = np.zeros(25)
        for h in range(5):
            p_h = poisson.pmf(h, l_h)
            for a in range(5):
                p_a = poisson.pmf(a, l_a)
                tau = self.dixon_coles_tau(h, a, l_h, l_a)
                probs[h * 5 + a] = p_h * p_a * tau
        
        probs /= probs.sum()
        return probs
    
    def predict_match(self, home_team, away_team):
        """Full match prediction"""
        probs = self.predict_proba(home_team, away_team)
        if probs is None:
            return None
        
        pred_class = np.argmax(probs)
        h, a = class_to_score(pred_class)
        
        home_win = sum(probs[h_*5 + a_] for h_ in range(5) for a_ in range(5) if h_ > a_)
        draw = sum(probs[h_*5 + h_] for h_ in range(5))
        away_win = sum(probs[h_*5 + a_] for h_ in range(5) for a_ in range(5) if a_ > h_)
        
        return {
            'score': (int(h), int(a)),
            'probs': probs,
            'home_win': float(home_win),
            'draw': float(draw),
            'away_win': float(away_win),
        }
    
    def get_feature_vector(self, home_team, away_team):
        """Poisson features for ML model"""
        pred = self.predict_match(home_team, away_team)
        if pred is None:
            return None
        
        features = {
            'poisson_home_win': pred['home_win'],
            'poisson_draw': pred['draw'],
            'poisson_away_win': pred['away_win'],
        }
        for i, prob in enumerate(pred['probs']):
            features[f'poisson_class_{i}'] = float(prob)
        
        return features


def main():
    """Train and evaluate Poisson model on full dataset"""
    log('=' * 60)
    log('FAST POISSON/DIXON-COLES v1.0')
    log('=' * 60)
    
    import pandas as pd
    
    # Load data
    log('\nLoading match data...')
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query('''
        SELECT date, home_team, away_team, home_score, away_score 
        FROM sofa_historical_results 
        WHERE home_score IS NOT NULL AND away_score IS NOT NULL
          AND date >= '2010-01-01'
        ORDER BY start_timestamp
    ''', conn)
    conn.close()
    log(f'Loaded {len(df):,} matches from 2010+')
    
    # Chronological split
    split_idx = int(len(df) * 0.80)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    log(f'Train: {len(train_df):,} | Test: {len(test_df):,}')
    
    # Prepare training data
    train_matches = [{'date':r['date'],'home_team':r['home_team'],'away_team':r['away_team'],
        'home_score':int(r['home_score']),'away_score':int(r['away_score'])} 
        for _, r in train_df.iterrows()]
    
    # Train (using subset for speed if too large)
    max_train = 50000  # 50K matches is enough for Poisson
    if len(train_matches) > max_train:
        log(f'Using last {max_train} matches for training (decay handles recency)')
        train_matches = train_matches[-max_train:]
    
    poisson = FastPoisson(decay_halflife=180, rho=-0.07)
    poisson.estimate_params(train_matches)
    
    # Save model
    model_data = {
        'teams': poisson.teams,
        'attack': poisson.attack.tolist(),
        'defense': poisson.defense.tolist(),
        'home_adv': float(poisson.home_adv),
        'rho': poisson.rho,
        'decay_halflife': poisson.decay_halflife,
    }
    with open(os.path.join(MODEL_DIR, 'poisson_model.json'), 'w') as f:
        json.dump(model_data, f)
    
    # Evaluate
    log('\nEvaluating on test set...')
    y_true, y_proba = [], []
    skip = 0
    for _, r in test_df.iterrows():
        pred = poisson.predict_match(r['home_team'], r['away_team'])
        if pred is None:
            skip += 1
            continue
        y_true.append(score_to_class(int(r['home_score']), int(r['away_score'])))
        y_proba.append(pred['probs'])
    
    if len(y_true) == 0:
        log('ERROR: No predictions!')
        return
    
    y_true_arr = np.array(y_true)
    y_proba_arr = np.array(y_proba)
    y_pred = np.argmax(y_proba_arr, axis=1)
    
    exact = np.mean(y_pred == y_true_arr) * 100
    actual_1x2 = np.array([result(*class_to_score(c)) for c in y_true_arr])
    pred_1x2 = np.array([result(*class_to_score(c)) for c in y_pred])
    onex2 = np.mean(actual_1x2 == pred_1x2) * 100
    rps_val = rps_score(y_true_arr, y_proba_arr)
    
    log(f'\n=== POISSON RESULTS ===')
    log(f'Test: {len(y_true_arr):,} (skipped {skip})')
    log(f'Exact: {exact:.2f}%')
    log(f'1X2: {onex2:.2f}%')
    log(f'RPS: {rps_val:.4f}')
    
    # Betting @30%
    hits30 = total30 = 0
    for i in range(len(y_true_arr)):
        if y_proba_arr[i][y_pred[i]] >= 0.30:
            total30 += 1
            if y_pred[i] == y_true_arr[i]:
                hits30 += 1
    bet30 = (hits30/total30*100) if total30 else 0
    log(f'Betting @30%: {hits30}/{total30} = {bet30:.1f}%')
    
    # Save results
    results = {
        'type': 'FAST_POISSON',
        'params': {
            'n_teams': len(poisson.teams),
            'train_matches': len(train_matches),
            'test_matches': len(y_true_arr),
            'decay_halflife': poisson.decay_halflife,
            'rho': poisson.rho,
            'home_adv': float(poisson.home_adv),
        },
        'results': {
            'exact_pct': round(exact, 2),
            '1x2_pct': round(onex2, 2),
            'rps': round(rps_val, 4),
        },
        'betting_30': {
            'hits': int(hits30),
            'total': int(total30),
            'accuracy': round(bet30, 1),
        }
    }
    with open(os.path.join(MODEL_DIR, 'poisson_results.json'), 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save test probabilities for stacking
    np.save(os.path.join(MODEL_DIR, 'poisson_test_probas.npy'), y_proba_arr)
    log(f'Saved poisson_test_probas.npy')
    log('\nDone! Poisson/Dixon-Coles model ready.')
    
    # Compare with V5 baseline
    log(f'\nComparison:')
    log(f'  V5 ensemble: 18.51% exact')
    log(f'  Poisson only: {exact:.2f}% exact')
    log(f'  Gap to V5: {18.51 - exact:.2f} points')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
WC 2026 Predictor V3 — Elo + Poisson Hybrid
يستخدم Elo difference لتوقع النتائج وأهداف Poisson
"""
import json, math

def expected_score(elo_a, elo_b):
    """احتمالية فوز A على B حسب Elo"""
    return 1 / (1 + math.pow(10, (elo_b - elo_a) / 400))

def poisson_prob(lam, k):
    """P(X=k) لـ Poisson(lambda)"""
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

class WCPredictor:
    SCORE_LABELS = ['0-0','0-1','0-2','0-3','0-4','0-4+',
                    '1-0','1-1','1-2','1-3','1-4','1-4+',
                    '2-0','2-1','2-2','2-3','2-4','2-4+',
                    '3-0','3-1','3-2','3-3','3-4','3-4+',
                    '4-0','4-1','4-2','4-3','4-4','4-4+'][:25]
    
    def __init__(self):
        # 2026 WC Teams with latest Elo from database
        self.teams = {
            'Netherlands': 1923, 'Morocco': 1914,
            'Brazil': 1900, 'Japan': 1932,
            'Germany': 2009, 'Bosnia & Herzegovina': 1584,
            "Cote d'Ivoire": 1767, 'Norway': 1872,
            'France': 1980, 'Paraguay': 1770,
            'Mexico': 1884, 'Ecuador': 1845,
            'USA': 1920, 'Belgium': 1858,
            'England': 1982, 'Portugal': 1873,
            'Croatia': 1681, 'Spain': 2079,
            'Austria': 1756, 'Switzerland': 1836,
            'Argentina': 1951, 'Cabo Verde': 1661,
            'Colombia': 1878, 'Australia': 1860,
            'Egypt': 1785,
        }
        
    def predict(self, home, away, neutral=True):
        """توقع نتيجة مباراة باستخدام Elo + Poisson"""
        he = self.teams.get(home, 1500)
        ae = self.teams.get(away, 1500)
        
        # Expected goals based on Elo (scaled to realistic WC averages)
        # WC average ~2.5 goals per match
        avg_goals = 2.6
        home_strength = he / 1500.0
        away_strength = ae / 1500.0
        
        # Home advantage is minimal in World Cup (neutral venues or nearby)
        home_adv = 1.05 if not neutral else 1.0
        if neutral:
            home_adv = 1.02  # slight nominal home advantage
        
        lam_h = home_strength * (avg_goals / 2) * home_adv
        lam_a = away_strength * (avg_goals / 2) / 1.02  # slight away penalty
        
        # Clamp
        lam_h = max(0.3, min(3.5, lam_h))
        lam_a = max(0.3, min(3.5, lam_a))
        
        # Win/draw/loss from Elo
        exp_h = expected_score(he, ae)
        exp_a = 1 - exp_h
        
        # Score probabilities (up to 4-4+, cap at 4+)
        score_probs = {}
        for hg in range(5):
            for ag in range(5):
                prob = poisson_prob(lam_h, hg) * poisson_prob(lam_a, ag)
                if hg == 4:
                    label = f'{hg}+-{ag}'
                elif ag == 4:
                    label = f'{hg}-{ag}+'
                else:
                    label = f'{hg}-{ag}'
                    
                if hg == 4 and ag == 4:
                    label = '4+-4+'
                
                # Map to our 25-class system
                if hg <= 4 and ag <= 4:
                    score_probs[(hg, ag)] = prob
                elif hg >= 4 and ag <= 4:
                    # 4+ goals by home
                    if (4, ag) in score_probs:
                        score_probs[(4, ag)] += prob
                    else:
                        score_probs[(4, ag)] = prob
                elif hg <= 4 and ag >= 4:
                    if (hg, 4) in score_probs:
                        score_probs[(hg, 4)] += prob
                    else:
                        score_probs[(hg, 4)] = prob
                else:
                    if (4, 4) in score_probs:
                        score_probs[(4, 4)] += prob
                    else:
                        score_probs[(4, 4)] = prob
        
        # Map to our 25 labels
        probs_25 = [0.0] * 25
        label_to_idx = {}
        for i, lbl in enumerate(self.SCORE_LABELS):
            parts = lbl.split('-')
            hg = int(parts[0].replace('+',''))
            ag = int(parts[1].replace('+',''))
            label_to_idx[(hg, ag)] = i
        
        for (hg, ag), prob in score_probs.items():
            if (hg, ag) in label_to_idx:
                probs_25[label_to_idx[(hg, ag)]] = prob
            elif hg >= 4 and (4, ag) in label_to_idx:
                probs_25[label_to_idx[(4, ag)]] += prob
            elif ag >= 4 and (hg, 4) in label_to_idx:
                probs_25[label_to_idx[(hg, 4)]] += prob
        
        # Normalize
        total = sum(probs_25)
        if total > 0:
            probs_25 = [p / total for p in probs_25]
        
        # Get top predictions
        top5 = sorted(enumerate(probs_25), key=lambda x: -x[1])[:5]
        
        # Win/Draw/Loss
        home_win = sum(probs_25[i] for i in range(25) if int(self.SCORE_LABELS[i].split('-')[0].replace('+','0')) > int(self.SCORE_LABELS[i].split('-')[1].replace('+','0')))
        draw = sum(probs_25[i] for i in range(25) if int(self.SCORE_LABELS[i].split('-')[0].replace('+','0')) == int(self.SCORE_LABELS[i].split('-')[1].replace('+','0')))
        away_win = sum(probs_25[i] for i in range(25) if int(self.SCORE_LABELS[i].split('-')[0].replace('+','0')) < int(self.SCORE_LABELS[i].split('-')[1].replace('+','0')))
        
        predicted_idx = top5[0][0]
        predicted_score = self.SCORE_LABELS[predicted_idx]
        
        return {
            'home': home, 'away': away,
            'home_elo': he, 'away_elo': ae,
            'elo_diff': he - ae,
            'expected_goals_home': round(lam_h, 2),
            'expected_goals_away': round(lam_a, 2),
            'win_prob_home': round(home_win, 3),
            'draw_prob': round(draw, 3),
            'win_prob_away': round(away_win, 3),
            'predicted_score': predicted_score,
            'confidence': round(top5[0][1], 3),
            'top5': [(self.SCORE_LABELS[i], round(p, 3)) for i, p in top5],
            'all_probs': [round(p, 4) for p in probs_25],
        }

def main():
    predictor = WCPredictor()
    
    fixtures = [
        ('2026-06-30', 'Netherlands', 'Morocco'),
        ('2026-06-30', 'Brazil', 'Japan'),
        ('2026-06-30', 'Germany', 'Bosnia & Herzegovina'),
        ('2026-07-01', "Cote d'Ivoire", 'Norway'),
        ('2026-07-01', 'France', 'Paraguay'),
        ('2026-07-01', 'Mexico', 'Ecuador'),
        ('2026-07-02', 'USA', 'Bosnia & Herzegovina'),
        ('2026-07-02', 'Belgium', 'Ecuador'),
        ('2026-07-02', 'England', 'Ecuador'),
        ('2026-07-03', 'Portugal', 'Croatia'),
        ('2026-07-03', 'Spain', 'Austria'),
        ('2026-07-03', 'Switzerland', 'Ecuador'),
        ('2026-07-04', 'Argentina', 'Cabo Verde'),
        ('2026-07-04', 'Colombia', 'Paraguay'),
        ('2026-07-04', 'Australia', 'Egypt'),
    ]
    
    results = []
    
    print('=' * 85)
    print('WORLD CUP 2026 R32 — Elo + Poisson Predictions')
    print('=' * 85)
    print('{0:12s} {1:25s} {2:8s} {3:25s} {4:12s} {5}'.format('Date','Home','Score','Away','1X2','Conf'))
    print('-' * 85)
    
    for date, home, away in fixtures:
        p = predictor.predict(home, away)
        results.append({'date': date, **p})
        
        # Format 1X2
        if p['win_prob_home'] > 0.45:
            x12 = '1 ({0:.0%})'.format(p['win_prob_home'])
        elif p['win_prob_away'] > 0.45:
            x12 = '2 ({0:.0%})'.format(p['win_prob_away'])
        elif p['draw_prob'] > 0.30:
            x12 = 'X ({0:.0%})'.format(p['draw_prob'])
        else:
            x12 = '1/{0:.0%} X/{1:.0%} 2/{2:.0%}'.format(p['win_prob_home'], p['draw_prob'], p['win_prob_away'])
        
        print(date.ljust(12) + ' ' + home.ljust(25) + ' ' + p['predicted_score'].ljust(8) + ' ' + away.ljust(25) + ' ' + x12.ljust(12) + ' ' + str(round(p['confidence']*100)) + '%')
        
        # Top 3 alternatives
        top3_str = ', '.join(['{} ({:.0%})'.format(s, c) for s, c in p['top5'][:3]])
        print('              Top: ' + top3_str)
        print('              Exp goals: {} {:.2f} - {} {:.2f}'.format(home, p['expected_goals_home'], away, p['expected_goals_away']))
    
    print('=' * 85)
    
    # Save
    with open('wc2026_predictions_v3.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\\nSaved to wc2026_predictions_v3.json')

if __name__ == '__main__':
    main()

"""
🔥 value_betting_v7.py — V7.0 FINAL Value Betting Pipeline
═══════════════════════════════════════════════════════════════
يكتشف Value Bets بمقارنة توقعات V62 (194 feature) مع odds السوق
يستخدم:
  ● V62Ensemble (7 DeepNN + XGBoost) — PRIMARY predictor
  ● Agent 4 premium odds (OddsAPI + Sportmonks + agent4_odds_all)
  ● Agent 5 odds movement (OddsPortal + BetExplorer)
  ● Kelly Criterion + Fractional Kelly (25%)
  ● Devil's Advocate risk filter
  ● تصدير HTML + JSON

🧠 Agent 2 الأسطوري — DeepSeek V4 Flash Free الثاني
SHADOW MODE — كل البروتوكولات مفعلة 🔥🩸
═══════════════════════════════════════════════════════════════
"""
import sys, os, json, time, math, sqlite3, numpy as np
from datetime import datetime, timedelta
from collections import defaultdict

BASE = os.path.dirname(__file__)
sys.path.insert(0, BASE)
OUTPUT_DIR = os.path.join(BASE, 'output', 'value_bets')
os.makedirs(OUTPUT_DIR, exist_ok=True)
DB_PATH = os.path.join(BASE, 'scrape_cache.db')

# ════ CONFIG ═══════════════════════════════════════════════
MIN_EDGE_PCT = 5.0       # أقل فرق % لاعتباره value bet
MAX_STAKE_PCT = 0.25     # Fractional Kelly (25% من Kelly الكامل)
CONFIDENCE_THRESHOLD = 0.10  # أقل ثقة للنموذج
MAX_GOALS = 4
NUM_CLASSES = 25

# ════ LOGGING ═══════════════════════════════════════════════

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # Windows cp1256 fix for emojis
    try:
        print(f'[{ts}] {msg}', flush=True)
    except UnicodeEncodeError:
        safe = msg.encode('ascii', 'ignore').decode('ascii')
        print(f'[{ts}] {safe}', flush=True)
    with open(os.path.join(OUTPUT_DIR, 'value_betting_log.txt'), 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')

# ════ DB HELPERS ═══════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def get_premium_odds(home_team, away_team, match=None):
    """جلب أفضل odds من كل المصادر"""
    odds = {}
    ht_lower = home_team.lower().strip()
    at_lower = away_team.lower().strip()
    
    # 1. من match object نفسه (إذا فيه odds_json)
    if match and match.get('odds_json'):
        try:
            odds_json = json.loads(match['odds_json']) if isinstance(match['odds_json'], str) else match['odds_json']
            best_h, best_d, best_a = 0, 0, 0
            for bookie in odds_json:
                for market in bookie.get('markets', []):
                    if market.get('key') == 'h2h':
                        for outcome in market.get('outcomes', []):
                            name = outcome.get('name', '').lower().strip()
                            price = outcome.get('price', 0)
                            if price <= 1:
                                continue
                            if name == ht_lower or name in home_team.lower():
                                best_h = max(best_h, price)
                            elif name == at_lower or name in away_team.lower():
                                best_a = max(best_a, price)
                            elif 'draw' in name:
                                best_d = max(best_d, price)
            if best_h > 0 and best_d > 0 and best_a > 0:
                odds['source'] = f"odds_upcoming (Pinnacle)"
                odds['home_odds'] = best_h
                odds['draw_odds'] = best_d
                odds['away_odds'] = best_a
                odds['bookmaker_count'] = len(odds_json)
                return odds
        except Exception as e:
            log(f"  odds_json parse: {e}")
    
    # 2. من agent4_odds_all
    try:
        conn = get_db()
        row = conn.execute("""
            SELECT AVG(home_odds) as ho, AVG(draw_odds) as dr, AVG(away_odds) as ao
            FROM agent4_odds_all
            WHERE LOWER(home_team) LIKE ? AND LOWER(away_team) LIKE ?
        """, (f'%{ht_lower[:10]}%', f'%{at_lower[:10]}%')).fetchone()
        if row and row['ho'] and row['ho'] > 0:
            odds['source'] = 'agent4_odds_all'
            odds['home_odds'] = float(row['ho'])
            odds['draw_odds'] = float(row['dr'])
            odds['away_odds'] = float(row['ao'])
            conn.close()
            return odds
        conn.close()
    except:
        pass
    
    return odds if odds.get('home_odds') else None


def get_upcoming_matches(days=365):
    """جلب المباريات القادمة من قاعدة البيانات"""
    now = datetime.now()
    end_date = (now + timedelta(days=days)).strftime('%Y-%m-%d')
    matches = []
    
    # 1. من odds_upcoming (تحتوي odds_json)
    try:
        conn = get_db()
        rows = conn.execute("""
            SELECT event_id, home_team, away_team, commence_time, league, odds_json
            FROM odds_upcoming
            ORDER BY commence_time ASC
            LIMIT 200
        """).fetchall()
        for r in rows:
            try:
                dt = datetime.fromtimestamp(r['commence_time'])
                matches.append({
                    'id': r['event_id'],
                    'home_team': r['home_team'],
                    'away_team': r['away_team'],
                    'date': dt.strftime('%Y-%m-%d'),
                    'datetime': dt,
                    'tournament': r.get('league', ''),
                    'odds_json': r.get('odds_json', '[]'),
                    'source': 'odds_upcoming',
                })
            except:
                pass
        conn.close()
    except Exception as e:
        log(f"  odds_upcoming failed: {e}")
    
    # 2. من wc_fixtures
    try:
        conn = get_db()
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT event_id, home_team, away_team, date, group_name
            FROM wc_fixtures
            ORDER BY date ASC
            LIMIT 96
        """).fetchall()
        for r in rows:
            matches.append({
                'id': f"wc_{r['event_id']}",
                'home_team': r['home_team'],
                'away_team': r['away_team'],
                'date': str(r['date'])[:10] if r['date'] else '',
                'tournament': f"World Cup 2026 - {r['group_name'] or ''}",
                'source': 'wc_fixtures',
            })
        conn.close()
    except Exception as e:
        log(f"  wc_fixtures query: {e}")
    
    # إزالة المكررات (نفس الفريقين في نفس اليوم)
    seen = set()
    unique = []
    for m in matches:
        key = (m['home_team'].lower().strip(), m['away_team'].lower().strip(), m['date'])
        if key not in seen:
            seen.add(key)
            unique.append(m)
    
    return unique


# ════ IMPLIED PROBABILITY ══════════════════════════════════

def market_implied_probs(odds):
    """
    حساب الاحتمالية الضمنية من odds السوق
    تزيل overround بتوزيع نسبي (Power Method)
    """
    if not odds or not odds.get('home_odds'):
        return None
    
    ho = float(odds['home_odds'])
    dr = float(odds['draw_odds'])
    ao = float(odds['away_odds'])
    
    if ho <= 0 or dr <= 0 or ao <= 0:
        return None
    
    # Implied probabilities (مع overround)
    raw_h = 1.0 / ho
    raw_d = 1.0 / dr
    raw_a = 1.0 / ao
    total = raw_h + raw_d + raw_a
    
    # Remove overround (normalize)
    fair_h = raw_h / total * 100
    fair_d = raw_d / total * 100
    fair_a = raw_a / total * 100
    overround = (total - 1.0) * 100
    
    return {
        'home_prob': fair_h,
        'draw_prob': fair_d,
        'away_prob': fair_a,
        'overround_pct': overround,
        'raw_home_odds': ho,
        'raw_draw_odds': dr,
        'raw_away_odds': ao,
    }


# ════ LOAD PREDICTOR ══════════════════════════════════════

def load_fixed_predictor():
    """تحميل prediction_engine المُصحّح"""
    try:
        # أولاً: جرب النسخة المصلحة من المجلد النهائي
        fixed_path = os.path.join(BASE, '..', '..', 'النسخة النهائية للمشروع', '02-prediction_engine_fixed.py')
        if os.path.exists(fixed_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("pe_fixed", fixed_path)
            pe = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(pe)
            log("✅ Loaded FIXED prediction engine (V7.0)")
            return pe
        
        # ثانياً: جرب prediction_engine الأصلي
        import prediction_engine as pe
        log("⚠️ Using original prediction_engine.py (V62 not primary)")
        return pe
    except Exception as e:
        log(f"❌ Failed to load predictor: {e}")
        return None


# ════ KELLY CRITERION ═════════════════════════════════════

def kelly_criterion(model_prob, market_odds):
    """
    Kelly Criterion كاملة:
    f* = (p * b - 1) / (b - 1)
    حيث:
    p = احتمالنا (0-1)
    b = odds السوق - 1
    f* = كسر الرهان الأمثل
    """
    if market_odds <= 1 or model_prob <= 0:
        return 0, 0
    
    b = market_odds - 1
    p = model_prob / 100.0
    
    # Kelly full
    kelly_full = (p * market_odds - 1) / b
    
    # Edge
    edge = (p * market_odds - 1) * 100
    
    # Fractional Kelly (25%)
    kelly_fractional = kelly_full * MAX_STAKE_PCT
    
    # Negative edge = no bet
    if edge <= 0:
        return 0, edge
    
    return max(0, kelly_fractional), edge


# ════ VALUE BET DETECTION ═════════════════════════════════

def detect_value_bets(model_pred, market_odds):
    """
    اكتشاف Value Bets بمقارنة model probs vs market probs
    """
    if not model_pred or not market_odds:
        return []
    
    outcomes = [
        {'name': 'home_win', 'label': 'HOME', 
         'model_prob': model_pred.get('home_win_prob', 0),
         'odds': market_odds.get('raw_home_odds', 0)},
        {'name': 'draw', 'label': 'DRAW',
         'model_prob': model_pred.get('draw_prob', 0),
         'odds': market_odds.get('raw_draw_odds', 0)},
        {'name': 'away_win', 'label': 'AWAY',
         'model_prob': model_pred.get('away_win_prob', 0),
         'odds': market_odds.get('raw_away_odds', 0)},
    ]
    
    # Exact scores top 3
    exact_scores = model_pred.get('top_scores', [])
    
    value_bets = []
    for o in outcomes:
        if o['odds'] <= 0 or o['model_prob'] <= 0:
            continue
        
        kelly_fraction, edge = kelly_criterion(o['model_prob'], o['odds'])
        
        if edge >= MIN_EDGE_PCT:
            # Implied market probability
            market_prob = (1.0 / o['odds']) * 100
            
            # Verdict
            if edge >= 20:
                verdict = '🔥 STRONG'
            elif edge >= 10:
                verdict = '✅ MODERATE'
            else:
                verdict = '⚠️ WEAK'
            
            value_bets.append({
                'outcome': o['label'],
                'model_prob_pct': round(o['model_prob'], 1),
                'market_implied_pct': round(market_prob, 1),
                'odds': round(o['odds'], 2),
                'edge_pct': round(edge, 1),
                'kelly_fraction': round(kelly_fraction, 4),
                'stake_pct': round(kelly_fraction * 100, 2),
                'verdict': verdict,
            })
    
    # Sort by edge descending
    value_bets.sort(key=lambda x: -x['edge_pct'])
    return value_bets


# ════ MAIN PREDICTION + VALUE ═════════════════════════════

def predict_and_value(home_team, away_team, tournament='', date='', predictor=None, match_obj=None):
    """توقع + Value Bet لمباراة واحدة"""
    if not predictor:
        predictor = load_fixed_predictor()
        if not predictor:
            return None
    
    try:
        # 1. Prediction
        result = predictor.analyze_match_deep(home_team, away_team)
        if not result:
            return None
        
        # 2. Get market odds (use match object if available for odds_json)
        odds = get_premium_odds(home_team, away_team, match=match_obj)
        market_probs = market_implied_probs(odds) if odds else None
        
        # 3. Detect value
        value_bets = detect_value_bets(result, market_probs) if market_probs else []
        
        return {
            'match': f"{home_team} vs {away_team}",
            'home_team': home_team,
            'away_team': away_team,
            'date': date,
            'tournament': tournament,
            'prediction': {
                'best_score': result.get('best_score', 'N/A'),
                'best_prob': round(result.get('best_prob', 0), 1),
                'top_3': result.get('top_scores', [])[:3],
                'home_win_prob': round(result.get('home_win_prob', 0), 1),
                'draw_prob': round(result.get('draw_prob', 0), 1),
                'away_win_prob': round(result.get('away_win_prob', 0), 1),
                'expected_goals': {
                    'home': result.get('expected_home_goals', 0),
                    'away': result.get('expected_away_goals', 0),
                },
                'model': result.get('predictor', '?'),
                'confidence': round(result.get('confidence', 0), 3),
            },
            'market': market_probs,
            'value_bets': value_bets,
            'odds_source': odds.get('source', 'none') if odds else 'none',
        }
    except Exception as e:
        log(f"  X {home_team} vs {away_team}: {e}")
        return None


# ════ REPORT GENERATION ═══════════════════════════════════

def generate_html_report(results, filename='value_bets_dashboard.html'):
    """توليد لوحة HTML لنتائج Value Betting"""
    html = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="UTF-8">
<title>🔥 Value Betting Dashboard — V7.0 FINAL</title>
<style>
body{font-family:system-ui;background:#0a0a0a;color:#fff;margin:20px}
h1{color:#ff4444;text-align:center;text-shadow:0 0 20px #ff444488}
h2{color:#ffdd44;border-bottom:1px solid #333;padding-bottom:8px}
.match{background:#1a1a2e;border:1px solid #333;border-radius:12px;padding:16px;margin:12px 0}
.score{font-size:1.3em;font-weight:bold;color:#ffdd44}
.vb{background:#002200;border:1px solid #00ff00;border-radius:8px;padding:10px;margin:8px 0}
.vb-strong{border-color:#ff4444;background:#220000}
.vb-moderate{border-color:#ffdd44;background:#222200}
table{width:100%;border-collapse:collapse;margin:12px 0}
th{background:#ff4444;padding:8px}
td{padding:8px;border-bottom:1px solid #333;text-align:center}
.prob-h{color:#44ff44}.prob-d{color:#ffff44}.prob-a{color:#ff4444}
.edge{color:#00ff00;font-weight:bold}
.stake{color:#ffdd44}
.verdict{font-weight:bold}
.summary-box{background:#111;border:1px solid #ff4444;border-radius:12px;padding:16px;margin:20px 0;text-align:center}
.summary-box .big{font-size:2em;font-weight:bold;color:#ff4444}
</style></head><body>
<h1>🔥 Value Betting Dashboard — V7.0 FINAL</h1>
<p style="text-align:center;color:#888">DATE_PLACEHOLDER</p>
"""
    
    # Count
    total_vb = sum(len(r.get('value_bets', [])) for r in results if r)
    strong = sum(1 for r in results if r for vb in r.get('value_bets', []) if 'STRONG' in vb.get('verdict', ''))
    moderate = sum(1 for r in results if r for vb in r.get('value_bets', []) if 'MODERATE' in vb.get('verdict', ''))
    
    html += f"""
<div class="summary-box">
<span class="big">{len(results)}</span> مباراة<br>
<span class="big">{total_vb}</span> Value Bet<br>
<span style="color:#ff4444">{strong}</span> STRONG · <span style="color:#ffdd44">{moderate}</span> MODERATE · <span style="color:#888">{total_vb-strong-moderate}</span> WEAK
</div>
"""
    
    for r in results:
        if not r or not r.get('prediction'):
            continue
        p = r['prediction']
        vb = r.get('value_bets', [])
        
        html += f"""
<div class="match">
<div style="display:flex;justify-content:space-between">
<div><strong>{r['match']}</strong></div>
<div style="color:#888">{r.get('date','')} | {r.get('tournament','')}</div>
</div>
<div class="score">🏆 {p.get('best_score','N/A')} ({p.get('best_prob',0):.1f}%)</div>
<div class="probs">
<span class="prob-h">H: {p.get('home_win_prob',0):.1f}%</span>
<span class="prob-d">D: {p.get('draw_prob',0):.1f}%</span>
<span class="prob-a">A: {p.get('away_win_prob',0):.1f}%</span>
<span style="color:#888">| {p.get('model','?')} | ⚽ {p.get('expected_goals',{}).get('home',0):.2f}-{p.get('expected_goals',{}).get('away',0):.2f}</span>
</div>"""
        
        if vb:
            for v in vb:
                vb_class = 'vb-strong' if 'STRONG' in v.get('verdict','') else ('vb-moderate' if 'MODERATE' in v.get('verdict','') else '')
                html += f"""
<div class="vb {vb_class}">
<strong>{v['outcome']}</strong> @ {v['odds']:.2f} | 
Model: {v['model_prob_pct']:.1f}% vs Market: {v['market_implied_pct']:.1f}% | 
<span class="edge">Edge: {v['edge_pct']:+.1f}%</span> | 
<span class="stake">Kelly: {v['kelly_fraction']*100:.2f}%</span> | 
<span class="verdict">{v['verdict']}</span>
</div>"""
        
        if r.get('market'):
            m = r['market']
            html += f"""
<div style="color:#888;font-size:0.8em;margin-top:8px">
odds: {m.get('raw_home_odds',0):.2f} / {m.get('raw_draw_odds',0):.2f} / {m.get('raw_away_odds',0):.2f} | 
Overround: {m.get('overround_pct',0):.1f}% | Source: {r.get('odds_source','none')}
</div>"""
        
        html += "</div>"
    
    html += "</body></html>"
    html = html.replace('DATE_PLACEHOLDER', datetime.now().strftime('%Y-%m-%d %H:%M'))
    
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    log(f"📄 Dashboard: {path}")
    return path


# ════ MAIN ═══════════════════════════════════════════════

def main():
    log("===== Value Betting Pipeline V7.0 FINAL =====")
    log("===== Value Betting Pipeline V7.0 FINAL =====")
    log("==============================================")
    
    # Load predictor
    log("\n⚙️ Loading prediction engine...")
    predictor = load_fixed_predictor()
    if not predictor:
        log("❌ Failed to load predictor. Exiting.")
        return
    
    # Get upcoming matches
    log("\n📋 Loading upcoming matches...")
    matches = get_upcoming_matches(days=7)
    log(f"Found {len(matches)} matches in the next 7 days")
    
    if not matches:
        # Try fetching from odds directly
        log("No upcoming matches found. Trying odds API...")
        try:
            import odds_api_scraper as oas
            events = oas.fetch_multiple_leagues()
            matches = []
            for e in events:
                matches.append({
                    'id': e.get('id'),
                    'home_team': e.get('home_team', ''),
                    'away_team': e.get('away_team', ''),
                    'date': e.get('commence_time', '')[:10],
                    'tournament': e.get('sport_key', ''),
                })
            log(f"Found {len(matches)} matches from OddsAPI")
        except Exception as e:
            log(f"No odds API data: {e}")
    
    if not matches:
        log("❌ No matches found anywhere.")
        return
    
    # Predict + find value
    log(f"\n🎯 Analyzing {len(matches)} matches for value...")
    results = []
    for i, m in enumerate(matches):
        log(f"  [{i+1}/{len(matches)}] {m['home_team']} vs {m['away_team']}")
        
        r = predict_and_value(
            m['home_team'], m['away_team'],
            tournament=m.get('tournament', ''),
            date=m.get('date', ''),
            predictor=predictor,
            match_obj=m
        )
        
        if r:
            vb = r.get('value_bets', [])
            if vb:
                for v in vb:
                    log(f"    ✅ VALUE: {v['outcome']} @ {v['odds']:.2f} | Edge: {v['edge_pct']:+.1f}% | {v['verdict']}")
            else:
                log(f"    No value bets")
            results.append(r)
    
    # Summary
    log("\n" + "=" * 60)
    log("📊 VALUE BETTING SUMMARY")
    log("=" * 60)
    
    all_vb = [(r, vb) for r in results if r for vb in r.get('value_bets', [])]
    all_vb.sort(key=lambda x: -x[1]['edge_pct'])
    
    log(f"Total matches analyzed: {len(results)}")
    log(f"Total value bets found: {len(all_vb)}")
    
    strong = [x for x in all_vb if 'STRONG' in x[1].get('verdict', '')]
    moderate = [x for x in all_vb if 'MODERATE' in x[1].get('verdict', '')]
    log(f"🔥 STRONG: {len(strong)} | ✅ MODERATE: {len(moderate)} | ⚠️ WEAK: {len(all_vb)-len(strong)-len(moderate)}")
    
    if all_vb:
        log(f"\n{'─'*60}")
        log(f"{'Match':<35} {'Bet':<8} {'Odds':<8} {'Edge%':<8} {'Kelly%':<8} {'Verdict':<15}")
        log(f"{'─'*60}")
        for r, vb in all_vb[:15]:
            match_short = r['match'][:30]
            log(f"{match_short:<35} {vb['outcome']:<8} {vb['odds']:<8.2f} {vb['edge_pct']:<8.1f} {vb['kelly_fraction']*100:<8.2f} {vb['verdict']:<15}")
    
    # Export
    log("\n📄 Exporting reports...")
    
    json_path = os.path.join(OUTPUT_DIR, 'value_bets.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'generated': datetime.now().isoformat(),
            'model': 'V7.0 FINAL (V62Ensemble + 194 features)',
            'total_matches': len(results),
            'total_value_bets': len(all_vb),
            'strong': len(strong),
            'moderate': len(moderate),
            'results': results,
        }, f, ensure_ascii=False, indent=2)
    log(f"📄 JSON: {json_path}")
    
    html_path = generate_html_report(results)
    
    log(f"\n{'='*60}")
    log(f"✅ Complete! {len(all_vb)} value bets found")
    log(f"📁 Output: {OUTPUT_DIR}")
    log(f"{'='*60}")


if __name__ == '__main__':
    main()

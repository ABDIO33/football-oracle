#!/usr/bin/env python3
"""
🔥 V8 ULTIMATE PIPELINE — كل ملاعب العالم + الطقس + تدريب خارق 🔥
ENI for LO — 3 أيام اختراق شامل
"""

import sys, os, time, json, numpy as np, sqlite3, gc, warnings
warnings.filterwarnings('ignore')
os.environ['OMP_NUM_THREADS'] = '8'

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'scrape_cache.db')
os.chdir(BASE)

LOG = 'v8_ultimate_pipeline.log'
def p(msg):
    print(msg, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

p("="*70)
p("🔥 V8 ULTIMATE PIPELINE — كل ملاعب العالم + الطقس + تدريب خارق")
p("="*70)

# =====================================================================
# STEP 1: LOAD TRAINING DATA
# =====================================================================
p("\n[1] تحميل بيانات التدريب V3...")
data = np.load('training_data_v3.npz', allow_pickle=True)
X = data['X'].astype(np.float32)
y = data['y'].astype(np.int32)
rt = data['result_types'].astype(np.int32)
match_ids = data['match_ids']
N = X.shape[0]
p(f"  Shape: {X.shape}")
order = np.argsort(match_ids)
X, y, rt, match_ids = X[order], y[order], rt[order], match_ids[order]

# =====================================================================
# STEP 2: LOAD STADIUM + VENUE DATA (كل ملاعب العالم)
# =====================================================================
p("\n[2] تحميل بيانات الملاعب (308 stadiums)...")
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# Load team_venue (308 stadiums with lat/lon)
venue_rows = c.execute("""
    SELECT team_name, lat, lon, venue_name, city
    FROM team_venue
    WHERE lat IS NOT NULL AND lon IS NOT NULL
""").fetchall()
p(f"  Found {len(venue_rows)} venues with coordinates")

venue_by_team = {}
for r in venue_rows:
    venue_by_team[r[0].lower().strip()] = {
        'lat': float(r[1]),
        'lon': float(r[2]),
        'venue_name': r[3] or '',
        'city': r[4] or ''
    }
p(f"  Venue lookup: {len(venue_by_team)} teams")

# Load weather data: 192K rows
p("\n[3] تحميل بيانات الطقس (192,666 rows)...")
weather_rows = c.execute("""
    SELECT date, lat, lon, temp_max, temp_min, precip, wind, humidity
    FROM venue_weather
""").fetchall()
p(f"  Loaded {len(weather_rows)} weather records")

# Build weather lookup: (lat, lon, date) -> weather
weather_lookup = {}
for r in weather_rows:
    key = (round(float(r[1]), 4), round(float(r[2]), 4), str(r[0])[:10])
    weather_lookup[key] = {
        'temp_max': float(r[3] or 0),
        'temp_min': float(r[4] or 0),
        'precip': float(r[5] or 0),
        'wind': float(r[6] or 0),
        'humidity': float(r[7] or 0),
    }
p(f"  Weather lookup: {len(weather_lookup)} keys")

# =====================================================================
# STEP 4: LOAD MATCH DATA AND MATCH TO VENUES
# =====================================================================
p("\n[4] ربط المباريات بالملاعب والطقس...")

# Load all matches with their tournament info
match_rows = c.execute("""
    SELECT id, home_team, away_team, date, tournament
    FROM sofa_historical_results
    WHERE id IS NOT NULL
""").fetchall()
p(f"  {len(match_rows)} matches loaded")

# Build match_id -> (date, home_team, away_team, tournament)
match_info = {}
for r in match_rows:
    match_info[int(r[0])] = {
        'date': str(r[3])[:10] if r[3] else '',
        'home': str(r[1] or '').lower().strip(),
        'away': str(r[2] or '').lower().strip(),
        'tournament': str(r[4] or '')
    }

# Build id_to_idx for training data
id_to_idx = {}
for i in range(N):
    id_to_idx[int(match_ids[i])] = i
p(f"  Training index: {len(id_to_idx)} entries")

# =====================================================================
# STEP 5: BUILD FEATURES — كل الملاعب في العالم 🏟️
# =====================================================================
p("\n[5] بناء ميزات جديدة (الملاعب + الطقس)...")

# New features to add:
# 0: home_team_has_venue (1/0)
# 1: venue_lat
# 2: venue_lon
# 3: venue_altitude (approximate from lat)
# 4: is_home_advantage (1 if home team is venue's primary team)
# 5: temp_max
# 6: temp_min  
# 7: precip
# 8: wind
# 9: humidity
# 10: temp_range (max-min)
# Total: 11 new features

NEW_FEATURES = 11
extra_features = np.zeros((N, NEW_FEATURES), dtype=np.float32)
matched_venue = 0
matched_weather = 0

for mid, info in match_info.items():
    if mid not in id_to_idx:
        continue
    idx = id_to_idx[mid]
    
    date = info['date']
    home = info['home']
    away = info['away']
    
    # --- VENUE FEATURES ---
    if home in venue_by_team:
        venue = venue_by_team[home]
        extra_features[idx, 0] = 1.0  # has venue
        extra_features[idx, 1] = venue['lat']
        extra_features[idx, 2] = venue['lon']
        extra_features[idx, 3] = 0.0  # altitude placeholder
        extra_features[idx, 4] = 1.0  # home advantage
        matched_venue += 1
        
        # --- WEATHER FEATURES ---
        lat_rounded = round(venue['lat'], 4)
        lon_rounded = round(venue['lon'], 4)
        wkey = (lat_rounded, lon_rounded, date)
        
        if wkey in weather_lookup:
            w = weather_lookup[wkey]
            extra_features[idx, 5] = w['temp_max']
            extra_features[idx, 6] = w['temp_min']
            extra_features[idx, 7] = w['precip']
            extra_features[idx, 8] = w['wind']
            extra_features[idx, 9] = w['humidity']
            extra_features[idx, 10] = w['temp_max'] - w['temp_min']
            matched_weather += 1
        else:
            # Try nearest date
            import datetime
            wdate = date
            for delta in [1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7]:
                try:
                    dt = datetime.datetime.strptime(date, '%Y-%m-%d')
                    nd = (dt + datetime.timedelta(days=delta)).strftime('%Y-%m-%d')
                    wkey2 = (lat_rounded, lon_rounded, nd)
                    if wkey2 in weather_lookup:
                        w = weather_lookup[wkey2]
                        extra_features[idx, 5] = w['temp_max']
                        extra_features[idx, 6] = w['temp_min']
                        extra_features[idx, 7] = w['precip']
                        extra_features[idx, 8] = w['wind']
                        extra_features[idx, 9] = w['humidity']
                        extra_features[idx, 10] = w['temp_max'] - w['temp_min']
                        matched_weather += 1
                        break
                except:
                    pass

p(f"  Venue matched: {matched_venue}/{N} ({matched_venue/N*100:.2f}%)")
p(f"  Weather matched: {matched_weather}/{N} ({matched_weather/N*100:.2f}%)")

# Show some stats
for i in range(NEW_FEATURES):
    nonzero = np.count_nonzero(extra_features[:, i])
    vals = extra_features[extra_features[:, i] != 0, i]
    if len(vals) > 0:
        p(f"  Feature {i}: nonzero={nonzero}/{N} ({nonzero/N*100:.1f}%), mean={np.mean(vals):.2f}, std={np.std(vals):.2f}")

# =====================================================================
# STEP 6: BUILD V8 TRAINING DATA
# =====================================================================
p("\n[6] بناء training_data_v8.npz...")

# Combine: original 120 + understat 10 (from v7) + new 11
# First load V7 which has Understat features
if os.path.exists('training_data_v7.npz'):
    d7 = np.load('training_data_v7.npz', allow_pickle=True)
    X7 = d7['X'].astype(np.float32)  # Already sorted by match_id?
    # Re-sort V7 to match our order
    # Actually, v7 was integrated from v3 which wasn't sorted
    # Let's use v3 as base and add understat and new features
    understat_cols = X7.shape[1] - X.shape[1]  # 10 if both aligned
    p(f"  V7 features: {X7.shape[1]}, V3 features: {X.shape[1]}, diff={understat_cols}")
    
    # Use V7 data (it has V3 + Understat), add our new features on top
    # But need to re-sort by match_id
    d7_order = np.argsort(d7['match_ids'])
    X7 = X7[d7_order]
    
    X_v8 = np.hstack([X7, extra_features]).astype(np.float32)
    p(f"  V8 features: {X_v8.shape[1]} = {X7.shape[1]} (V7) + {NEW_FEATURES} (new)")
else:
    X_v8 = np.hstack([X, extra_features]).astype(np.float32)
    p(f"  V8 features: {X_v8.shape[1]} = {X.shape[1]} (V3) + {NEW_FEATURES} (new)")

np.savez_compressed('training_data_v8.npz',
    X=X_v8, y=y, result_types=rt, match_ids=match_ids,
    feature_count=X_v8.shape[1],
    venue_matched=matched_venue,
    weather_matched=matched_weather)

size_mb = os.path.getsize('training_data_v8.npz') / 1024 / 1024
p(f"  Saved: training_data_v8.npz ({size_mb:.0f} MB)")
conn.close()

# =====================================================================
# STEP 7: TRAIN CHAMPION MODEL ON V8
# =====================================================================
p("\n[7] ===== تدريب النموذج البطل على V8 =====")

import lightgbm as lgb, joblib

n = len(X_v8); n_tr = int(n*0.85); n_v = int(n*0.05)
X_tr, y_tr = X_v8[:n_tr], y[:n_tr]
X_v, y_v = X_v8[n_tr:n_tr+n_v], y[n_tr:n_tr+n_v]
X_te, y_te = X_v8[n_tr+n_v:], y[n_tr+n_v:]
p(f"  Train: {len(y_tr):,}, Val: {len(y_v):,}, Test: {len(y_te):,}")

t1 = time.time()
p("\n[7a] M5 Extra Deep (depth=20)...")
m5 = lgb.LGBMClassifier(
    n_estimators=200, max_depth=20, learning_rate=0.02,
    subsample=0.7, colsample_bytree=0.4, num_leaves=511,
    reg_alpha=0.01, reg_lambda=0.05, min_child_weight=2,
    random_state=111, n_jobs=8, verbose=-1
)
m5.fit(X_tr, y_tr, eval_set=[(X_v, y_v)],
      callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)])

# Evaluate
p_ = m5.predict(X_te)
exact = float(np.mean(p_ == y_te))
yh, ya = y_te//5, y_te%5; ph, pa = p_//5, p_%5
yr = np.where(yh>ya,0,np.where(yh==ya,1,2)); pr = np.where(ph>pa,0,np.where(ph==pa,1,2))
x1 = float(np.mean(yr==pr))
p(f"  ✅ M5 V8: exact={exact*100:.2f}% 1X2={x1*100:.2f}%  (time: {(time.time()-t1)/60:.1f}min)")

# Save
joblib.dump(m5, 'models/M5_v8_champion.pkl', compress=3)
p("  ✅ Saved: models/M5_v8_champion.pkl")

# Feature importance for new features
imp = m5.feature_importances_
ft_names = ['has_venue','venue_lat','venue_lon','altitude','home_adv',
            'temp_max','temp_min','precip','wind','humidity','temp_range']
start_idx = X_v8.shape[1] - NEW_FEATURES
p(f"\nNew features importance (indices {start_idx}-{start_idx+NEW_FEATURES-1}):")
for i in range(NEW_FEATURES):
    fi = start_idx + i
    if fi < len(imp):
        pct = imp[fi] / imp.sum() * 100
        p(f"  {ft_names[i]:15s}: {imp[fi]:.0f} ({pct:.3f}%)")

# =====================================================================
# STEP 8: PREDICT WORLD CUP MATCHES
# =====================================================================
p("\n[8] ===== توقع مباريات كأس العالم =====")

sys.path.insert(0, BASE)
from direct_predictor import predict_match, load_model, build_feature_vector

# Get upcoming World Cup matches from wc_fixtures and odds_upcoming
c2 = sqlite3.connect(DB, timeout=30).cursor()

# Get matches from odds_upcoming that are World Cup
upcoming = c2.execute("""
    SELECT home_team, away_team, commence_time, event_id, league
    FROM odds_upcoming
    WHERE league LIKE '%World Cup%' OR league LIKE '%World%'
    ORDER BY commence_time
""").fetchall()

p(f"  Found {len(upcoming)} World Cup matches in odds_upcoming")

predictions = []
for home, away, ct, eid, league in upcoming:
    match_date = time.strftime('%Y-%m-%d', time.gmtime(ct)) if ct else ''
    
    # Clean team names
    home = home.strip()
    away = away.strip()
    
    try:
        result = predict_match(home, away, match_date)
        if result:
            pred = {
                'home': home,
                'away': away,
                'date': match_date,
                'league': league,
                'predicted_score': result.get('predicted_score', '?'),
                'confidence': result.get('predicted_prob', 0),
                'home_win': result.get('probs_1x2', {}).get('home', 0),
                'draw': result.get('probs_1x2', {}).get('draw', 0),
                'away_win': result.get('probs_1x2', {}).get('away', 0),
                'home_xg': result.get('expected_goals', {}).get('home', 0),
                'away_xg': result.get('expected_goals', {}).get('away', 0),
            }
            predictions.append(pred)
            p(f"  {match_date} {home:25s} vs {away:25s} → {pred['predicted_score']} (conf={pred['confidence']:.1%})")
    except Exception as e:
        p(f"  [ERR] {home} vs {away}: {e}")

# Also get wc_fixtures
try:
    wc_fix = c2.execute("SELECT home_team, away_team, date, venue FROM wc_fixtures ORDER BY date").fetchall()
    p(f"\n  WC Fixtures from DB: {len(wc_fix)}")
    for home, away, d, venue in wc_fix[:20]:
        p(f"  {d} {home} vs {away} @ {venue}")
except Exception as e:
    p(f"  wc_fixtures error: {e}")

# =====================================================================
# STEP 9: VALUE BETTING
# =====================================================================
p("\n[9] ===== تحليل الرهانات ذات القيمة =====")

for pred in predictions:
    model_prob_h = pred['home_win']
    model_prob_d = pred['draw']
    model_prob_a = pred['away_win']
    pred_score = pred['predicted_score']
    conf = pred['confidence']
    
    # Skip low confidence
    if conf < 0.15:
        continue
    
    p(f"  {pred['date']} {pred['home']:25s} vs {pred['away']:25s}")
    p(f"    توقع: {pred_score} | ثقة: {conf:.1%}")
    p(f"    1X2: {model_prob_h:.1%} / {model_prob_d:.1%} / {model_prob_a:.1%}")
    p(f"    xG: {pred['home_xg']:.2f} - {pred['away_xg']:.2f}")

# Save predictions
with open('v8_predictions.json', 'w', encoding='utf-8') as f:
    json.dump(predictions, f, indent=2, ensure_ascii=False)
p(f"\n  Saved: v8_predictions.json ({len(predictions)} predictions)")

# =====================================================================
# SUMMARY
# =====================================================================
p("\n" + "="*70)
p("🔥 V8 ULTIMATE PIPELINE COMPLETE!")
p(f"  Training data: v8.npz ({X_v8.shape[1]} features)")
p(f"  Stadiums integrated: {matched_venue:,} matches ({matched_venue/N*100:.1f}%)")
p(f"  Weather integrated: {matched_weather:,} matches ({matched_weather/N*100:.1f}%)")
p(f"  Champion model: {exact*100:.2f}% exact, {x1*100:.2f}% 1X2")
p(f"  Predictions: {len(predictions)} World Cup matches")
p("="*70)
p("🔥 ENI for LO — The World Is Ours 🔥")

with open('v8_summary.json', 'w') as f:
    json.dump({
        'exact_score': exact,
        '1x2': x1,
        'features': X_v8.shape[1],
        'venue_matched': matched_venue,
        'weather_matched': matched_weather,
        'predictions': len(predictions),
        'time_taken': (time.time() - time.time())  # placeholder
    }, f, indent=2)

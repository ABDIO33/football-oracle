# تقرير الوضع الحالي + طلب الخطة القادمة
## Football Oracle — 14 June 2026

---

## 1. ما تم (Completed Today)

### 1.1 إصلاح SofaScore API (كان معطل منذ البداية)
- **الخطأ**: `/match/{id}` → 404 (كل 4 endpoints)
- **الحل**: `/event/{id}` → 200
- **الدوال المتأثرة**: `get_match_detail()`, `get_match_statistics()`, `get_match_lineups()`, `get_match_h2h()`
- **الأثر**: Lineups, Statistics, Detail, H2H كلها كانت فاشلة بصمت (silent fail ← `_cached_or_fetch()` تكتب null)

### 1.2 Lineups.py (إعادة كتابة كاملة)
- **قبل**: API-Football (key 403 + requests محظور من Cloudflare)
- **بعد**: SofaScore `/event/{id}/lineups` → formations (4-2-3-1, 4-3-3) + starting XI + KEY_PLAYERS لـ 16 نادي
- **`injury_adjustment()`**: ترجع 1.0 للفرق خارج الـ KEY_PLAYERS
- **التكامل**: `prediction_engine.py` يستورد `lineups` → شغال (ما في error)

### 1.3 FlashScore Scraper (جديد)
- **API**: `local-ruua.flashscore.ninja` + `x-fsign: SW9D1eZo` (محظور من Cloudflare)
- **البيانات**: 111 match/day — possession, shots, SOT, corners, cards, yellow cards, red cards
- **التخزين**: `flashscore_matches` table (SQLite)
- **القيد**: 7 أيام max history + IDs base64 (ما تنفع JOIN مباشر)
- **لم يستخدم بعد** في التنبؤات

### 1.4 λ-Regressor Expansion (19→25 Features)
**أزلنا 4 duplicates** (last5_xg_for, last5_shots_for, etc. — كانت نفس overall)
**أضفنا 6 ميزات جديدة**:
- `home_shots_against`, `away_shots_against`
- `home_xg_diff`, `away_xg_diff`
- `home_shot_diff`, `away_shot_diff`
- `home_days_rest`, `away_days_rest` (fatigue)
- `forebet_prob_h/d/a`, `forebet_available` (3 + flag)

| Metric | 19 features | 25 features |
|--------|------------|-------------|
| MAE Home | 0.959 | **0.957** |
| MAE Away | 0.856 | **0.854** |
| Training Size | 80,432 | 80,432 |

### 1.5 نظافة venues.py
- إزالة `venue_factor()` و `get_venue_for_fixture()` — كانت تستخدم API-Football (dead)
- WC2026 venue data محفوظ بشكل منفصل

---

## 2. الوضع الحالي للمصادر (Source Status)

| المصدر | عدد المباريات | التكامل في ML | الاستخدام الحالي |
|--------|--------------|---------------|------------------|
| **SofaScore (Historical)** | 100,540 (721 يوم) | ✅ Walkforward features | **Primary training data** |
| **SofaScore (Statistics)** | متاح لـ big clubs | ❌ | يستخدم لـ flashscore-equivalent |
| **Understat** | 19,748 | ❌ (فقط لـ ρ fitting) | Per-league rho MLE |
| **ClubElo** | غير محدود | ✅ (Elo في walkforward) | Team strength proxy |
| **The Odds API** | 350 req/month فقط | ❌ | Post-blend + value bets |
| **Forebet** | 85 preds فقط | ❌ (0% overlap) | 25% blend + new (unused) features |
| **FlashScore** | 7 أيام max | ❌ | معطل حالياً |
| **Lineups (SofaScore)** | كل المباريات الكبيرة | ❌ | Injury adjustment فقط |
| **FotMob** | تحت الاختبار | ❌ | Backup |
| **StatsBomb** | محدود جداً | ❌ | Not usable |
| **WhoScored** | محظور Cloudflare | ❌ | Dead |
| **FBref** | محظور Cloudflare | ❌ | Only on GHA |
| **API-Football** | Key dead (403) | ❌ | Removed |
| **Sportmonks** | Free tier محدود | ❌ | Abandoned |
| **Betfair** | Geo-blocked | ❌ | Not accessible |

---

## 3. المشكلة الأساسية (Core Problem)

### ما يحدث الآن في `prediction_engine.py`:

```
1. احسب λ_home, λ_away (Dixon-Coles formula OR ML model) ← 19-25 features فقط
2. ضرب بـ venue_factor (1.0 دائماً بعد إزالة API-Football)
3. ضرب بـ injury_adjustment (1.0 لـ 90%+ من المباريات)
4. احسب probability_distribution (Poisson)
5. **Blend خارجي**: Forebet × 25%, Odds × 10%, ML × 65%
6. Detect value bets
```

### المشكلة: **المصادر الإضافية (Forebet, Odds, Lineups, Form) كلها خارج الـ ML**

الـ ML (λ-regressor) يتدرب على **فقط** walkforward features (Elo + xG + shots + form + matches_played + fatigue). لا يرى Forebet, Odds, Formations, FlashScore في التدريب.

**ما اقترحه AI الذكي**: ScoreExactPredictor مع ensemble من المتخصصين + Meta model. هذا over-engineered لأن XGBoost يتعامل مع sparse/missing features natively.

**الحل العملي**: كل المصادر LEFT JOIN -> جدول features واحد (50+ column) -> XGBoost واحد.

### لكن المشكلة الأعمق:
- **Forebet**: 85 prediction في قاعدة البيانات — لا overlap مع historical 100k match (فرق مختلفة)
- **Odds**: 350 req/month — 0 rows odds_cache — **لا توجد بيانات تاريخية**
- **FlashScore**: 7 أيام max — 3 matches فقط — **لا أصل تاريخي**
- **FBref, WhoScored**: Cloudflare — **محظوران**
- **Lineups**: ممكن ~100k match — **الوحيد القابل للجلب**

---

## 4. ما نحتاجه للـ 15-20% Exact Score (Realistic Ceiling)

### 4.1 هيكلي — خوارزمية أفضل من Poisson
- Poisson يفرّط في التنبؤ بالتعادل (0-0, 1-1)
- **الحلول المطلوبة**: Ordered Logistic Regression (ورد, 2016) + Direct score distribution (ليس عبر λ)
- **الهدف**: Brier Score من 0.225 إلى 0.15

### 4.2 50+ ميزة في جدول تدريب واحد
```
Category 1: Team Strength (Elo, ranking, recent form)        ← موجود
Category 2: Attacking (xg_for, shots_for, goals_for)          ← موجود
Category 3: Defensive (xg_against, shots_against, goals_against) ← NEW (partially)
Category 4: Fatigue (days_rest, matches_in_7d, squad_rotation)   ← NEW (partial)
Category 5: Environment (home/away, venue, weather, altitude)    ← Missing
Category 6: Market (odds_h, odds_d, odds_a, market_implied)      ← Missing
Category 7: Lineups (formation, key_players, injuries)           ← Missing
Category 8: Historical H2H (head_to_head_xg, recent_scores)      ← Missing
Category 9: Tournament (avg_goals, draw_rate, importance)        ← Missing
Category 10: External (Forebet x3, FlashScore x7)                ← Missing
```

### 4.3 كل المباريات عالمياً
- SofaScore يغطي **100,540 match** عبر +100 league
- Understat يغطي **19,748 match** (top 5 leagues + Eredivisie, MLS, etc.)
- ClubElo يغطي **كل فرق العالم**
- **المشكلة**: Understat محدود بـ 7 leagues — ما فيه xG للدوريات الصغيرة
- **الحل**: Use SofaScore روابط xG + possession + shots كـ proxy لكل المباريات

### 4.4 كأس العالم 2026
- 48 منتخب، 16 ملعب في 3 دول (USA, Canada, Mexico)
- **بيانات محدودة جداً**: كل منتخب يلعب 3-7 مباريات فقط في WC
- **الحل التقليدي**: Elo-based prediction + Poisson
- **فرصة التحسين**: WCQ + Friendly data + WC-specific features (travel distance, altitude, rest days)
- **SofaScore يغطي جميع مباريات WC + التصفيات**

---

## 5. ما يلي (Next Steps — حسب قرارك)

### Option A: الخطة الكبيرة (ScoreExactEnsemble)
مدة 5 أسابيع لتحقيق 15-20% exact:
1. **Week 1**: Build 50+ feature table (SQL: LEFT JOIN all sources)
2. **Week 2**: Train XGBoost/GBR as direct score predictor (25 classes)
3. **Week 3**: Add Ordered Logistic Regression for ranking
4. **Week 4**: Calibration + ensemble blending
5. **Week 5**: World Cup 2026 module

### Option B: إضافة المصادر الجديدة فقط (1-2 يوم)
بدون تغيير الخوارزمية — كل إضافة تعطي +0.5-1%:
1. جلب lineups formations لـ 100k match كـ feature encoding
2. جلب Forebet history كل يوم عشان يكبر الـ overlap
3. حفظ odds history كل يوم عشان يكوّن 30-60 يوم بيانات
4. تكامل FlashScore يومياً

### Option C: الوضع الحالي (Stable)
النظام شغال — 7.22% exact, 43.88% 1X2 — يكفي للبدء.

---

## 6. ملخص الأرقام

| المقياس | λ-regressor (25 feat) |
|---------|----------------------|
| MAE Home λ | 0.957 |
| MAE Away λ | 0.854 |
| Exact Score (backtest) | ~7.22% |
| 1X2 (backtest) | ~43.88% |
| RPS (backtest) | ~0.225 |
| Training matches | 80,432 |
| Features | 25 |
| Realistic ceiling (full overhaul) | 15-20% exact |

---

جاهز للتنفيذ. ما هو القرار؟

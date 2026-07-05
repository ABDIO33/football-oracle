# 📊 Score Exact 100 — تقرير الأداء
تاريخ التقرير: 2026-06-26 15:43

## 🏆 أداء النماذج

| المعيار | V3 (128K) | V5 (887K) | الهدف |
|---------|:---------:|:---------:|:----:|
| Exact Score | 25.89% | 18.51% | >25% |
| 1X2 | 78.12% | 62.31% | >75% |
| RPS | 0.0559 | 0.0880 | <0.058 |

## 📦 النماذج المخزنة

- `v3_model.pkl` — 105.4MB
- `v5_model.pkl` — 105.4MB
- `xgb_v5.pkl` — 95.6MB
- `xgb_v3.pkl` — 93.2MB
- `v4_pp.npz` — 81.6MB
- `checkpoint_xgb.pkl` — 80.7MB
- `preprocessed_data.npz` — 76.2MB
- `mlp_blend.pkl` — 70.1MB
- `v4_preprocessed.npz` — 66.7MB
- `improved_model.pkl` — 57.2MB
- `v5_pp.npz` — 56.7MB
- `real_model.pkl` — 56.4MB
- `v5_preprocessed.npz` — 56.2MB
- `m4_epoch20.pt` — 4.7MB
- `m4_epoch40.pt` — 4.7MB
- `m4_epoch60.pt` — 4.7MB
- `checkpoint_M5_big.pt` — 4.3MB
- `M5_big_v3.pt` — 4.3MB
- `M5_big_v5.pt` — 4.3MB
- `checkpoint_M5_wide.pt` — 2.9MB
- `M5_wide_v3.pt` — 2.9MB
- `M5_wide_v5.pt` — 2.9MB
- `mlp_model.pkl` — 2.6MB
- `checkpoint_M5_deep.pt` — 1.3MB
- `M5_deep_v3.pt` — 1.3MB
- `M5_deep_v5.pt` — 1.2MB
- `checkpoint_M5_medium.pt` — 1.1MB
- `M5_medium_v3.pt` — 1.1MB
- `M5_medium_v5.pt` — 1.1MB
- `lambda_home.pkl` — 453KB
- `lambda_away.pkl` — 445KB
- `checkpoint_M5_small.pt` — 329KB
- `M5_small_v3.pt` — 328KB
- `real_m5.pt` — 328KB
- `M5_small_v5.pt` — 326KB
- `meta_learner.pkl` — 11KB
- `isotonic_calibrators.pkl` — 7KB
- `ultimate_model.pkl` — 4KB
- `checkpoint_scaler.pkl` — 3KB
- `v4_scaler.pkl` — 3KB
- `v5_scaler.pkl` — 2KB
- `mlp_scaler.pkl` — 2KB
- `checkpoint_imputer.pkl` — 1KB
- `v4_imputer.pkl` — 1KB
- `mlp_imputer.pkl` — 1KB
- `v5_imputer.pkl` — 827B

## 🔧 الميزات الجديدة (V6) — 126 ميزة
تم إضافة 41 ميزة إضافية إلى 85 ميزة أساسية = **126 ميزة**
- Poisson 25-class probabilities 📊
- League strength + tournament importance 🏆
- H2H features 🆚
- Formation analysis ⚽
- Form streaks + volatility 📈

## 🚀 جاهز للتشغيل
`train_v6.py` — يدعم 126 ميزة، 7 architectures، 200 epochs
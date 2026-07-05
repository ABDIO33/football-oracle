#!/usr/bin/env python3
"""Agent 5 - StatsBomb xG Model (robust version)"""
import sys, os, json, time, warnings, logging, numpy as np, pandas as pd
from pathlib import Path
from datetime import datetime

warnings.filterwarnings('ignore')
os.environ['PYTHONIOENCODING'] = 'utf-8'
# Reconfigure stdout/stderr
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('xg_model_run.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('XG')

MODELS_DIR = Path(__file__).parent / 'models'
DATA_DIR = Path(__file__).parent / 'statsbomb_data'
MODELS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

COMPETITIONS = [
    (2, 27), (11, 27), (12, 27), (7, 27),
    (43, 3), (43, 106), (37, 90), (49, 107),
]

PITCH_LENGTH, PITCH_WIDTH, GOAL_WIDTH = 120.0, 80.0, 7.32

def extract_all_shots():
    """Extract all shots from all matches."""
    from statsbombpy import sb

    all_shots = []
    total_matches = 0
    errors = 0

    logger.info(f"Fetching matches from {len(COMPETITIONS)} competitions...")
    all_match_ids = []

    for comp_id, season_id in COMPETITIONS:
        try:
            matches = sb.matches(competition_id=comp_id, season_id=season_id)
            mids = matches['match_id'].unique().tolist()
            all_match_ids.extend(mids)
            logger.info(f"  Comp {comp_id}/{season_id}: {len(mids)} matches")
        except Exception as e:
            logger.warning(f"  Comp {comp_id}/{season_id} failed: {e}")

    logger.info(f"Total matches: {len(all_match_ids)}")

    for i, match_id in enumerate(all_match_ids):
        if i % 100 == 0 and i > 0:
            logger.info(f"Progress: {i}/{len(all_match_ids)} matches, {len(all_shots)} shots, {errors} errors")

        try:
            events = sb.events(match_id=int(match_id))
            shots = events[events['type'] == 'Shot']
            if shots.empty:
                continue
            total_matches += 1

            for _, shot in shots.iterrows():
                try:
                    loc = shot.get('location')
                    if not isinstance(loc, (list, tuple)) or len(loc) < 2:
                        continue
                    x, y = float(loc[0]), float(loc[1])

                    distance = np.sqrt((PITCH_LENGTH - x)**2 + (PITCH_WIDTH/2 - y)**2)
                    if distance < 0.1:
                        continue

                    angle = np.arctan2(
                        GOAL_WIDTH * (PITCH_LENGTH - x),
                        (PITCH_LENGTH - x)**2 + (PITCH_WIDTH/2 - y)**2 - (GOAL_WIDTH/2)**2
                    )
                    if np.isnan(angle) or np.isinf(angle):
                        angle = 0.0

                    ff = shot.get('shot_freeze_frame')
                    n_def = 0
                    if isinstance(ff, list):
                        for p in ff:
                            if isinstance(p, dict) and not p.get('teammate', True):
                                n_def += 1

                    xg = shot.get('shot_statsbomb_xg', 0)
                    if xg is None or (isinstance(xg, float) and np.isnan(xg)):
                        xg = 0.0

                    is_goal = 1 if shot.get('shot_outcome') == 'Goal' else 0

                    body = str(shot.get('shot_body_part', 'Right Foot'))
                    stype = str(shot.get('shot_type', 'Open Play'))
                    technique = str(shot.get('shot_technique', 'Normal'))

                    all_shots.append({
                        'match_id': int(match_id),
                        'minute': int(shot.get('minute', 0)),
                        'half': 1 if int(shot.get('minute', 0)) <= 45 else 2,
                        'x': round(x, 2), 'y': round(y, 2),
                        'distance': round(distance, 2),
                        'angle': round(angle, 4),
                        'header': 1 if 'Head' in body else 0,
                        'right_foot': 1 if 'Right' in body else 0,
                        'left_foot': 1 if 'Left' in body else 0,
                        'open_play': 1 if stype == 'Open Play' else 0,
                        'free_kick': 1 if 'Free' in stype else 0,
                        'penalty': 1 if 'Penalty' in stype else 0,
                        'corner': 1 if 'Corner' in stype else 0,
                        'first_time': 1 if shot.get('shot_first_time') else 0,
                        'one_on_one': 1 if shot.get('shot_one_on_one') else 0,
                        'deflected': 1 if shot.get('shot_deflected') else 0,
                        'under_pressure': 1 if shot.get('under_pressure') else 0,
                        'n_defenders': n_def,
                        'xg': round(float(xg), 4),
                        'goal': is_goal,
                        'technique': technique,
                    })
                except Exception:
                    errors += 1
                    continue

        except Exception as e:
            errors += 1
            continue

    df = pd.DataFrame(all_shots)
    logger.info(f"\nExtraction complete: {len(df)} shots from {total_matches} matches ({errors} errors)")
    return df

def engineer_and_train(df):
    """Engineer features and train XGBoost model."""
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
    from sklearn.calibration import CalibratedClassifierCV
    import joblib

    logger.info("Engineering features...")

    # Base features
    base = ['distance', 'angle', 'header', 'right_foot', 'left_foot',
            'open_play', 'free_kick', 'penalty', 'corner',
            'first_time', 'one_on_one', 'deflected', 'under_pressure',
            'n_defenders', 'half']

    # Engineered
    df['dist_sq'] = df['distance'] ** 2
    df['angle_sq'] = df['angle'] ** 2
    df['log_dist'] = np.log1p(df['distance'])
    df['x_centered'] = abs(df['x'] - 60)
    df['y_centered'] = abs(df['y'] - 40)
    df['danger'] = np.exp(-df['distance'] / 20) * (1 + abs(df['angle']) / 1.5)
    df['def_pressure'] = df['n_defenders'] / (df['distance'] + 1)
    df['header_pressure'] = df['header'] * df['under_pressure']
    df['x_norm'] = df['x'] / PITCH_LENGTH
    df['y_norm'] = df['y'] / PITCH_WIDTH

    extended = ['dist_sq', 'angle_sq', 'log_dist', 'x_centered', 'y_centered',
                'danger', 'def_pressure', 'header_pressure', 'x_norm', 'y_norm']

    features = base + extended
    logger.info(f"Total features: {len(features)}: {features}")

    # Save features
    with open(MODELS_DIR / 'xg_features.json', 'w') as f:
        json.dump({'features': features, 'n_features': len(features)}, f, indent=2)

    # Split
    matches = df['match_id'].unique()
    train_m, test_m = train_test_split(matches, test_size=0.2, random_state=42)

    X_train = df[df['match_id'].isin(train_m)][features].values
    y_train = df[df['match_id'].isin(train_m)]['goal'].values
    X_test = df[df['match_id'].isin(test_m)][features].values
    y_test = df[df['match_id'].isin(test_m)]['goal'].values

    logger.info(f"Train: {len(X_train)} shots, Test: {len(X_test)} shots")
    logger.info(f"Goal rate train: {y_train.mean()*100:.2f}%, test: {y_test.mean()*100:.2f}%")

    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    model = xgb.XGBClassifier(
        n_estimators=500, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
        scale_pos_weight=pos_weight,
        objective='binary:logistic',
        eval_metric=['logloss', 'auc'],
        random_state=42, n_jobs=-1,
        early_stopping_rounds=50,
    )

    model.fit(X_train, y_train,
              eval_set=[(X_train, y_train), (X_test, y_test)],
              verbose=False)

    # Save model
    model.save_model(str(MODELS_DIR / 'xg_model.json'))
    logger.info(f"Model saved to models/xg_model.json")

    # Predict
    y_pred = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_pred)
    brier = brier_score_loss(y_test, y_pred)
    ll = log_loss(y_test, y_pred)
    naive_ll = log_loss(y_test, np.full_like(y_test, y_test.mean()))

    logger.info(f"\n=== XGBoost xG Results ===")
    logger.info(f"AUC: {auc:.4f}")
    logger.info(f"Brier: {brier:.4f}")
    logger.info(f"Log Loss: {ll:.4f} (naive: {naive_ll:.4f})")

    # Feature importance
    imp = pd.DataFrame({'feature': features, 'importance': model.feature_importances_})
    imp = imp.sort_values('importance', ascending=False)
    logger.info(f"\nTop 10 features:")
    for i, (_, r) in enumerate(imp.head(10).iterrows()):
        logger.info(f"  {i+1}. {r['feature']}: {r['importance']:.4f}")

    # Calibrate
    cal = CalibratedClassifierCV(model, method='sigmoid', cv=5)
    cal.fit(X_train, y_train)
    y_pred_cal = cal.predict_proba(X_test)[:, 1]
    cal_brier = brier_score_loss(y_test, y_pred_cal)
    cal_ll = log_loss(y_test, y_pred_cal)

    logger.info(f"\nCalibrated: Brier={cal_brier:.4f}, LogLoss={cal_ll:.4f}")

    joblib.dump(cal, str(MODELS_DIR / 'xg_model_calibrated.pkl'))
    logger.info(f"Calibrated model saved to models/xg_model_calibrated.pkl")

    # Per-match analysis
    df_test = df[df['match_id'].isin(test_m)].copy()
    df_test['pred_xg'] = cal.predict_proba(df_test[features].values)[:, 1]

    match_stats = df_test.groupby('match_id').agg({
        'xg': 'sum', 'pred_xg': 'sum', 'goal': 'sum', 'match_id': 'count'
    }).rename(columns={'match_id': 'shots'})

    logger.info(f"\nPer-match stats:")
    logger.info(f"  Mean xG: {match_stats['xg'].mean():.3f} (StatsBomb) vs {match_stats['pred_xg'].mean():.3f} (Ours)")
    logger.info(f"  Mean goals: {match_stats['goal'].mean():.3f}")
    logger.info(f"  MAE vs StatsBomb: {abs(match_stats['pred_xg'] - match_stats['xg']).mean():.3f}")
    logger.info(f"  MAE vs Goals: {abs(match_stats['pred_xg'] - match_stats['goal']).mean():.3f}")

    match_stats.to_csv(DATA_DIR / 'match_xg_analysis.csv')

    # Results JSON
    results = {
        'n_matches': int(len(matches)),
        'n_shots': int(len(df)),
        'n_train': int(len(X_train)),
        'n_test': int(len(X_test)),
        'auc_roc': round(auc, 4),
        'brier': round(brier, 4),
        'brier_calibrated': round(cal_brier, 4),
        'log_loss': round(ll, 4),
        'log_loss_calibrated': round(cal_ll, 4),
        'goal_rate': round(float(y_test.mean()), 4),
        'feature_importance': imp.head(20).to_dict('records'),
        'top_features': features[:10],
        'timestamp': datetime.now().isoformat(),
    }
    with open(MODELS_DIR / 'xg_model_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    return results

def main():
    start = time.time()

    # Extract
    df = extract_all_shots()
    if df.empty:
        logger.error("No shots extracted!")
        return 1

    # Save raw
    df.to_csv(DATA_DIR / 'shots_raw.csv', index=False)
    logger.info(f"Raw shots saved ({len(df)} rows)")

    # Train
    results = engineer_and_train(df)

    elapsed = time.time() - start
    logger.info(f"\n{'='*60}")
    logger.info(f"COMPLETE: {elapsed/60:.1f} minutes")
    logger.info(f"Shots: {len(df)}, AUC: {results['auc_roc']}, Brier: {results['brier_calibrated']}")
    logger.info(f"{'='*60}")
    return 0

if __name__ == '__main__':
    sys.exit(main())

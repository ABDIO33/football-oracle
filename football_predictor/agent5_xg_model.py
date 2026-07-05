#!/usr/bin/env python3
"""
Agent 5 — Phase 2: STATSBOMB xG MODEL
=======================================
Extract shot events from 1923+ StatsBomb matches, engineer features,
train XGBoost expected goals model, calibrate and save.

Protocols: SIGMA-ZERO, DΞMON CORE, BLACK CODE CURSE
"""

import os
import sys
import json
import time
import warnings
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict, Optional
from collections import defaultdict

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('StatsBombXG')

# Paths
MODELS_DIR = Path(__file__).parent / 'models'
MODELS_DIR.mkdir(exist_ok=True)
DATA_DIR = Path(__file__).parent / 'statsbomb_data'
DATA_DIR.mkdir(exist_ok=True)

# Competition IDs for our 1923-match dataset
TARGET_COMPETITIONS = [
    # Top 5 leagues 2015/16
    (2, 27),    # Premier League 2015/16 (380 matches)
    (11, 27),   # La Liga 2015/16 (380 matches)
    (12, 27),   # Serie A 2015/16 (380 matches)
    (7, 27),    # Ligue 1 2015/16 (377 matches)
    # World Cups for variety
    (43, 3),    # FIFA World Cup 2018 (64 matches)
    (43, 106),  # FIFA World Cup 2022 (64 matches)
    # Extra competitions to reach 1923+
    (37, 90),   # FA WSL 2020/21 (131)
    (49, 107),  # NWSL 2023 (137)
]

# Standard pitch dimensions
PITCH_LENGTH = 120.0  # meters
PITCH_WIDTH = 80.0    # meters
GOAL_WIDTH = 7.32     # meters
GOAL_HEIGHT = 2.44    # meters


def fetch_all_matches() -> pd.DataFrame:
    """Fetch all matches from target competitions via statsbombpy."""
    from statsbombpy import sb

    all_matches = []
    total = 0

    logger.info(f"📊 Fetching matches from {len(TARGET_COMPETITIONS)} competitions...")

    for comp_id, season_id in TARGET_COMPETITIONS:
        try:
            matches = sb.matches(competition_id=comp_id, season_id=season_id)
            logger.info(f"   Competition {comp_id}/{season_id}: {len(matches)} matches")
            matches['competition_id'] = comp_id
            matches['season_id'] = season_id
            all_matches.append(matches)
            total += len(matches)
        except Exception as e:
            logger.warning(f"   ❌ Competition {comp_id}/{season_id} failed: {e}")

    if not all_matches:
        logger.error("❌ No matches fetched!")
        return pd.DataFrame()

    df = pd.concat(all_matches, ignore_index=True)
    logger.info(f"✅ Total matches fetched: {len(df)}")
    return df


def extract_shot_events(match_ids: List[int], max_matches: int = None) -> pd.DataFrame:
    """
    Extract all shot events from matches using statsbombpy.
    Features: location, body part, shot type, freeze frame, pressure, etc.
    """
    from statsbombpy import sb

    all_shots = []
    match_count = 0

    if max_matches:
        match_ids = match_ids[:max_matches]

    logger.info(f"🎯 Extracting shot events from {len(match_ids)} matches...")

    for i, match_id in enumerate(match_ids):
        if i % 100 == 0:
            logger.info(f"   Progress: {i}/{len(match_ids)} matches processed ({len(all_shots)} shots)")

        try:
            events = sb.events(match_id=match_id)

            if events.empty:
                continue

            # Filter shot events
            shots = events[events['type'] == 'Shot'].copy()

            if shots.empty:
                continue

            match_count += 1

            for _, shot in shots.iterrows():
                try:
                    # Basic location
                    loc = shot.get('location', None)
                    if loc is None or not isinstance(loc, (list, tuple)) or len(loc) < 2:
                        continue

                    x, y = float(loc[0]), float(loc[1])

                    # Distance to goal (center of goal at x=120, y=40)
                    distance = np.sqrt((PITCH_LENGTH - x) ** 2 + (PITCH_WIDTH / 2 - y) ** 2)

                    # Angle to goal (using goal width)
                    goal_left = PITCH_WIDTH / 2 - GOAL_WIDTH / 2
                    goal_right = PITCH_WIDTH / 2 + GOAL_WIDTH / 2

                    angle = np.arctan2(GOAL_WIDTH * (PITCH_LENGTH - x),
                                       (PITCH_LENGTH - x) ** 2 + (PITCH_WIDTH / 2 - y) ** 2 - (GOAL_WIDTH / 2) ** 2)

                    # Handle NaN/Inf in angle
                    if np.isnan(angle) or np.isinf(angle):
                        angle = 0.0

                    # Shot features
                    shot_type = shot.get('shot_type', 'Open Play')
                    body_part = shot.get('shot_body_part', 'Right Foot')
                    technique = shot.get('shot_technique', 'Normal')
                    first_time = shot.get('shot_first_time', False)
                    one_on_one = shot.get('shot_one_on_one', False)
                    deflected = shot.get('shot_deflected', False)
                    redirected = shot.get('shot_redirect', False)
                    under_pressure = shot.get('under_pressure', False)

                    # Freeze frame info (number of defenders, goalkeeper position)
                    freeze_frame = shot.get('shot_freeze_frame', [])
                    n_defenders = 0
                    n_attackers = 0
                    gk_dist = distance  # default

                    if freeze_frame and isinstance(freeze_frame, list):
                        for player in freeze_frame:
                            is_teammate = player.get('teammate', False)
                            if not is_teammate:
                                n_defenders += 1
                                # Distance from shooter to nearest defender
                                if 'location' in player:
                                    dx = x - player['location'][0]
                                    dy = y - player['location'][1]
                                    def_dist = np.sqrt(dx ** 2 + dy ** 2)
                                    if def_dist < gk_dist:
                                        gk_dist = def_dist
                            else:
                                n_attackers += 1

                    # Target xG
                    xg_target = shot.get('shot_statsbomb_xg', 0.0)
                    if xg_target is None or np.isnan(xg_target):
                        xg_target = 0.0

                    # Goal outcome
                    outcome = shot.get('shot_outcome', 'Off Target')
                    is_goal = 1 if outcome == 'Goal' else 0

                    # Play pattern
                    play_pattern = shot.get('play_pattern', 'Regular')

                    # Game state
                    minute = shot.get('minute', 0)
                    half = 1 if minute is not None and minute <= 45 else 2

                    # Header?
                    is_header = 1 if body_part and 'Head' in str(body_part) else 0

                    # Footedness
                    is_right_foot = 1 if body_part and 'Right' in str(body_part) else 0
                    is_left_foot = 1 if body_part and 'Left' in str(body_part) else 0
                    is_other_body = 1 if not is_right_foot and not is_left_foot else 0

                    # Big chance (proxy: xG > 0.3)
                    big_chance = 1 if xg_target > 0.3 else 0

                    # Distance and angle categories
                    dist_bin = min(int(distance / 5), 12)  # 0-60m in 5m bins
                    angle_bin = min(int(abs(angle) * 4), 8)  # 0-~1.5 rad in ~0.2 rad bins

                    # Build row
                    row = {
                        'match_id': match_id,
                        'team_id': shot.get('possession_team_id', 0),
                        'player_id': shot.get('player_id', 0),
                        'minute': minute,
                        'half': half,
                        'x': x,
                        'y': y,
                        'distance': round(distance, 2),
                        'angle': round(angle, 4),
                        'is_header': is_header,
                        'is_right_foot': is_right_foot,
                        'is_left_foot': is_left_foot,
                        'is_other_body': is_other_body,
                        'shot_type_Open_Play': 1 if shot_type == 'Open Play' else 0,
                        'shot_type_Free_Kick': 1 if shot_type == 'Free Kick' else 0,
                        'shot_type_Penalty': 1 if shot_type == 'Penalty' else 0,
                        'shot_type_Corner': 1 if shot_type == 'Corner' else 0,
                        'shot_type_Throw_In': 1 if 'Throw' in str(shot_type) else 0,
                        'shot_type_Set_Piece': 1 if 'Set' in str(shot_type) else 0,
                        'first_time': 1 if first_time else 0,
                        'one_on_one': 1 if one_on_one else 0,
                        'deflected': 1 if deflected else 0,
                        'redirected': 1 if redirected else 0,
                        'under_pressure': 1 if under_pressure else 0,
                        'n_defenders': n_defenders,
                        'n_attackers': n_attackers,
                        'gk_distance': round(gk_dist, 2),
                        'big_chance': big_chance,
                        'dist_bin': dist_bin,
                        'angle_bin': angle_bin,
                        'xg_target': round(xg_target, 4),
                        'is_goal': is_goal,
                        'outcome': outcome,
                        'play_pattern': str(play_pattern),
                        'technique': str(technique),
                    }
                    all_shots.append(row)

                except Exception as e:
                    continue

        except Exception as e:
            continue

    if not all_shots:
        logger.error("❌ No shots extracted!")
        return pd.DataFrame()

    df = pd.DataFrame(all_shots)
    logger.info(f"✅ Shots extracted: {len(df)} from {match_count} matches")
    logger.info(f"   Goals: {df['is_goal'].sum()} ({df['is_goal'].mean()*100:.2f}%)")
    logger.info(f"   Avg xG: {df['xg_target'].mean():.4f}")
    logger.info(f"   Avg distance: {df['distance'].mean():.1f}m")
    return df


def engineer_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Engineer advanced features for xG prediction.
    Returns feature matrix and feature names.
    """
    logger.info("🔧 Engineering features...")

    # Base features
    base_features = [
        'x', 'y', 'distance', 'angle',
        'is_header', 'is_right_foot', 'is_left_foot', 'is_other_body',
        'shot_type_Open_Play', 'shot_type_Free_Kick', 'shot_type_Penalty',
        'shot_type_Corner', 'shot_type_Throw_In', 'shot_type_Set_Piece',
        'first_time', 'one_on_one', 'deflected', 'redirected', 'under_pressure',
        'n_defenders', 'n_attackers', 'gk_distance',
        'big_chance', 'dist_bin', 'angle_bin', 'half',
    ]

    # Interaction features
    df['dist_angle_interaction'] = df['distance'] * (1 + abs(df['angle']))
    df['dist_squared'] = df['distance'] ** 2
    df['angle_squared'] = df['angle'] ** 2
    df['log_distance'] = np.log1p(df['distance'])
    df['defender_pressure'] = df['n_defenders'] / (df['distance'] + 1)
    df['gk_distance_ratio'] = df['gk_distance'] / (df['distance'] + 0.1)
    df['x_centered'] = abs(df['x'] - 60)  # distance from center horizontally
    df['y_centered'] = abs(df['y'] - 40)  # distance from center vertically
    df['header_under_pressure'] = df['is_header'] * df['under_pressure']

    # Normalized coordinates
    df['x_norm'] = df['x'] / PITCH_LENGTH
    df['y_norm'] = df['y'] / PITCH_WIDTH

    # Distance-angle product (measures shot danger zone)
    df['danger_zone'] = np.exp(-df['distance'] / 20) * (1 + abs(df['angle']) / 1.5)

    extended_features = [
        'dist_angle_interaction', 'dist_squared', 'angle_squared', 'log_distance',
        'defender_pressure', 'gk_distance_ratio', 'x_centered', 'y_centered',
        'header_under_pressure', 'x_norm', 'y_norm', 'danger_zone'
    ]

    all_features = base_features + extended_features

    # Check for NaN and fill
    for col in all_features:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    # Verify all features exist
    available_features = [f for f in all_features if f in df.columns]
    logger.info(f"✅ {len(available_features)} features engineered")
    logger.info(f"   Features: {available_features}")

    return df, available_features


def train_xgboost_model(df: pd.DataFrame, features: List[str]) -> Dict:
    """
    Train XGBoost xG model with proper train/test split.
    Uses match-level split to prevent leakage.
    """
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (roc_auc_score, log_loss, brier_score_loss,
                                 accuracy_score, precision_score, recall_score,
                                 confusion_matrix)
    from sklearn.calibration import CalibratedClassifierCV

    logger.info("🚀 Training XGBoost xG model...")

    # Match-level split
    matches = df['match_id'].unique()
    train_matches, test_matches = train_test_split(
        matches, test_size=0.2, random_state=42
    )

    train_idx = df['match_id'].isin(train_matches)
    test_idx = df['match_id'].isin(test_matches)

    X_train = df.loc[train_idx, features].values
    y_train = df.loc[train_idx, 'is_goal'].values
    X_test = df.loc[test_idx, features].values
    y_test = df.loc[test_idx, 'is_goal'].values

    logger.info(f"   Train: {len(X_train)} shots from {len(train_matches)} matches")
    logger.info(f"   Test:  {len(X_test)} shots from {len(test_matches)} matches")
    logger.info(f"   Train goal rate: {y_train.mean()*100:.2f}%")
    logger.info(f"   Test goal rate:  {y_test.mean()*100:.2f}%")

    # Scale pos_weight for imbalance
    neg_pos_ratio = (y_train == 0).sum() / (y_train == 1).sum()

    # Train XGBoost
    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        scale_pos_weight=neg_pos_ratio,
        objective='binary:logistic',
        eval_metric=['logloss', 'auc'],
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1,
        early_stopping_rounds=50,
    )

    # Train with eval set for early stopping
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_test, y_test)],
        verbose=False
    )

    # Predictions
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    # Metrics
    auc = roc_auc_score(y_test, y_pred_proba)
    brier = brier_score_loss(y_test, y_pred_proba)
    ll = log_loss(y_test, y_pred_proba)

    # Accuracy at different thresholds
    acc_05 = accuracy_score(y_test, (y_pred_proba >= 0.05).astype(int))
    acc_10 = accuracy_score(y_test, (y_pred_proba >= 0.10).astype(int))

    # Log loss of naive model (mean goal rate)
    naive_pred = np.full_like(y_test, y_test.mean())
    naive_ll = log_loss(y_test, naive_pred)

    # Calibration
    from sklearn.calibration import calibration_curve
    prob_true, prob_pred = calibration_curve(y_test, y_pred_proba, n_bins=10)

    logger.info(f"\n📊 === XGBoost xG Model Results ===")
    logger.info(f"   AUC-ROC:         {auc:.4f}")
    logger.info(f"   Brier Score:     {brier:.4f}")
    logger.info(f"   Log Loss:        {ll:.4f} (naive: {naive_ll:.4f})")
    logger.info(f"   Acc@0.05:        {acc_05:.4f}")
    logger.info(f"   Acc@0.10:        {acc_10:.4f}")
    logger.info(f"   Pos/Neg ratio:   {neg_pos_ratio:.2f}")

    # Feature importance
    importance = pd.DataFrame({
        'feature': features,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)

    logger.info(f"\n📈 Top 15 features:")
    for i, (_, row) in enumerate(importance.head(15).iterrows()):
        logger.info(f"   {i+1}. {row['feature']}: {row['importance']:.4f}")

    # Save model
    model_path = MODELS_DIR / 'xg_model.json'
    model.save_model(str(model_path))
    logger.info(f"✅ Model saved to {model_path}")

    # Calibrate model with Platt scaling
    cal_model = CalibratedClassifierCV(model, method='sigmoid', cv=5)
    cal_model.fit(X_train, y_train)
    y_pred_cal = cal_model.predict_proba(X_test)[:, 1]
    cal_brier = brier_score_loss(y_test, y_pred_cal)
    cal_ll = log_loss(y_test, y_pred_cal)

    logger.info(f"\n📊 === Calibrated Model ===")
    logger.info(f"   Brier Score:     {cal_brier:.4f} (was {brier:.4f})")
    logger.info(f"   Log Loss:        {cal_ll:.4f} (was {ll:.4f})")

    # Save calibrated model
    import joblib
    cal_path = MODELS_DIR / 'xg_model_calibrated.pkl'
    joblib.dump(cal_model, str(cal_path))
    logger.info(f"✅ Calibrated model saved to {cal_path}")

    # Save results
    results = {
        'auc_roc': round(auc, 4),
        'brier_score': round(brier, 4),
        'brier_calibrated': round(cal_brier, 4),
        'log_loss': round(ll, 4),
        'log_loss_calibrated': round(cal_ll, 4),
        'log_loss_naive': round(naive_ll, 4),
        'n_train': int(len(X_train)),
        'n_test': int(len(X_test)),
        'n_matches_train': int(len(train_matches)),
        'n_matches_test': int(len(test_matches)),
        'goal_rate_train': round(float(y_train.mean()), 4),
        'goal_rate_test': round(float(y_test.mean()), 4),
        'pos_neg_ratio': round(float(neg_pos_ratio), 2),
        'feature_importance': importance.head(20).to_dict('records'),
        'calibration_curve': {
            'prob_true': [round(float(p), 4) for p in prob_true],
            'prob_pred': [round(float(p), 4) for p in prob_pred],
        },
        'timestamp': datetime.now().isoformat(),
    }

    results_path = MODELS_DIR / 'xg_model_results.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"✅ Results saved to {results_path}")

    return results


def analyze_per_match(df: pd.DataFrame, features: List[str], model) -> pd.DataFrame:
    """Analyze per-match xG performance."""
    logger.info("\n📊 Per-match xG analysis...")

    # Get predictions
    X = df[features].values
    df['predicted_xg'] = model.predict_proba(X)[:, 1]

    # Aggregate per match
    match_xg = df.groupby('match_id').agg({
        'xg_target': 'sum',
        'predicted_xg': 'sum',
        'is_goal': 'sum',
        'match_id': 'count'
    }).rename(columns={'match_id': 'n_shots'})

    match_xg['xg_error'] = match_xg['predicted_xg'] - match_xg['xg_target']
    match_xg['goal_error'] = match_xg['predicted_xg'] - match_xg['is_goal']

    # Per-team analysis
    team_xg = df.groupby('team_id').agg({
        'xg_target': 'sum',
        'predicted_xg': 'sum',
        'is_goal': 'sum',
        'match_id': 'nunique'
    }).rename(columns={'match_id': 'n_matches'})
    team_xg['goals_per_match'] = team_xg['is_goal'] / team_xg['n_matches']

    # Log interesting findings
    total_actual = df['is_goal'].sum()
    total_xg = df['xg_target'].sum()
    total_pred = df['predicted_xg'].sum()

    logger.info(f"   Total actual goals: {total_actual}")
    logger.info(f"   Total StatsBomb xG: {total_xg:.2f}")
    logger.info(f"   Total predicted xG: {total_pred:.2f}")
    logger.info(f"   xG error (pred - actual): {total_pred - total_actual:.2f}")
    logger.info(f"   xG error (pred - statsbomb): {total_pred - total_xg:.2f}")

    # Mean absolute error per match
    mae_xg = abs(match_xg['xg_error']).mean()
    mae_goals = abs(match_xg['goal_error']).mean()
    logger.info(f"   MAE per match (vs StatsBomb xG): {mae_xg:.3f}")
    logger.info(f"   MAE per match (vs actual goals): {mae_goals:.3f}")

    return match_xg


def main():
    """Main execution."""
    print("\n" + "█" * 70)
    print("  AGENT 5 — PHASE 2: STATSBOMB xG MODEL")
    print("  SIGMA-ZERO | DΞMON CORE v9999999 | BLACK CODE CURSE")
    print("█" * 70)

    start = time.time()

    # Step 1: Fetch matches
    print("\n[1/6] Fetching matches from StatsBomb...")
    matches_df = fetch_all_matches()
    if matches_df.empty:
        logger.error("No matches fetched, aborting")
        return 1

    # Step 2: Extract shot events
    print("\n[2/6] Extracting shot events...")
    match_ids = matches_df['match_id'].unique().tolist()
    logger.info(f"   {len(match_ids)} unique matches available")

    shots_df = extract_shot_events(match_ids)
    if shots_df.empty:
        logger.error("No shots extracted, aborting")
        return 1

    # Save raw shots to CSV
    shots_csv = DATA_DIR / 'shots_raw.csv'
    shots_df.to_csv(shots_csv, index=False)
    logger.info(f"✅ Raw shots saved to {shots_csv}")

    # Step 3: Engineer features
    print("\n[3/6] Engineering features...")
    shots_df, features = engineer_features(shots_df)

    # Save feature list
    with open(MODELS_DIR / 'xg_features.json', 'w') as f:
        json.dump({'features': features, 'n_features': len(features)}, f, indent=2)

    # Step 4: Train model
    print("\n[4/6] Training XGBoost xG model...")
    results = train_xgboost_model(shots_df, features)

    # Step 5: Per-match analysis
    print("\n[5/6] Analyzing per-match xG...")
    import xgboost as xgb
    import joblib

    # Load model for analysis
    if (MODELS_DIR / 'xg_model.json').exists():
        model = xgb.XGBClassifier()
        model.load_model(str(MODELS_DIR / 'xg_model.json'))

        # Get calibrated model if available
        if (MODELS_DIR / 'xg_model_calibrated.pkl').exists():
            cal_model = joblib.load(str(MODELS_DIR / 'xg_model_calibrated.pkl'))
            match_xg = analyze_per_match(shots_df, features, cal_model)
        else:
            match_xg = analyze_per_match(shots_df, features, model)

        match_xg.to_csv(DATA_DIR / 'match_xg_analysis.csv')
        logger.info(f"✅ Match xG analysis saved")

    # Step 6: Summary
    elapsed = time.time() - start
    print("\n[6/6] Summary")

    print("\n" + "=" * 60)
    print(f"  ✅✅ STATSBOMB xG MODEL COMPLETE ✅✅")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Matches processed: {len(match_ids)}")
    print(f"  Shots extracted: {len(shots_df)}")
    print(f"  Features: {len(features)}")
    print(f"  AUC-ROC: {results.get('auc_roc', 'N/A')}")
    print(f"  Brier:   {results.get('brier_score', 'N/A')}")
    print(f"  Models saved to:")
    print(f"    models/xg_model.json")
    print(f"    models/xg_model_calibrated.pkl")
    print(f"  Data saved to:")
    print(f"    statsbomb_data/shots_raw.csv")
    print(f"    statsbomb_data/match_xg_analysis.csv")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

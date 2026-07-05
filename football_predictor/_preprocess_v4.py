"""Preprocess training data once, save to npz for instant V4 loading"""
import sys, os, json, time, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data, FEATURES, NUM_CLASSES
import gc

t0 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] Loading training data for 675K matches...')
X, y, mids = _load_training_data()
print(f'[{time.strftime("%H:%M:%S")}] Loaded: {len(X):,} samples, {X.shape[1]} features')
print(f'Elapsed: {(time.time()-t0)/60:.1f} min')

import joblib
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
np.savez_compressed(os.path.join(MODEL_DIR, 'v4_preprocessed.npz'), X=X, y=y, mids=mids,
    features_shape=np.array([X.shape[1]]))
print(f'Saved to v4_preprocessed.npz')
print(f'Total time: {(time.time()-t0)/60:.1f} min')

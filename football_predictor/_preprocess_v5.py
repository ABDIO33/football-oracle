"""Preprocess 887K matches for V5 training"""
import sys, os, json, time, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from direct_predictor import _load_training_data
import gc

t0 = time.time()
print(f'[{time.strftime("%H:%M:%S")}] Loading 887K matches with walkforward...')
X, y, mids = _load_training_data()
print(f'[{time.strftime("%H:%M:%S")}] Loaded {len(X):,} samples, {X.shape[1]} features in {(time.time()-t0)/60:.1f} min')

import joblib
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
np.savez_compressed(os.path.join(MODEL_DIR, 'v5_preprocessed.npz'), X=X, y=y, mids=mids)
print(f'Saved v5_preprocessed.npz ({len(X):,})')

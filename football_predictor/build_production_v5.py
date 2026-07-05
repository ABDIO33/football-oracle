"""
Build V5 production model from training artifacts
Saves as v5_model.pkl (compatible with predict_match)
"""
import sys, os, json, time, numpy as np, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

import torch, torch.nn as nn
import xgboost as xgb
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'v5_production_log.txt')

def log(msg):
    with open(LOG, 'a') as f:
        f.write(f'[{time.strftime("%H:%M:%S")}] {msg}\n')
    print(f'[{time.strftime("%H:%M:%S")}] {msg}')

log('Building V5 production model...')

# Check V5 results
results_file = os.path.join(MODEL_DIR, 'v5_results.json')
if not os.path.exists(results_file):
    log('ERROR: V5 results not found. Training may still be running.')
    exit(1)

results = json.load(open(results_file))
ensemble_acc = results['ensemble']['exact_pct']
log(f'V5 Ensemble: {ensemble_acc}% exact')

class M5Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layers):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layers):
            modules += [nn.Linear(prev, sz)]
            if sz >= 64: modules += [nn.BatchNorm1d(sz)]
            modules += [nn.ELU(), nn.Dropout(0.25 * (0.5 if i == len(layers)-1 else 1.0))]
            prev = sz
        modules += [nn.Linear(prev, num_classes)]
        self.net = nn.Sequential(*modules)
    def forward(self, x): return self.net(x)

ARCHS = {
    'M5_small_v5': [128, 256, 128],
    'M5_medium_v5': [256, 512, 256],
    'M5_wide_v5': [1024, 512, 256],
    'M5_deep_v5': [256, 512, 256, 128],
    'M5_big_v5': [512, 1024, 512],
}

# Load imputer + scaler
imp = joblib.load(os.path.join(MODEL_DIR, 'v5_imputer.pkl'))
scaler = joblib.load(os.path.join(MODEL_DIR, 'v5_scaler.pkl'))
input_dim = imp.statistics_.shape[0]
log(f'Input dim: {input_dim}')

# Load all models + weights
weights = results['weights']
models = {}
for name, layers in ARCHS.items():
    pt_file = os.path.join(MODEL_DIR, f'{name}.pt')
    if os.path.exists(pt_file):
        m = M5Variant(input_dim, 25, layers)
        m.load_state_dict(torch.load(pt_file, map_location='cpu'))
        m.eval()
        models[name] = m
        log(f'  Loaded {name} (weight={weights.get(name, 0)*100:.0f}%)')

# Load XGBoost
xgb_file = os.path.join(MODEL_DIR, 'xgb_v5.pkl')
if os.path.exists(xgb_file):
    xgb_model = joblib.load(xgb_file)
    models['xgb_v5'] = xgb_model
    log(f'  Loaded xgb_v5 (weight={weights.get("xgb_v5", 0)*100:.0f}%)')

# Save production model
class V5Ensemble:
    def __init__(self, models, weights, imp, scaler):
        self.models = models
        self.weights = weights
        self.imp = imp
        self.scaler = scaler
        self.num_classes = 25
    
    def predict_proba(self, X):
        X_imp = self.imp.transform(X)
        X_s = self.scaler.transform(X_imp)
        ensemble = np.zeros((X_s.shape[0], 25))
        for name, m in self.models.items():
            w = self.weights.get(name, 0)
            if w == 0: continue
            if name == 'xgb_v5':
                proba = m.predict_proba(X_s)
            else:
                with torch.no_grad():
                    proba = torch.softmax(m(torch.tensor(X_s, dtype=torch.float32)), dim=1).numpy()
            ensemble += w * proba
        return ensemble

prod = V5Ensemble(models, weights, imp, scaler)
prod_path = os.path.join(MODEL_DIR, 'v5_model.pkl')
joblib.dump(prod, prod_path)
size_mb = os.path.getsize(prod_path) / (1024*1024)
log(f'Saved v5_model.pkl ({size_mb:.0f} MB)')

# Test with a dummy vector
dummy = np.zeros((1, input_dim), dtype=np.float32)
proba = prod.predict_proba(dummy)
log(f'Test prediction OK: {proba.shape}')

log(f'\nProduction model ready!')
log(f'V5 Ensemble: {ensemble_acc}% exact score')
if ensemble_acc > 26:
    log('🏆 NEW WORLD BEST!')
elif ensemble_acc > 25.89:
    log('✅ BEAT V3!')

# Update the main model path for predict_match
import shutil
shutil.copy(prod_path, os.path.join(MODEL_DIR, 'v3_model.pkl'))
log('Also saved as v3_model.pkl (will be auto-loaded by predict_match)')

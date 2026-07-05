"""
Builds production-ready V3 model from saved checkpoints
"""
import sys, os, json, joblib, numpy as np
import torch, torch.nn as nn
sys.path.insert(0, os.path.dirname(__file__))

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

class M5_Variant(nn.Module):
    def __init__(self, input_dim, num_classes, layer_sizes, dropout_rate=0.25):
        super().__init__()
        modules = []
        prev = input_dim
        for i, sz in enumerate(layer_sizes):
            modules.append(nn.Linear(prev, sz))
            if sz >= 64:
                modules.append(nn.BatchNorm1d(sz))
            modules.append(nn.ELU())
            modules.append(nn.Dropout(dropout_rate * (0.5 if i == len(layer_sizes)-1 else 1.0)))
            prev = sz
        modules.append(nn.Linear(prev, num_classes))
        self.net = nn.Sequential(*modules)
    def forward(self, x):
        return self.net(x)

class TorchWrapper:
    def __init__(self, input_dim, num_classes, layers, state_dict):
        self.input_dim = input_dim
        self.num_classes = num_classes
        self.layers = layers
        self.state_dict = {k: (v.cpu().numpy() if isinstance(v, torch.Tensor) else v) for k, v in state_dict.items()}
        self._model = None
    
    def _build(self):
        if self._model is None:
            self._model = M5_Variant(self.input_dim, self.num_classes, self.layers)
            sd = {k: torch.tensor(v) for k, v in self.state_dict.items()}
            self._model.load_state_dict(sd)
            self._model.eval()
        return self._model
    
    def predict_proba(self, X):
        m = self._build()
        with torch.no_grad():
            return torch.softmax(m(torch.tensor(X, dtype=torch.float32)), dim=1).numpy()
    
    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)

class V3EnsemblePredictor:
    def __init__(self, model_dir):
        results = json.load(open(os.path.join(model_dir, 'v3_results.json')))
        ARCHS = {
            'M5_small_v3': [128, 256, 128],
            'M5_medium_v3': [256, 512, 256],
            'M5_big_v3': [512, 1024, 512],
            'M5_wide_v3': [1024, 512, 256],
            'M5_deep_v3': [256, 512, 256, 128],
        }
        self.weights = results['weights']
        self.model_names = results['model_names']
        self.models = {}
        for name in self.model_names:
            if name == 'xgb_v3':
                self.models[name] = joblib.load(os.path.join(model_dir, 'xgb_v3.pkl'))
            else:
                sd = torch.load(os.path.join(model_dir, f'{name}.pt'), map_location='cpu')
                self.models[name] = TorchWrapper(85, 25, ARCHS[name], sd)
        self.imputer = joblib.load(os.path.join(model_dir, 'checkpoint_imputer.pkl'))
        self.scaler = joblib.load(os.path.join(model_dir, 'checkpoint_scaler.pkl'))
    
    def predict_proba(self, X):
        X_s = self.scaler.transform(self.imputer.transform(X))
        ep = None
        for name in self.model_names:
            p = self.models[name].predict_proba(X_s)
            w = self.weights.get(name, 0)
            if ep is None:
                ep = p * w
            else:
                ep += p * w
        return ep
    
    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)

if __name__ == '__main__':
    print('Building V3 production model...')
    
    # Load test data directly (already preprocessed)
    data = np.load(os.path.join(MODEL_DIR, 'preprocessed_data.npz'), allow_pickle=True)
    X_test_s = data['X_test_s']
    y_test = data['y_test']
    
    # Reverse transform: we need original (with NaNs)
    scaler = joblib.load(os.path.join(MODEL_DIR, 'checkpoint_scaler.pkl'))
    X_test_unscaled = scaler.inverse_transform(X_test_s)
    
    # Test prediction using V3EnsemblePredictor
    predictor = V3EnsemblePredictor(MODEL_DIR)
    preds = predictor.predict(X_test_unscaled)
    exact = float(np.mean(preds == y_test))
    
    def cs(c): return (c // 5, c % 5)
    def res(h, a): return 0 if h > a else (1 if h == a else 2)
    a1x2 = np.array([res(*cs(c)) for c in y_test])
    p1x2 = np.array([res(*cs(c)) for c in preds])
    a1 = float(np.mean(p1x2 == a1x2))
    
    print(f'Exact: {exact*100:.2f}%  1X2: {a1*100:.2f}%')
    
    # Save
    path = os.path.join(MODEL_DIR, 'v3_model.pkl')
    joblib.dump(predictor, path)
    print(f'Saved v3_model.pkl ({os.path.getsize(path)/1e6:.0f} MB)')

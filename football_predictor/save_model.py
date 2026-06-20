"""Save XGBoost model + metrics"""
import sys, numpy as np, pickle, os, json
sys.path.insert(0, '.')
from direct_predictor import _load_training_data
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import LabelEncoder
import xgboost as xgb

print('Loading + training...')
X, y, ids = _load_training_data()
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
imp = SimpleImputer(strategy='median')
X_train_i = imp.fit_transform(X_train)
X_test_i = imp.transform(X_test)
le = LabelEncoder()
y_train_enc = le.fit_transform(y_train)
y_test_enc = le.transform(y_test)

model = xgb.XGBClassifier(n_estimators=700, max_depth=6, learning_rate=0.08, subsample=0.8, colsample_bytree=0.8, objective='multi:softprob', num_class=25, eval_metric='mlogloss', random_state=42, n_jobs=-1)
model.fit(X_train_i, y_train_enc)

probs = model.predict_proba(X_test_i)
preds = np.argmax(probs, axis=1)
exact = (preds == y_test_enc).mean()

hda_pred = np.zeros((len(y_test_enc), 3))
for i in range(25):
    h, a = i // 5, i % 5
    hda_pred[:, 0 if h > a else 1 if h == a else 2] += probs[:, i]
true_hda = np.array([0 if h > a else 1 if h == a else 2 for h in range(5) for a in range(5)])
hda_acc = (np.argmax(hda_pred, axis=1) == true_hda[y_test_enc]).mean()

def calc_rps(probs, true_labels):
    rps_list = []
    for i in range(len(true_labels)):
        p = probs[i]
        cp = np.cumsum([sum(p[j] for j in range(25) if j // 5 > j % 5), sum(p[j] for j in range(25) if j // 5 == j % 5), sum(p[j] for j in range(25) if j // 5 < j % 5)])
        ct = np.array([1 if true_labels[i] <= k else 0 for k in range(3)])
        rps_list.append(np.mean((cp - ct) ** 2))
    return np.mean(rps_list)

rps = calc_rps(probs, y_test_enc)

print(f'\nXGBoost: Exact={exact*100:.2f}%  1X2={hda_acc*100:.2f}%  RPS={rps:.4f}')

model.save_model('models/direct_score.ubj')
results = {'best_exact': round(exact*100,2), 'best_1x2': round(hda_acc*100,2), 'best_rps': round(rps,4), 'samples': len(X)}
with open('models/ensemble_results.json','w') as f:
    json.dump(results, f, indent=2)
sz = os.path.getsize('models/direct_score.ubj') / 1e6
print(f'Saved! Size: {sz:.0f} MB')

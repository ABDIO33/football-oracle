"""
calibration_v2.py — 3-layer calibration for 25-class score predictions
Layer 1: Temperature Scaling (DeepNN logit calibration)
Layer 2: Per-class Platt/Isotonic hybrid (score-level calibration)
Layer 3: Beta calibration for draw marginal
"""
import sqlite3, os, json, time, numpy as np
from collections import defaultdict
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from scipy.optimize import minimize
from scipy.stats import beta as beta_dist
import joblib

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
LOG = os.path.join(MODEL_DIR, 'calibration_v2_log.txt')
_EVAL_DB = os.path.join(os.path.dirname(__file__), 'evaluation.db')

NUM_CLASSES = 25
SCORE_CLASSES = [(h, a) for h in range(5) for a in range(5)]


def log(msg):
    ts = time.strftime("%H:%M:%S")
    with open(LOG, 'a') as f:
        f.write(f'[{ts}] {msg}\n')
    print(f'[{ts}] {msg}')


def _result(h, a):
    return 0 if h > a else (1 if h == a else 2)


def _1x2_from_25(probas):
    """Convert 25-class score probas to 3-class 1X2."""
    n = len(probas)
    out = np.zeros((n, 3))
    for i in range(n):
        p = probas[i]
        out[i, 0] = sum(p[h*5 + a] for h in range(5) for a in range(5) if h > a)
        out[i, 1] = sum(p[h*5 + h] for h in range(5))
        out[i, 2] = sum(p[h*5 + a] for h in range(5) for a in range(5) if a > h)
    return out


# ═══════════════════════════════════════════════════════════
# LAYER 1: Temperature Scaling
# ═══════════════════════════════════════════════════════════

def fit_temperature(logits, y_true, init_temp=1.0):
    """Fit temperature scaling parameter using NLL."""
    def nll(T):
        scaled = logits / T
        shifted = scaled - scaled.max(axis=1, keepdims=True)
        exp_s = np.exp(shifted)
        probs = exp_s / exp_s.sum(axis=1, keepdims=True)
        nll_val = -np.mean(np.log(probs[np.arange(len(y_true)), y_true] + 1e-15))
        return nll_val + 0.001 * (T - 1.0) ** 2

    result = minimize(nll, init_temp, method='L-BFGS-B', bounds=[(0.1, 10.0)])
    return float(result.x[0]) if result.success else 1.0


def apply_temperature(logits, T):
    return logits / T


# ═══════════════════════════════════════════════════════════
# LAYER 2: Per-class Platt/Isotonic Calibration
# ═══════════════════════════════════════════════════════════

def fit_per_class_calibrators(probas, y_true, rare_threshold=0.01):
    """
    Fit per-class calibrators for all 25 score classes.
    Uses Platt (LogisticRegression) for rare scores (<1% prevalence),
    Isotonic for common scores.
    """
    n = len(probas)
    n_classes = probas.shape[1]
    calibrators = [None] * n_classes
    class_prevalence = np.bincount(y_true, minlength=n_classes) / n

    for cls in range(n_classes):
        y_binary = (y_true == cls).astype(float)
        p_cls = probas[:, cls]

        if class_prevalence[cls] < rare_threshold:
            cal = LogisticRegression(C=1.0, class_weight='balanced')
            cal.fit(p_cls.reshape(-1, 1), y_binary)
        else:
            cal = IsotonicRegression(out_of_bounds='clip')
            cal.fit(p_cls, y_binary)

        calibrators[cls] = cal

    return calibrators, class_prevalence


def apply_per_class_calibration(probas, calibrators, class_prevalence):
    """Apply per-class calibrators and renormalize."""
    n, n_classes = probas.shape
    calibrated = np.zeros_like(probas)

    for cls in range(n_classes):
        cal = calibrators[cls]
        if isinstance(cal, LogisticRegression):
            calibrated[:, cls] = cal.predict_proba(probas[:, cls].reshape(-1, 1))[:, 1]
        elif isinstance(cal, IsotonicRegression):
            calibrated[:, cls] = cal.predict(probas[:, cls])

    calibrated = np.clip(calibrated, 1e-15, None)
    calibrated /= calibrated.sum(axis=1, keepdims=True)
    return calibrated


# ═══════════════════════════════════════════════════════════
# LAYER 3: Beta Calibration for Draw Marginal
# ═══════════════════════════════════════════════════════════

def fit_beta_calibration(draw_probas, y_1x2):
    """Fit Beta calibration for draw probabilities."""
    y_draw = (y_1x2 == 1).astype(float)

    def neg_ll(params):
        a, b, c = params
        if a <= 0 or b <= 0 or c <= 0 or c >= 1:
            return 1e10
        p_cal = c * beta_dist.cdf(draw_probas, a, b) + (1 - c) * draw_probas
        p_cal = np.clip(p_cal, 1e-15, 1 - 1e-15)
        return -np.mean(y_draw * np.log(p_cal) + (1 - y_draw) * np.log(1 - p_cal))

    result = minimize(neg_ll, [1.5, 1.5, 0.05], method='L-BFGS-B',
                      bounds=[(0.01, 10), (0.01, 10), (0.0, 1.0)])
    return result.x if result.success else [1.0, 1.0, 0.0]


def apply_beta_calibration(draw_probas, beta_params):
    a, b, c = beta_params
    return c * beta_dist.cdf(draw_probas, a, b) + (1 - c) * draw_probas


# ═══════════════════════════════════════════════════════════
# Full CalibrationPipeline
# ═══════════════════════════════════════════════════════════

class CalibrationPipeline:
    """3-layer calibration for 25-class score predictions."""

    def __init__(self, T=1.0, per_class_calibrators=None, class_prevalence=None,
                 beta_params=None):
        self.T = T
        self.per_class_calibrators = per_class_calibrators
        self.class_prevalence = class_prevalence
        self.beta_params = beta_params

    def fit(self, logits, y_true, probas_25=None):
        """Fit all 3 layers."""
        log('[Layer 1] Fitting temperature scaling...')
        self.T = fit_temperature(logits, y_true)
        log(f'  Temperature T={self.T:.4f}')

        logits_calibrated = apply_temperature(logits, self.T)
        temp_probas = np.exp(logits_calibrated - logits_calibrated.max(axis=1, keepdims=True))
        temp_probas /= temp_probas.sum(axis=1, keepdims=True)

        log('[Layer 2] Fitting per-class calibrators...')
        self.per_class_calibrators, self.class_prevalence = fit_per_class_calibrators(
            temp_probas, y_true)
        log(f'  {sum(1 for c in self.class_prevalence if c < 0.01)} rare classes → Platt')
        log(f'  {sum(1 for c in self.class_prevalence if c >= 0.01)} common classes → Isotonic')

        if probas_25 is None:
            probas_25 = temp_probas
        cal_25 = apply_per_class_calibration(
            probas_25, self.per_class_calibrators, self.class_prevalence)

        log('[Layer 3] Fitting beta calibration for draws...')
        y_1x2 = np.array([_result(*divmod(int(c), 5)) for c in y_true])
        draw_marginals = _1x2_from_25(cal_25)[:, 1]
        self.beta_params = fit_beta_calibration(draw_marginals, y_1x2)
        log(f'  Beta params: a={self.beta_params[0]:.3f}, b={self.beta_params[1]:.3f}, c={self.beta_params[2]:.3f}')

        return self

    def predict_proba(self, logits=None, probas_25=None):
        """Apply calibration in sequence."""
        if logits is not None:
            logits_cal = apply_temperature(logits, self.T)
            probas = np.exp(logits_cal - logits_cal.max(axis=1, keepdims=True))
            probas /= probas.sum(axis=1, keepdims=True)
        elif probas_25 is not None:
            probas = probas_25.copy()
        else:
            raise ValueError("Need logits or probas_25")

        if self.per_class_calibrators is not None:
            probas = apply_per_class_calibration(
                probas, self.per_class_calibrators, self.class_prevalence)

        if self.beta_params is not None:
            draw_idx = _1x2_from_25(probas)[:, 1]
            beta_calibrated = apply_beta_calibration(draw_idx, self.beta_params)
            for i in range(len(probas)):
                for h in range(5):
                    for a in range(5):
                        if h == a:
                            probas[i, h*5 + h] *= beta_calibrated[i] / max(draw_idx[i], 1e-10)
            probas /= probas.sum(axis=1, keepdims=True)

        return probas

    def save(self, path=None):
        if path is None:
            path = os.path.join(MODEL_DIR, 'calibration_v2.pkl')
        joblib.dump(self, path)
        log(f'Calibration pipeline saved to {path}')

    @staticmethod
    def load(path=None):
        if path is None:
            path = os.path.join(MODEL_DIR, 'calibration_v2.pkl')
        return joblib.load(path)


# ═══════════════════════════════════════════════════════════
# Training Entry Point
# ═══════════════════════════════════════════════════════════

def train_calibration():
    """Train the full calibration pipeline on evaluation data."""
    log('='*60)
    log('CALIBRATION V2 TRAINING')
    log('='*60)

    try:
        conn = sqlite3.connect(_EVAL_DB)
        cur = conn.execute(
            "SELECT prediction_json, actual_result FROM eval_predictions WHERE status='resolved'"
        )
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        log(f'Error loading evaluation data: {e}')
        return None

    if len(rows) < 100:
        log(f'Not enough evaluation data: {len(rows)} < 100')
        return None

    records = []
    for row in rows:
        pred = json.loads(row[0])
        actual = row[1].strip().upper()
        records.append({
            'prediction': pred,
            'actual': actual,
        })

    y_true = []
    logits_list = []
    probas_25_list = []

    for r in records:
        pred = r['prediction']
        if 'score_probas' in pred:
            probas = np.array(pred['score_probas'])
            probas_25_list.append(probas)
        if 'score_logits' in pred:
            logits = np.array(pred['score_logits'])
            logits_list.append(logits)
        actual = r['actual']
        if isinstance(actual, str) and '-' in actual:
            parts = actual.split('-')
            if len(parts) == 2:
                try:
                    h, a = int(parts[0]), int(parts[1])
                    hc, ac = min(h, 4), min(a, 4)
                    y_true.append(hc * 5 + ac)
                except:
                    continue

    if len(y_true) < 100:
        log(f'Not enough parseable results: {len(y_true)}')
        return None

    y_true = np.array(y_true)
    n = len(y_true)

    if len(logits_list) == n:
        logits_arr = np.array(logits_list)
    else:
        logits_arr = None
        log(f'No logits available, using probas only')

    if len(probas_25_list) == n:
        probas_25_arr = np.array(probas_25_list)
    else:
        probas_25_arr = None

    log(f'Loaded {len(records)} evaluation records, {len(y_true)} usable')

    pipeline = CalibrationPipeline()
    pipeline.fit(logits_arr, y_true, probas_25_arr)
    pipeline.save()

    y_1x2 = np.array([_result(*divmod(int(c), 5)) for c in y_true])

    uncal_probas = probas_25_arr if probas_25_arr is not None else (
        np.exp(logits_arr - logits_arr.max(axis=1, keepdims=True)) /
        np.exp(logits_arr - logits_arr.max(axis=1, keepdims=True)).sum(axis=1, keepdims=True)
        if logits_arr is not None else None)

    if uncal_probas is not None:
        cal_probas = pipeline.predict_proba(logits=logits_arr, probas_25=probas_25_arr)

        uncal_pred = np.argmax(uncal_probas, axis=1)
        cal_pred = np.argmax(cal_probas, axis=1)

        uncal_exact = np.mean(uncal_pred == y_true) * 100
        cal_exact = np.mean(cal_pred == y_true) * 100

        log(f'Uncalibrated exact: {uncal_exact:.2f}%')
        log(f'Calibrated exact:   {cal_exact:.2f}%')
        log(f'Change: {cal_exact - uncal_exact:+.2f}pp')

    log('='*60)
    return pipeline


if __name__ == '__main__':
    train_calibration()

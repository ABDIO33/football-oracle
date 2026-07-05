"""
mega_pipeline_v62.py — End-to-end V6.2 Pipeline for Score Exact 100
يدمج:
  1. _preprocess_v62.py → 194 features
  2. train_v62.py → 7 architectures + XGBoost + ensemble
  3. stacking_v2.py → LightGBM meta-learner
  4. calibration_v2.py → 3-layer calibration
  5. تقرير الأداء النهائي

المشروع: Score Exact 100
القائد: DeepSeek V4 Flash Free الأول
"""
import sys, os, json, time, numpy as np, warnings, gc, subprocess, traceback
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

BASE = os.path.dirname(__file__)
MODEL_DIR = os.path.join(BASE, 'models')
LOG = os.path.join(MODEL_DIR, 'mega_pipeline_v62_log.txt')

def log(msg):
    ts = time.strftime("%H:%M:%S")
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {msg}\n')
    print(f'[{ts}] {msg}', flush=True)


def run_step(name, script, *args):
    """Run a Python script as a subprocess and log it"""
    log(f'\n{"="*60}')
    log(f'STEP: {name}')
    log(f'Script: {script} {" ".join(args)}')
    log(f'{"="*60}')
    
    t0 = time.time()
    cmd = [sys.executable, script] + list(args)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=72000)  # 20h max
        elapsed = time.time() - t0
        
        # Log output
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                log(f'  {line}')
        
        if result.stderr:
            stderr_lines = result.stderr.strip().split('\n')
            # Only log last 20 lines of stderr (or errors)
            error_lines = [l for l in stderr_lines if 'Error' in l or 'Traceback' in l or 'error' in l.lower()]
            if error_lines:
                for line in error_lines[:10]:
                    log(f'  ⚠️ {line}')
            elif len(stderr_lines) > 20:
                log(f'  ⚠️ ... ({len(stderr_lines)} stderr lines, showing last 5)')
                for line in stderr_lines[-5:]:
                    log(f'  {line}')
            else:
                for line in stderr_lines:
                    log(f'  {line}')
        
        if result.returncode != 0:
            log(f'❌ STEP FAILED (rc={result.returncode}) after {elapsed:.0f}s')
            return False
        
        log(f'✅ Step completed in {elapsed:.0f}s ({elapsed/60:.1f}min)')
        return True
    
    except subprocess.TimeoutExpired:
        log(f'❌ STEP TIMEOUT after 20h')
        return False
    except Exception as e:
        log(f'❌ STEP EXCEPTION: {e}')
        traceback.print_exc()
        return False


def check_results():
    """Verify all output files exist and report results"""
    log('\n' + '='*60)
    log('VERIFICATION OF RESULTS')
    log('='*60)
    
    checks = {
        'V6.2 Preprocessed Data': 'v62_preprocessed.npz',
        'V6.2 Imputer': 'v62_imputer.pkl',
        'V6.2 Scaler': 'v62_scaler.pkl',
        'V6.2 Features': 'v62_features.pkl',
        'V6.2 Results': 'v62_results.json',
        'V6.2 Test Probas': 'v62_test_probas.npy',
        'V6.2 All Probas': 'v62_all_probas.npy',
        'V6.2 Model Names': 'v62_model_names.pkl',
        'Stacking V2': 'stacking_v2.pkl',
        'Stacking V2 Results': 'stacking_v2_results.json',
        'Calibration V2': 'calibration_v2.pkl',
    }
    
    missing = []
    for name, fname in checks.items():
        path = os.path.join(MODEL_DIR, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            log(f'  ✅ {name}: {fname} ({size/1024:.0f} KB)')
        else:
            log(f'  ❌ {name}: {fname} MISSING')
            missing.append(name)
    
    return len(missing) == 0


def build_final_report():
    """Build final performance report"""
    log('\n' + '='*60)
    log('BUILDING FINAL REPORT')
    log('='*60)
    
    results_path = os.path.join(MODEL_DIR, 'v62_results.json')
    stacking_path = os.path.join(MODEL_DIR, 'stacking_v2_results.json')
    
    report = {
        'pipeline': 'V6.2 Mega Pipeline',
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'features': 194,
        'architectures': 7,
        'results': {},
        'stacking': None,
    }
    
    try:
        with open(results_path) as f:
            report['results'] = json.load(f)
    except:
        report['results'] = {'error': 'not available'}
    
    try:
        with open(stacking_path) as f:
            report['stacking'] = json.load(f)
    except:
        report['stacking'] = {'error': 'not available'}
    
    # Save report
    report_path = os.path.join(MODEL_DIR, 'mega_pipeline_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    log('\n' + '-'*40)
    log('FINAL PERFORMANCE SUMMARY')
    log('-'*40)
    
    if 'ensemble' in report['results']:
        e = report['results']['ensemble']
        log(f'V6.2 Ensemble Exact: {e.get("exact_pct", "?")}%')
        log(f'V6.2 Ensemble 1X2:   {e.get("1x2_pct", "?")}%')
        log(f'V6.2 Ensemble RPS:   {e.get("rps", "?")}')
    
    if report['stacking']:
        for name, scores in report['stacking'].items():
            if isinstance(scores, dict):
                log(f'Stacking {name}: exact={scores.get("exact", "?")}%')
    
    log('-'*40)
    return report


def main():
    """Run the complete V6.2 pipeline"""
    log('='*60)
    log('MEGA PIPELINE V6.2 — Score Exact 100')
    log('194 features → 7 architectures → Stacking → Calibration')
    log('='*60)
    
    pipeline_t0 = time.time()
    
    # ─── Step 1: Preprocess (build 194 features) ───
    log('\n⚠️ IMPORTANT: Data preprocessing will take ~30 min for full 887K matches')
    log('⚠️ Using 2010+ data with chronological split (2025 cutoff)')
    
    success = run_step('Preprocess (194 features)', '_preprocess_v62.py')
    if not success:
        log('❌ PREPROCESS FAILED — aborting pipeline')
        return False
    
    # ─── Step 2: Train V6.2 (7 architectures + XGBoost) ───
    log('\n⚠️ Training 7 architectures × 200 epochs = ~5-10 hours')
    
    success = run_step('Train V6.2 (7 arch + XGBoost)', 'train_v62.py')
    if not success:
        log('❌ TRAINING FAILED — stacking/calibration may still work with partial results')
    
    # ─── Step 3: Stacking V2 (LightGBM meta-learner) ───
    log('\n⚠️ Stacking V2: OOF probabilities → LightGBM meta-learner')
    
    success = run_step('Stacking V2', 'stacking_v2.py')
    if not success:
        log('⚠️ Stacking V2 failed — trying legacy stacking_ensemble...')
        run_step('Stacking Legacy', 'stacking_ensemble.py')
    
    # ─── Step 4: Calibration V2 (3-layer) ───
    log('\n⚠️ Calibration V2: Temperature + Per-class + Beta')
    
    success = run_step('Calibration V2', 'calibration_v2.py')
    if not success:
        log('⚠️ Calibration V2 failed — trying legacy calibration...')
        run_step('Calibration Legacy', 'calibration.py')
    
    # ─── Step 5: Verify results ───
    log('\n' + '='*60)
    log('VERIFYING RESULTS')
    log('='*60)
    
    all_ok = check_results()
    report = build_final_report()
    
    total_time = (time.time() - pipeline_t0) / 60
    log(f'\n{"="*60}')
    log(f'PIPELINE COMPLETE in {total_time:.0f} minutes ({total_time/60:.1f} hours)')
    log(f'All checks passed: {all_ok}')
    log(f'{"="*60}')
    
    return all_ok


def quick_test():
    """Quick end-to-end test with 2% sample"""
    log('='*60)
    log('QUICK TEST — V6.2 Pipeline (2% sample, 50 epochs)')
    log('='*60)
    
    pipeline_t0 = time.time()
    
    # Quick preprocess
    log('\n[1/4] Quick preprocess (1% sample)...')
    from _preprocess_v62 import build_v62_dataset
    result = build_v62_dataset(start_year=2010, test_cutoff='2025-01-01', sample_pct=0.01)
    Xtr, Xte, ytr, yte, features, imp, scaler = result
    log(f'Data: {len(Xtr)} train, {len(Xte)} test, {Xtr.shape[1]} features')
    
    # Quick train (small model, few epochs)
    log('\n[2/4] Quick train (M5_small, 10 epochs)...')
    import torch, torch.nn as nn
    from train_v62 import M5Variant, LabelSmoothingLoss, train_model
    
    train_ds = torch.utils.data.TensorDataset(
        torch.tensor(Xtr, dtype=torch.float32),
        torch.tensor(ytr, dtype=torch.long))
    val_ds = torch.utils.data.TensorDataset(
        torch.tensor(Xte, dtype=torch.float32),
        torch.tensor(yte, dtype=torch.long))
    tl = torch.utils.data.DataLoader(train_ds, 256, True)
    vl = torch.utils.data.DataLoader(val_ds, 512)
    
    model = M5Variant(Xtr.shape[1], 25, [128, 256, 128], dr=0.25)
    criterion = LabelSmoothingLoss(smoothing=0.1, gamma=2.0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=10, eta_min=1e-5)
    
    best_val, best_ep = train_model(
        model, tl, vl, criterion, optimizer, scheduler, 10, 
        torch.device('cpu'), use_mixup=True)
    
    # Quick stacking test
    log('\n[3/4] Quick stacking test...')
    try:
        from stacking_v2 import train_stacking_v2
        # Skip actual long stacking for quick test
        log('  (skipped in quick mode)')
    except Exception as e:
        log(f'  stacking check: {e}')
    
    # Quick calibration test
    log('\n[4/4] Quick calibration test...')
    try:
        from calibration_v2 import train_calibration
        log('  ✅ calibration_v2.train_calibration() found')
    except Exception as e:
        log(f'  calibration check: {e}')
    
    total_time = (time.time() - pipeline_t0) / 60
    log(f'\nQuick test completed in {total_time:.1f} min')
    log(f'Model validation exact: {best_val:.2f}%')
    
    return True


if __name__ == '__main__':
    if '--quick' in sys.argv:
        quick_test()
    elif '--check' in sys.argv:
        check_results()
    else:
        main()

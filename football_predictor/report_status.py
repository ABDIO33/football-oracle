# -*- coding: utf-8 -*-
"""تقرير التدريب الحالي"""
import sqlite3, json, os, time, subprocess

print('='*55)
print('   🏆 تقرير التدريب — الحالة الحالية')
print('='*55)

# 1. Infinite trainer
print()
print('[1] Infinite Trainer:')
if os.path.exists('training_results.db'):
    conn = sqlite3.connect('training_results.db')
    cnt = conn.execute('SELECT COUNT(*) FROM results').fetchone()[0]
    best = conn.execute('SELECT MAX(test_exact) FROM results').fetchone()[0]
    avg = conn.execute('SELECT AVG(test_exact) FROM results').fetchone()[0]
    
    print('  النماذج المدربة: %d' % cnt)
    print('  أفضل دقة: %.2f%%' % (best*100))
    print('  متوسط الدقة: %.2f%%' % (avg*100))
    
    if cnt > 0:
        print('  أفضل 5 نماذج:')
        for r in conn.execute('SELECT iteration, test_exact, n_estimators, max_depth, lr, train_time FROM results ORDER BY test_exact DESC LIMIT 5').fetchall():
            print('    #%d: %.2f%% ne=%d d=%d lr=%.3f (%ds)' % (r[0], r[1]*100, r[2], r[3], r[4], r[5]))
    conn.close()
else:
    print('  ❌ قاعدة البيانات غير موجودة')

# 2. Auto-ensemble
print()
print('[2] Auto-Ensemble:')
if os.path.exists('auto_ensemble_log.txt'):
    with open('auto_ensemble_log.txt', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for l in lines[-3:]:
        print('  %s' % l.strip())
else:
    print('  لا يوجد سجل بعد')

if os.path.exists('models/auto_ensemble_best.json'):
    r = json.load(open('models/auto_ensemble_best.json'))
    print('  أفضل ensemble: %.2f%%' % (r['test_exact']*100))
else:
    print('  لا يوجد ensemble بعد')

# 3. Best model
print()
print('[3] أفضل نموذج شامل:')
if os.path.exists('models/ultimate_results.json'):
    r = json.load(open('models/ultimate_results.json'))
    print('  V3 Ensemble: %.2f%% exact, %.2f%% 1X2' % (r['test_exact']*100, r['test_1x2']*100))
    
    if os.path.exists('models/ultimate_v5_results.json'):
        v5 = json.load(open('models/ultimate_v5_results.json'))
        print('  V5 Ensemble: %.2f%% exact (136 features)' % (v5['test_exact']*100))

# 4. Processes
print()
print('[4] العمليات في الخلفية:')
try:
    r = subprocess.run(['wmic', 'process', 'where', "name='python.exe'", 'get', 'ProcessId,CommandLine'],
                       capture_output=True, text=True)
    for line in r.stdout.split('\n'):
        l = line.strip()
        if 'infinite_trainer' in l:
            pid = l.split()[0]
            print('  🔄 Infinite Trainer (PID %s) ✅' % pid if pid.isdigit() else '  🔄 Infinite Trainer ✅')
        elif 'auto_ensemble' in l:
            pid = l.split()[0]
            print('  🧩 Auto-Ensemble (PID %s) ✅' % pid if pid.isdigit() else '  🧩 Auto-Ensemble ✅')
        elif 'streamlit' in l:
            pid = l.split()[0]
            print('  🌐 Dashboard (PID %s) ✅' % pid if pid.isdigit() else '  🌐 Dashboard ✅')
        elif 'live_predictor' in l:
            pid = l.split()[0]
            print('  📡 Live Predictor (PID %s) ✅' % pid if pid.isdigit() else '  📡 Live Predictor ✅')
except:
    print('  (لا يمكن قراءة العمليات)')

# 5. Time running
print()
print('[5] وقت التشغيل:')
start_time = time.time() - 3600  # estimated start
if os.path.exists('training_results.db') and cnt > 0:
    duration = time.time() - start_time
    speed = cnt / (duration / 3600) if duration > 0 else 0
    print('  %d نموذج في %.1f ساعة = %.0f نموذج/ساعة' % (cnt, duration/3600, speed))
    print('  أفضل دقة: %.2f%%' % (best*100))
    
    # Estimate when to beat V3
    remaining = 48 - duration/3600
    if remaining > 0:
        estimated_models = int(speed * remaining)
        print('  متبقي: %.1f ساعة (~%d نموذج إضافي)' % (remaining, estimated_models))

print()
print('='*55)
print('   🚀 مستمرون!')
print('='*55)

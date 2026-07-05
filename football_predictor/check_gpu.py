"""Check GPU and test data loading"""
import torch
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

print(f'CUDA: {torch.cuda.is_available()}')
print(f'Device count: {torch.cuda.device_count()}')
if torch.cuda.is_available():
    print(f'Device: {torch.cuda.get_device_name(0)}')

from direct_predictor import _load_training_data, FEATURES
print(f'Features: {len(FEATURES)}')

t0 = time.time()
print('Loading training data...')
result = _load_training_data()
if result and len(result) >= 2:
    X, y = result[0], result[1]
    print(f'X shape: {X.shape}')
    print(f'y shape: {y.shape}')
    print(f'n samples: {len(X)}')
    print(f'Classes: {len(set(y))}')
else:
    print(f'No data or error')
    print(f'Result: {result}')

print(f'Time: {time.time()-t0:.1f}s')

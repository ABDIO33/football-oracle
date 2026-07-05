"""Check PyTorch CUDA availability"""
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'Device count: {torch.cuda.device_count()}')
    print(f'Device name: {torch.cuda.get_device_name(0)}')
    print(f'Memory: {torch.cuda.get_device_properties(0).total_mem / 1024**3:.1f} GB')
else:
    print('CUDA NOT available - CPU only')
    print('Checking why...')
    try:
        torch.cuda.is_available()
    except Exception as e:
        print(f'Error: {e}')
    import os
    print(f'CUDA_VISIBLE_DEVICES: {os.environ.get("CUDA_VISIBLE_DEVICES", "not set")}')

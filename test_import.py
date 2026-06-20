"""Test if joblib can be imported and used inside a function"""
def test_import():
    try:
        import joblib
        import os
        p = os.path.join('football_predictor', 'models', 'mlp_blend.pkl')
        data = joblib.load(p)
        print(f'Loaded OK: type={type(data)}, len={len(data)}')
        return True
    except Exception as e:
        print(f'Error: {e}')
        return False

result = test_import()
print(f'Result: {result}')

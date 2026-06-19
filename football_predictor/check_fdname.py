"""Check fd_name field for team mapping"""
import pandas as pd
t = pd.read_csv(r'C:\Users\zake.exe\Desktop\Score Exact 100\football_predictor\soccer_dataset\teams.csv')
has_fd = t[t['fd_name'].notna()]
print("Teams with fd_name:", len(has_fd), "/", len(t))
print()
print("Sample fd_name vs name:")
for _, r in has_fd.head(30).iterrows():
    print(f"  {r['name']:40s} -> {r['fd_name']}")

print()
print("Teams WITHOUT fd_name:")
for _, r in t[t['fd_name'].isna()].head(30).iterrows():
    print(f"  {r['name']}")

# Check Glicko ratings
print()
print("Glicko-2 ranges:")
mu_vals = t['rating_mu'].dropna()
sigma_vals = t['rating_sigma'].dropna()
print(f"  rating_mu: {mu_vals.min():.1f} to {mu_vals.max():.1f} (mean={mu_vals.mean():.1f})")
print(f"  rating_sigma: {sigma_vals.min():.2f} to {sigma_vals.max():.2f}")

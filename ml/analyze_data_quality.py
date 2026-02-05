"""
Analyze merged XAUUSD + XAGUSD data for AI order filter.
Run from project root: python ml/analyze_data_quality.py
Or from ml/: python analyze_data_quality.py
"""
import sys
from pathlib import Path

import pandas as pd

# Allow running from project root or ml/
ROOT = Path(__file__).resolve().parent
if (ROOT / "data" / "example.csv").exists():
    CSV = ROOT / "data" / "example.csv"
else:
    CSV = ROOT / "ml" / "data" / "example.csv"
if not CSV.exists():
    print("example.csv not found. Run merge_train_dataset first.")
    sys.exit(1)

FEATURES = [
    "rsi_at_break",
    "time_to_fill",
    "relative_volume",
    "atr_rel_excursion",
    "atr_breakout_wick",
    "atr_sl_dist",
    "atr_tp_dist",
]

def main():
    df = pd.read_csv(CSV)
    df = df[df["state"].isin(["TP_HIT", "SL_HIT"])].copy()
    df["win"] = (df["state"] == "TP_HIT").astype(int)

    print("=" * 50)
    print("DATA QUALITY: merged XAUUSD + XAGUSD")
    print("=" * 50)

    # 1. Counts and win rate per symbol
    print("\n--- COUNTS & WIN RATE BY SYMBOL ---")
    by_sym = df.groupby("symbol").agg(
        count=("win", "count"),
        wins=("win", "sum"),
        win_rate=("win", "mean"),
    ).round(4)
    print(by_sym)
    if by_sym["count"].std() > by_sym["count"].mean() * 0.5:
        print("  -> Imbalanced symbol counts can bias the model toward the larger symbol.")

    # 2. Feature distributions by symbol (different scale = mixing may hurt)
    print("\n--- FEATURE MEANS BY SYMBOL ---")
    for sym in sorted(df["symbol"].unique()):
        sub = df[df["symbol"] == sym][FEATURES]
        print(f"  {sym}: {sub.mean().round(3).to_dict()}")
    gold = df[df["symbol"] == "XAUUSD"][FEATURES].mean()
    silver = df[df["symbol"] == "XAGUSD"][FEATURES].mean()
    diff = (gold - silver).abs()
    if (diff > 2.0).any():  # only warn on meaningfully different scales (e.g. RSI 10+ pts)
        print("  -> Large differences between symbols: model may learn 'symbol' more than 'setup'.")

    # 3. Correlation with target per symbol (is signal consistent?)
    print("\n--- FEATURE–TARGET CORRELATION (per symbol) ---")
    for sym in sorted(df["symbol"].unique()):
        sub = df[df["symbol"] == sym]
        corr = sub[FEATURES + ["win"]].corr()["win"].drop("win").sort_values(key=abs, ascending=False)
        print(f"  {sym}: {corr.round(3).to_dict()}")
    print("  -> If correlations differ a lot by symbol, one unified model may be suboptimal.")

    # 4. Per-symbol AUC (quick XGB single fold)
    print("\n--- PER-SYMBOL AUC (single train/val split) ---")
    try:
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import roc_auc_score
        for sym in sorted(df["symbol"].unique()):
            sub = df[df["symbol"] == sym][FEATURES + ["win"]].dropna()
            if len(sub) < 100:
                print(f"  {sym}: too few samples ({len(sub)})")
                continue
            X = sub[FEATURES]
            y = sub["win"]
            Xt, Xv, yt, yv = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
            n_neg, n_pos = (yt == 0).sum(), (yt == 1).sum()
            clf = xgb.XGBClassifier(max_depth=3, n_estimators=80, scale_pos_weight=n_neg / max(n_pos, 1), random_state=42)
            clf.fit(Xt, yt)
            auc = roc_auc_score(yv, clf.predict_proba(Xv)[:, 1])
            print(f"  {sym}: AUC = {auc:.3f} (n={len(sub)})")
        print("  -> If one symbol has much higher AUC alone, consider training per-symbol or adding symbol as a feature.")
    except Exception as e:
        print("  (skipped:", e, ")")

    # 5. Interpretation
    print("\n--- INTERPRETATION ---")
    print("  • Max |correlation| < 0.1 and per-symbol AUC near 0.5 → weak signal in current features.")
    print("  • Improving AUC likely needs: better features (e.g. risk-reward ratio, regime), more data,")
    print("    or a different target (e.g. filter 'clear losers' vs rest) if TP/SL is noisy.")
    print("=" * 50)

if __name__ == "__main__":
    main()

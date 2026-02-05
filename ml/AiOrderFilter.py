import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import os
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.metrics import classification_report, roc_auc_score, f1_score

class AiOrderFilter:
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.model = None
        self.best_threshold = 0.5  # Tuned on validation; use in strategy if filtering by score
        self.features = [
            'rsi_at_break',
            'time_to_fill',
            'relative_volume',
            'atr_rel_excursion',
            'atr_breakout_wick',
            'atr_sl_dist',
            'atr_tp_dist',
        ]
        if model_path and os.path.exists(model_path):
            loaded = joblib.load(model_path)
            if isinstance(loaded, dict):
                self.model = loaded["model"]
                self.best_threshold = loaded.get("best_threshold", 0.5)
            else:
                self.model = loaded

    def _clean_data(self, df):
        # Keeps only valid trade outcomes
        df = df[df['state'].isin(['TP_HIT', 'SL_HIT'])].copy()
        df['target'] = (df['state'] == 'TP_HIT').astype(int)
        return df[self.features + ['target']].dropna()

    def train(self, csv_path, val_size=0.2, tune_threshold=True):
        raw_df = pd.read_csv(csv_path)
        df = self._clean_data(raw_df)

        X = df[self.features]
        y = df['target']

        # Class balance: upweight minority (Win) so model doesn't default to predicting Loss
        n_neg = (y == 0).sum()
        n_pos = (y == 1).sum()
        scale_pos_weight = n_neg / max(n_pos, 1)

        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=val_size, stratify=y, random_state=42
        )

        self.model = xgb.XGBClassifier(
            max_depth=3,
            learning_rate=0.05,
            n_estimators=200,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            objective='binary:logistic',
            random_state=42,
            eval_metric='auc',
            early_stopping_rounds=15,
        )

        # --- 1. Cross-validation on full data (with same scale_pos_weight) ---
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(
            xgb.XGBClassifier(
                max_depth=3, learning_rate=0.05, n_estimators=150,
                subsample=0.8, scale_pos_weight=scale_pos_weight,
                objective='binary:logistic', random_state=42,
            ),
            X, y, cv=skf, scoring='roc_auc'
        )
        print("\n" + "="*30)
        print("📊 CROSS-VALIDATION METRICS")
        print("="*30)
        print(f"Mean AUC-ROC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

        # --- 2. Fit with early stopping on validation set ---
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # --- 3. Validation metrics (unbiased view) ---
        y_val_proba = self.model.predict_proba(X_val)[:, 1]
        val_auc = roc_auc_score(y_val, y_val_proba)
        print(f"Validation AUC-ROC: {val_auc:.4f}")

        # --- 4. Threshold tuning: maximize F1 for Win class on validation ---
        if tune_threshold:
            best_f1, best_t = 0.0, 0.5
            for t in np.linspace(0.2, 0.8, 31):
                pred = (y_val_proba >= t).astype(int)
                f1 = f1_score(y_val, pred, pos_label=1, zero_division=0)
                if f1 > best_f1:
                    best_f1, best_t = f1, t
            self.best_threshold = best_t
            print(f"Best threshold (F1 Win): {self.best_threshold:.3f} (F1={best_f1:.3f})")

        y_val_pred = (y_val_proba >= self.best_threshold).astype(int)
        print("\n📝 CLASSIFICATION REPORT (Validation Set)")
        print(classification_report(y_val, y_val_pred, target_names=['Loss', 'Win']))

        # --- 5. Feature importance ---
        print("💡 FEATURE IMPORTANCE")
        importance = dict(zip(self.features, self.model.feature_importances_))
        for feat, val in sorted(importance.items(), key=lambda x: x[1], reverse=True):
            print(f" - {feat}: {val:.4f}")

        # --- 6. Save model + threshold ---
        if not self.model_path:
            self.model_path = os.path.splitext(csv_path)[0] + ".joblib"
        joblib.dump({"model": self.model, "best_threshold": self.best_threshold}, self.model_path)
        print(f"\n✅ Model saved to: {self.model_path}")
        print("="*30 + "\n")

    def predict(self, data_dict):
        if not self.model:
            raise Exception("Model not loaded. Train first or provide model_path.")
        input_df = pd.DataFrame([data_dict])[self.features]
        return self.model.predict_proba(input_df)[0][1]
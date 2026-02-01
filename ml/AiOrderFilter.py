import pandas as pd
import xgboost as xgb
import joblib
import os
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report

class AiOrderFilter:
    def __init__(self, model_path=None):
        self.model_path = model_path
        self.model = None
        self.features = [
            'rsi_at_break', 
            'time_to_fill', 
            'relative_volume', 
            'atr_rel_excursion', 
            'atr_breakout_wick',
            'atr_sl_dist',
            'atr_tp_dist'
        ]
        
        if model_path and os.path.exists(model_path):
            self.model = joblib.load(model_path)

    def _clean_data(self, df):
        # Keeps only valid trade outcomes
        df = df[df['state'].isin(['TP_HIT', 'SL_HIT'])].copy()
        df['target'] = (df['state'] == 'TP_HIT').astype(int)
        return df[self.features + ['target']].dropna()

    def train(self, csv_path):
        raw_df = pd.read_csv(csv_path)
        df = self._clean_data(raw_df)
        
        X = df[self.features]
        y = df['target']

        self.model = xgb.XGBClassifier(
            max_depth=3,
            learning_rate=0.05,
            n_estimators=100,
            subsample=0.8,
            objective='binary:logistic',
            random_state=42
        )

        # --- 1. Cross Validation ---
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(self.model, X, y, cv=skf, scoring='roc_auc')
        
        print("\n" + "="*30)
        print("📊 CROSS-VALIDATION METRICS")
        print("="*30)
        print(f"Mean AUC-ROC: {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")

        # --- 2. Full Fit ---
        self.model.fit(X, y)
        
        # --- 3. Classification Report ---
        # This shows you Precision and Recall for your specific dataset
        y_pred = self.model.predict(X)
        print("\n📝 CLASSIFICATION REPORT (Training Set)")
        print(classification_report(y, y_pred, target_names=['Loss', 'Win']))

        # --- 4. Feature Importance ---
        # This tells you which indicator is actually working
        print("💡 FEATURE IMPORTANCE")
        importance = dict(zip(self.features, self.model.feature_importances_))
        for feat, val in sorted(importance.items(), key=lambda x: x[1], reverse=True):
            print(f" - {feat}: {val:.4f}")

        # --- 5. Save ---
        if not self.model_path:
            self.model_path = os.path.splitext(csv_path)[0] + ".joblib"
        joblib.dump(self.model, self.model_path)
        print(f"\n✅ Model saved to: {self.model_path}")
        print("="*30 + "\n")

    def predict(self, data_dict):
        if not self.model:
            raise Exception("Model not loaded. Train first or provide model_path.")
        input_df = pd.DataFrame([data_dict])[self.features]
        return self.model.predict_proba(input_df)[0][1]
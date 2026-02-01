# System Design: AI Trade Filter for "Break & Retest" Bot
**Strategy:** H1 Timeframe - Limit Order Execution  
**Objective:** Use XGBoost to filter out low-probability "overextended" or "stale" retests.

---

## 1. Architecture Overview
The system splits trading into two distinct layers:
1.  **The Algorithmic Bot:** Identifies price breaks and places Limit Orders at the retest level.
2.  **The AI Filter (Gatekeeper):** Analyzes the context of the break to decide if the order should stay active or be cancelled.

---

## 2. CSV Variable Definitions (data/forex/example.csv)
These variables allow the AI to judge "Quality" regardless of which currency pair you are trading.

| Variable | Logic | Significance |
| :--- | :--- | :--- |
| **atr_rel_excursion** | (Max Run - Level) / ATR | Measures if the breakout is "fresh" or "overextended." |
| **time_to_fill** | Candles between Break and Fill | Detects "stale" orders that are likely trend reversals. |
| **rsi** | RSI(14) at Break | Checks for exhaustion in the direction of the move. |
| **vol_ratio** | Vol / Vol_MA(20) | Confirms institutional conviction behind the break. |
| **wick_ratio** | Wick Size / ATR | Measures price rejection strength at the level. |
| **hour_sin / cos** | Trig Encoding | Helps AI understand session-specific win rates. |

---

## 3. The "Kill Switch" Logic
The bot doesn't just "set and forget." It uses the AI probability to manage the Limit Order:
* **High Confidence (>70%):** Leave order active.
* **Low Confidence (<45%):** Cancel the Limit Order (The market context has shifted).

---

## 4. Required Project Structure
```text
/trading_project
├── bot_main.py          # Trading execution
├── ai_gatekeeper.py     # AI logic & XGBoost code
├── AI_Gatekeeper.md     # This documentation
└── /data
    └── /forex
        ├── example.csv  # Training data
        └── model.ubj    # Binary AI model
```



# 🤖 Breakout Strategy Optimization with XGBoost

## 1. Core Logic
The goal of this system is to act as a **High-Pass Filter**. The bot identifies a breakout, but the AI decides if the "quality" of that breakout is worth the risk.

## 2. Validated Feature Set (Scale-Agnostic)
To allow the model to learn from both Gold and Silver simultaneously, we use normalized ratios:
- **rsi_at_break**: Momentum at the moment of entry.
- **time_to_fill**: Speed of the retest (Momentum vs. Stale price).
- **relative_volume**: (Current Volume / SMA 20). Identifies institutional conviction.
- **atr_rel_excursion**: How far price traveled before retesting (Exhaustion filter).
- **atr_breakout_wick**: Rejection at the break (Shaved candle = High Strength).

## 3. Current Performance Audit
- **Pipeline Health**: ✅ Excellent. Scripts correctly handle data cleaning and outcome filtering.
- **Sample Size**: ⚠️ Critical. 32 trades is insufficient for statistical significance.
- **Current AUC-ROC**: 0.28 (Indicates overfitting/noise).
- **Training Accuracy**: 94% (Confirms the model is memorizing, not learning yet).

## 4. Strategic Recommendations
1. **Merge Assets**: Immediately merge your Gold and Silver backtest CSVs. The model needs a "Metals" dataset of 100+ trades to begin seeing real patterns.
2. **The 0.70 Rule**: When deploying, do not take every "Win" prediction. Use `predict_proba` and only take trades where the AI confidence is > 70%.
3. **Session Filtering**: Add a "Trading Session" feature (Asian, London, NY) to help the AI understand that volume in London means more than volume in Asia.

## 5. Deployment Workflow
1. **Train**: `python3 train_model.py all_metals_data.csv`
2. **Validate**: Check that AUC-ROC moves closer to **0.60 - 0.70**.
3. **Predict**: Integrate the `.joblib` file into your live bot to filter entries in real-time.
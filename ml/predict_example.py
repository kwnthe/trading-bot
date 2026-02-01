from AiOrderFilter import AiOrderFilter
import numpy as np

# 1. Load the AI with the trained model
ai = AiOrderFilter(model_path="XAGUSD._H1_2025-11-26_13-10_2026-01-22_15-23.joblib")

# 2. Mock live data (What your bot sees at the moment of breakout)
live_trade_data = {
    'rsi_at_break': 58.5,
    'time_to_fill': 3,
    'relative_volume': 1.8,      # High volume
    'atr_rel_excursion': 1.1,    # Not exhausted
    'atr_breakout_wick': 0.05,   # Strong candle
    'atr_sl_dist': 0.95,         # Enough breathing room
    'atr_tp_dist': 1.85          # Reasonable target
}

# 3. Get AI Confidence
confidence = ai.predict(live_trade_data)

print(f"AI Win Probability: {confidence:.2%}")
if confidence > 0.65:
    print("Decision: ✅ TAKE TRADE")
else:
    print("Decision: ❌ SKIP TRADE")
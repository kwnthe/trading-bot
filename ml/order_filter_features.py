"""Build feature dict for AI order filter (metals.joblib) from strategy context."""


def build_order_filter_features(
    indicators,
    breakout_trend,
    entry_price,
    sl,
    tp,
    *,
    time_to_fill=0,
    atr_rel_excursion=0,
):
    """
    Build the 8-feature dict expected by AiOrderFilter.predict().

    indicators: dict with keys 'data', 'rsi', 'atr', 'volume_ma' (current bar [0])
    breakout_trend: Trend.UPTREND or Trend.DOWNTREND (or any with .name / comparison)
    entry_price, sl, tp: prices for atr_sl_dist / atr_tp_dist
    time_to_fill: candles to fill (0 at placement)
    atr_rel_excursion: 0 at placement, set later when filled
    """
    data = indicators["data"]
    atr_val = max(indicators["atr"][0], 1e-6) if len(indicators["atr"]) > 0 else 1e-6
    vol_ma = indicators["volume_ma"][0]
    is_uptrend = breakout_trend is not None and getattr(breakout_trend, "name", str(breakout_trend)) == "UPTREND"

    if is_uptrend:
        highest_excursion = data.high[0] - entry_price
        wick = data.high[0] - max(data.open[0], data.close[0])
    else:
        highest_excursion = entry_price - data.low[0]
        wick = min(data.open[0], data.close[0]) - data.low[0]

    return {
        "rsi_at_break": indicators["rsi"][0],
        "time_to_fill": time_to_fill,
        "relative_volume": data.volume[0] / vol_ma if vol_ma else 0,
        "atr_rel_excursion": atr_rel_excursion,
        "atr_breakout_wick": wick / atr_val,
        "atr_sl_dist": abs(sl - entry_price) / atr_val,
        "atr_tp_dist": abs(tp - entry_price) / atr_val,
    }

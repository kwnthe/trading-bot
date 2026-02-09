import logging
from typing import Optional, Iterable
import backtrader as bt
import numpy as np
import pandas as pd
from lightweight_charts import Chart

logger = logging.getLogger(__name__)

# ============================================================
# Utilities & Extraction
# ============================================================

def build_ohlc_df(data) -> pd.DataFrame:
    """Formats Backtrader data for Lightweight Charts."""
    df = pd.DataFrame({
        "time": [bt.num2date(d) for d in data.datetime.array],
        "open": data.open.array,
        "high": data.high.array,
        "low": data.low.array,
        "close": data.close.array,
        "volume": data.volume.array,
    })
    return df

def extract_strategy(cerebro, strategy=None):
    if strategy is not None: return strategy
    if hasattr(cerebro, "strategy"): return cerebro.strategy
    if hasattr(cerebro, "runstrats") and cerebro.runstrats: return cerebro.runstrats[0]
    if hasattr(cerebro, "results"): return cerebro.results[0]
    return None

def extract_ema(strategy, data_len: int):
    if strategy is None or not hasattr(strategy, "ema"): return False, None
    ema_line = strategy.ema.lines.ema
    try:
        ema = np.asarray(ema_line.array) if hasattr(ema_line, "array") else np.asarray(list(ema_line))
    except Exception:
        logger.exception("Failed to extract EMA")
        return False, None
    if len(ema) < data_len:
        ema = np.concatenate([np.full(data_len - len(ema), np.nan), ema])
    elif len(ema) > data_len:
        ema = ema[-data_len:]
    return True, ema

def _extract_orders_from_strategy(strategy, symbol: str) -> list[dict]:
    orders_to_plot: list[dict] = []
    if strategy is None or not hasattr(strategy, "get_completed_trades"):
        return orders_to_plot

    try:
        completed_trades = strategy.get_completed_trades()
        orders_to_plot.extend([
            trade for trade in completed_trades
            if trade.get("symbol") == symbol
            and trade.get("open_datetime")
            and trade.get("close_datetime")
        ])
    except Exception as e:
        logger.warning(f"Error extracting orders: {e}")
    return orders_to_plot

# ============================================================
# Zone Logic (The "Box" Fix)
# ============================================================

def add_lw_zones(chart, times, values, color, fill_color):
    """
    Groups contiguous price levels into boxes to avoid 
    connecting lines between different price zones.
    """
    if values is None or len(values) == 0:
        return

    start_idx = None
    
    for i in range(len(values)):
        val = values[i]
        
        # Detect start of a valid zone
        if not np.isnan(val) and start_idx is None:
            start_idx = i
        
        # Detect end of a zone (NaN, price change, or end of data)
        elif start_idx is not None:
            is_last = (i == len(values) - 1)
            price_changed = (values[i] != values[start_idx])
            
            if np.isnan(val) or price_changed or is_last:
                # Determine the end point
                end_idx = i if (is_last and not np.isnan(val) and not price_changed) else i - 1
                
                if end_idx >= start_idx:
                    chart.box(
                        start_time=times[start_idx],
                        start_value=values[start_idx],
                        end_time=times[end_idx],
                        end_value=values[start_idx], # Flat top/bottom creates a clean line-box
                        color=color,
                        fill_color=fill_color,
                        width=7
                    )
                
                # If we ended because of a price change, start the next zone immediately
                start_idx = i if (not np.isnan(val) and price_changed) else None

# ============================================================
# Main Rendering Function
# ============================================================

def render_tv_chart(
    cerebro,
    data,
    symbol: str,
    symbol_index: int = 0,
    strategy=None,
    orders: Optional[Iterable[dict]] = None,
):
    strategy = extract_strategy(cerebro, strategy)
    df = build_ohlc_df(data)

    # Initialize Chart
    chart = Chart(toolbox=True, width=1200, height=800, inner_width=1, inner_height=0.7)
    chart.legend(visible=True, font_size=12)
    chart.topbar.textbox('symbol', f"Bot Trading: {symbol}")

    # 1. Main Price
    chart.set(df)

    # 2. EMA (Standard Line)
    has_ema, ema_vals = extract_ema(strategy, len(df))
    if has_ema:
        ema_line = chart.create_line(name='EMA', color='#FF9800', width=2)
        ema_df = pd.DataFrame({"time": df["time"], "EMA": ema_vals}).dropna()
        if not ema_df.empty:
            ema_line.set(ema_df)

    # 3. ZONES (Support & Resistance as non-connected Boxes)
    if hasattr(cerebro, "data_indicators"):
        indicators = cerebro.data_indicators[symbol_index]
        breakout = indicators.get("breakout") if indicators else None
        
        if breakout is not None:
            # CONVERSION FIX: Convert numpy datetime64 to standard python datetime
            times = pd.to_datetime(df["time"]).tolist() 
            
            # Resistance (Red Boxes)
            res_vals = np.asarray(breakout.lines.resistance1.array)
            add_lw_zones(chart, times, res_vals, 
                         color="rgba(242, 54, 69, 0.8)", 
                         fill_color="rgba(242, 54, 69, 0.2)")
            
            # Support (Green Boxes)
            sup_vals = np.asarray(breakout.lines.support1.array)
            add_lw_zones(chart, times, sup_vals, 
                         color="rgba(8, 153, 129, 0.8)", 
                         fill_color="rgba(8, 153, 129, 0.2)")

    # 4. Markers & Risk/Reward Boxes
    if orders is None and strategy is not None:
        orders = _extract_orders_from_strategy(strategy, symbol)

    if orders:
        add_lw_markers(chart, orders)
        add_lw_order_boxes(chart, orders)

    chart.show(block=True)

# ============================================================
# Order Visualization Helpers
# ============================================================

def add_lw_order_boxes(chart, orders: Iterable[dict]):
    def _to_dt(v):
        if v is None: return None
        return v.to_pydatetime() if hasattr(v, "to_pydatetime") else v

    for o in orders:
        open_dt = _to_dt(o.get("open_datetime") or o.get("placed_datetime"))
        close_dt = _to_dt(o.get("close_datetime"))
        if not open_dt or not close_dt or close_dt == open_dt:
            continue

        entry = o.get("entry_executed_price") or o.get("entry_price")
        sl, tp = o.get("stop_loss") or o.get("sl"), o.get("take_profit") or o.get("tp")
        
        if None in (entry, sl, tp): continue
        entry_f, sl_f, tp_f = float(entry), float(sl), float(tp)

        # SL box
        chart.box(start_time=open_dt, start_value=min(sl_f, entry_f),
                  end_time=close_dt, end_value=max(sl_f, entry_f),
                  color="rgba(242,54,69,0.35)", fill_color="rgba(242,54,69,0.15)")

        # TP box
        chart.box(start_time=open_dt, start_value=min(entry_f, tp_f),
                  end_time=close_dt, end_value=max(entry_f, tp_f),
                  color="rgba(8,153,129,0.35)", fill_color="rgba(8,153,129,0.15)")

def add_lw_markers(chart, orders):
    def _to_dt(v):
        if v is None: return None
        return v.to_pydatetime() if hasattr(v, "to_pydatetime") else v

    markers = []
    # for o in orders:
    #     dt = _to_dt(o.get("open_datetime") or o.get("placed_datetime"))
    #     if not dt: continue
        
    #     # Entry Marker
    #     is_buy = "SELL" not in str(o.get("side", "BUY")).upper()
    #     markers.append({
    #         "time": dt,
    #         "position": "below" if is_buy else "above",
    #         "color": "#2196F3" if is_buy else "#F23645",
    #         "shape": "arrow_up" if is_buy else "arrow_down",
    #         "text": "Entry"
    #     })

    if markers:
        markers.sort(key=lambda x: pd.Timestamp(x["time"]))
        chart.marker_list(markers)

if __name__ == "__main__":
    # render_tv_chart(cerebro, data, "BTC/USDT")
    pass
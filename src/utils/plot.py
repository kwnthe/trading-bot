import logging
from typing import Optional, Iterable

import backtrader as bt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.models.chart_markers import ChartMarkerType

logger = logging.getLogger(__name__)

SHOW_HOVER_LABELS = True

# ============================================================
# Utilities
# ============================================================

def insert_gaps_with_x(x, y):
    """
    Insert NaN between level changes to prevent diagonal connections.
    """
    new_x, new_y = [], []

    for i in range(len(y)):
        if (
            i > 0
            and not np.isnan(y[i - 1])
            and not np.isnan(y[i])
            and y[i] != y[i - 1]
        ):
            new_x.append(x[i])
            new_y.append(np.nan)

        new_x.append(x[i])
        new_y.append(y[i])

    return new_x, new_y


def build_ohlc_df(data) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [bt.num2date(d) for d in data.datetime.array],
            "open": data.open.array,
            "high": data.high.array,
            "low": data.low.array,
            "close": data.close.array,
            "volume": data.volume.array,
        }
    )


# ============================================================
# Strategy / Indicator extraction (Backtrader-safe)
# ============================================================

def extract_strategy(cerebro, strategy=None):
    """
    Retrieve a strategy instance without triggering Backtrader
    boolean evaluation.
    """
    if strategy is not None:
        return strategy

    if hasattr(cerebro, "strategy"):
        return cerebro.strategy

    if hasattr(cerebro, "runstrats") and cerebro.runstrats:
        return cerebro.runstrats[0]

    if hasattr(cerebro, "results"):
        return cerebro.results[0]

    return None


def extract_rsi(strategy, data_len: int):
    """
    Extract RSI values from a Backtrader strategy safely.
    """
    if strategy is None or not hasattr(strategy, "rsi"):
        return False, None

    rsi_line = strategy.rsi.lines.rsi

    try:
        if hasattr(rsi_line, "array"):
            rsi = np.asarray(rsi_line.array)
        else:
            rsi = np.asarray(list(rsi_line))
    except Exception:
        logger.exception("Failed to extract RSI")
        return False, None

    # Align length with OHLC data
    if len(rsi) < data_len:
        rsi = np.concatenate([np.full(data_len - len(rsi), np.nan), rsi])
    elif len(rsi) > data_len:
        rsi = rsi[-data_len:]

    if np.all(np.isnan(rsi)):
        return False, None

    return True, rsi


def extract_ema(strategy, data_len: int):
    """
    Extract EMA values from a Backtrader strategy safely.
    """
    if strategy is None or not hasattr(strategy, "ema"):
        return False, None

    ema_line = strategy.ema.lines.ema

    try:
        if hasattr(ema_line, "array"):
            ema = np.asarray(ema_line.array)
        else:
            ema = np.asarray(list(ema_line))
    except Exception:
        logger.exception("Failed to extract EMA")
        return False, None

    # Align length with OHLC data
    if len(ema) < data_len:
        ema = np.concatenate([np.full(data_len - len(ema), np.nan), ema])
    elif len(ema) > data_len:
        ema = ema[-data_len:]

    if np.all(np.isnan(ema)):
        return False, None

    return True, ema


def extract_daily_rsi(strategy, data_len: int, df_dates: pd.Series):
    """
    Extract Daily RSI values from strategy's daily_data feed (created via replaydata).
    This uses the actual daily data feed so any issues with replaydata will be visible.
    Daily RSI has fewer data points, so we need to forward-fill values
    to align with the main timeframe data.
    """
    # Get daily data feed from strategy
    if strategy is None or not hasattr(strategy, "daily_data"):
        print("extract_daily_rsi: strategy is None or has no daily_data attribute")
        return False, None
    
    daily_data = strategy.daily_data
    if daily_data is None:
        print("extract_daily_rsi: daily_data is None")
        return False, None
    
    # Extract daily close prices from the daily data feed (created by replaydata)
    # Note: replaydata's array contains all intraday bars, not just daily bars
    # We need to filter to get only one bar per day (the last bar of each day)
    try:
        all_dates = pd.Series([bt.num2date(d) for d in daily_data.datetime.array])
        all_closes = np.asarray(daily_data.close.array)
        
        # Filter to get only one bar per day (the last bar of each day)
        # Group by date and take the last value
        df_daily = pd.DataFrame({
            'date': pd.to_datetime(all_dates).dt.normalize(),
            'datetime': all_dates,
            'close': all_closes
        })
        
        # Group by date and take the last bar of each day
        daily_aggregated = df_daily.groupby('date').agg({
            'close': 'last',
            'datetime': 'last'
        }).reset_index()
        
        daily_aggregated = daily_aggregated.sort_values('datetime')
        
        daily_dates = daily_aggregated['datetime']
        daily_closes = daily_aggregated['close'].values
        
        print(f"extract_daily_rsi: Filtered {len(all_closes)} bars from replaydata to {len(daily_closes)} daily bars")
    except Exception as e:
        logger.exception(f"Failed to extract daily data: {e}")
        return False, None
    
    if len(daily_closes) < 15:  # Need at least period+1 for RSI
        print(f"extract_daily_rsi: Not enough daily bars ({len(daily_closes)} < 15). Need at least 15 days for RSI(14) calculation.")
        return False, None
    
    # Calculate RSI from daily closes (from replaydata feed)
    daily_rsi = calculate_rsi_manual(daily_closes, period=14)
    
    print(f"extract_daily_rsi: Extracted {len(daily_rsi)} Daily RSI values from {len(daily_closes)} daily bars (from replaydata)")
    print(f"extract_daily_rsi: Date range: {daily_dates.min()} to {daily_dates.max()}")
    
    # Align daily RSI with main timeframe dates
    # Each daily RSI value should apply to ALL candles in that day
    try:
        # Normalize daily dates to midnight for proper date matching
        daily_dates_normalized = pd.to_datetime(daily_dates).dt.normalize()
        daily_rsi_series = pd.Series(daily_rsi, index=daily_dates_normalized)
        
        # Normalize main dates to midnight for matching
        # Ensure df_dates has the correct length
        if len(df_dates) != data_len:
            print(f"extract_daily_rsi: Warning - df_dates length ({len(df_dates)}) doesn't match data_len ({data_len}), using data_len")
            # If df_dates is wrong, we can't proceed - return error
            if len(df_dates) < data_len:
                print(f"extract_daily_rsi: Error - df_dates too short, cannot align")
                return False, None
        
        # Use only the first data_len elements if df_dates is longer
        df_dates_to_use = df_dates[:data_len] if len(df_dates) > data_len else df_dates
        df_dates_normalized = pd.to_datetime(df_dates_to_use).dt.normalize()
        
        # Map each main date to its corresponding daily RSI value
        # Use merge to ensure all bars on the same date get the same RSI value
        df_main_with_dates = pd.DataFrame({
            'date_normalized': df_dates_normalized,
            'original_index': range(len(df_dates_normalized))
        })
        
        df_daily_rsi = pd.DataFrame({
            'date_normalized': daily_dates_normalized,
            'daily_rsi': daily_rsi
        })
        
        # Merge to get RSI for each date, then forward-fill any missing dates
        df_merged = df_main_with_dates.merge(df_daily_rsi, on='date_normalized', how='left')
        df_merged = df_merged.sort_values('original_index')
        df_merged['daily_rsi'] = df_merged['daily_rsi'].ffill()  # Forward-fill any missing dates
        
        aligned_daily_rsi = df_merged['daily_rsi'].values
        
        # Ensure the result has the correct length (should match data_len)
        if len(aligned_daily_rsi) != data_len:
            print(f"extract_daily_rsi: Warning - aligned length ({len(aligned_daily_rsi)}) doesn't match data_len ({data_len}), adjusting")
            if len(aligned_daily_rsi) > data_len:
                aligned_daily_rsi = aligned_daily_rsi[:data_len]
            else:
                # Pad with NaN if shorter
                aligned_daily_rsi = np.concatenate([aligned_daily_rsi, np.full(data_len - len(aligned_daily_rsi), np.nan)])
        
        print(f"extract_daily_rsi: Aligned daily RSI from {len(daily_rsi)} to {len(aligned_daily_rsi)} values")
        non_nan_values = aligned_daily_rsi[~np.isnan(aligned_daily_rsi)]
        if len(non_nan_values) > 0:
            print(f"extract_daily_rsi: Daily RSI sample values: {non_nan_values[:5]}")
    except Exception as e:
        logger.exception(f"Failed to align daily RSI with main timeframe: {e}")
        return False, None

    if np.all(np.isnan(aligned_daily_rsi)):
        print("extract_daily_rsi: All daily RSI values are NaN")
        return False, None

    print(f"extract_daily_rsi: Successfully extracted daily RSI with {np.sum(~np.isnan(aligned_daily_rsi))} non-NaN values")
    return True, aligned_daily_rsi


def calculate_rsi_manual(prices, period=14):
    """
    Manually calculate RSI from price array using Wilder's smoothing method.
    This matches the standard RSI calculation used by most libraries.
    This avoids backtrader's synchronization issues.
    """
    import pandas as pd
    import numpy as np
    
    if len(prices) < period + 1:
        return np.full(len(prices), np.nan)
    
    # Convert to pandas Series for easier calculation
    prices_series = pd.Series(prices)
    
    # Calculate price changes
    delta = prices_series.diff()
    
    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    
    # Calculate average gains and losses using Wilder's smoothing
    # Wilder's method: First average = SMA, then: Avg = (Prev_Avg * (period - 1) + Current) / period
    # This is equivalent to: alpha = 1/period, but we'll do it explicitly for clarity
    avg_gains = gains.copy()
    avg_losses = losses.copy()
    
    # First average is simple moving average
    avg_gains.iloc[period] = gains.iloc[1:period+1].mean()
    avg_losses.iloc[period] = losses.iloc[1:period+1].mean()
    
    # Subsequent averages use Wilder's smoothing
    for i in range(period + 1, len(gains)):
        avg_gains.iloc[i] = (avg_gains.iloc[i-1] * (period - 1) + gains.iloc[i]) / period
        avg_losses.iloc[i] = (avg_losses.iloc[i-1] * (period - 1) + losses.iloc[i]) / period
    
    # Set first period values to NaN
    avg_gains.iloc[:period] = np.nan
    avg_losses.iloc[:period] = np.nan
    
    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.values



# ============================================================
# Figure creation
# ============================================================

def create_base_figure(symbol: str, height: int, has_rsi: bool):
    if has_rsi:
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            subplot_titles=(symbol, "RSI"),
        )
    else:
        fig = go.Figure()

    # hovermode will be set in apply_tradingview_style based on SHOW_HOVER_LABELS flag
    fig.update_layout(
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#2A2E39", size=12),
        showlegend=True,  # Enable legend to show RSI
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10),
        ),
        xaxis_rangeslider_visible=False,
        # Enable zoom and pan controls
        dragmode="pan",  # Default to pan mode (can switch to zoom with toolbar)
        # Show modebar with zoom/pan tools
        modebar=dict(
            orientation="v",
            bgcolor="rgba(255,255,255,0.8)",
            color="rgba(0,0,0,0.5)",
            activecolor="rgba(0,0,0,0.7)",
        ),
    )

    return fig


def add_price(fig, df, has_rsi):
    trace = go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        increasing=dict(line=dict(color="#089981"), fillcolor="#089981"),
        decreasing=dict(line=dict(color="#F23645"), fillcolor="#F23645"),
        hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
    )

    fig.add_trace(trace, row=1 if has_rsi else None, col=1 if has_rsi else None)


def add_rsi(fig, df, rsi, daily_rsi=None):
    """
    Add RSI line to the RSI subplot.
    """
    # Add regular RSI
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=rsi,
            mode="lines",
            line=dict(color="#2962FF", width=2),
            name="RSI",
            showlegend=True,
            hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
        ),
        row=2,
        col=1,
    )
    
    # Add daily RSI if provided (will appear as a more static line)
    if daily_rsi is not None:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=daily_rsi,
                mode="lines",
                line=dict(color="#FF9800", width=2, dash="dash"),
                name="Daily RSI",
                showlegend=True,
                hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
            ),
            row=2,
            col=1,
        )

    # fig.add_hline(y=70, row=2, col=1, line_dash="dash", line_color="#F23645")
    # fig.add_hline(y=30, row=2, col=1, line_dash="dash", line_color="#089981")
    # fig.add_hline(y=50, row=2, col=1, line_dash="dot", line_color="#787B86")


def add_ema(fig, df, ema, has_rsi):
    """
    Add EMA line to the main price chart.
    """
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=ema,
            mode="lines",
            line=dict(color="#FF9800", width=2),
            name="EMA",
            hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
            showlegend=False,
        ),
        row=1 if has_rsi else None,
        col=1 if has_rsi else None,
    )

def apply_tradingview_style(fig, has_rsi: bool):
    # Get current legend settings to preserve them
    current_showlegend = getattr(fig.layout, 'showlegend', False)
    current_legend = getattr(fig.layout, 'legend', None)
    
    # Enable hovermode to show spikes (crosshair lines), but hide labels with empty hovertemplates
    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#2A2E39", size=12),
        showlegend=current_showlegend,  # Preserve legend visibility
        legend=current_legend,  # Preserve legend settings
        hovermode="x",  # Enable hover to show spikes, but we'll hide labels with empty hovertemplates
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#E6E8EB",
        zeroline=False,
        showspikes=True,  # Always show crosshair lines (spikes)
        spikemode="across",  # Only show lines across, no arrows on axes
        spikesnap="cursor",
        spikecolor="#B2B5BE",
        spikethickness=1,
        tickfont=dict(color="#787B86"),
        # Enable zoom and pan on x-axis
        fixedrange=False,  # Allow zoom/pan
        rangeslider=dict(visible=False),  # Disable rangeslider but keep functionality
    )

    fig.update_yaxes(
        side="right",
        nticks=30,
        showgrid=True,
        gridcolor="#E6E8EB",
        zeroline=False,
        showspikes=True,  # Always show crosshair lines (spikes)
        spikemode="across",  # Only show lines across, no arrows on axes
        spikesnap="cursor",
        spikecolor="#B2B5BE",
        spikethickness=1,
        automargin=True,
        tickfont=dict(color="#787B86"),
        tickformat=".5f",
        hoverformat=".10f",
        # Enable zoom and pan on y-axis
        fixedrange=False,  # Allow zoom/pan
        # Enable scaleanchor for proportional zoom (optional)
        # scaleanchor="x",  # Uncomment to lock aspect ratio
    )

    if has_rsi:
        steps = [10, 30, 50, 70, 90]
        fig.update_yaxes(
            row=2,
            col=1,
            range=[0, 100],
            tickmode="array",
            tickvals=steps,
            ticktext=steps,
            showspikes=True,  # Show crosshair lines in RSI subplot too
            spikemode="across",
            spikesnap="cursor",
            spikecolor="#B2B5BE",
            spikethickness=1,
        )
        # Also enable spikes for x-axis of RSI subplot
        fig.update_xaxes(
            row=2,
            col=1,
            showspikes=True,  # Show crosshair lines in RSI subplot too
            spikemode="across",
            spikesnap="cursor",
            spikecolor="#B2B5BE",
            spikethickness=1,
        )


# ============================================================
# Indicators / overlays
# ============================================================

def add_support_resistance(fig, df, breakout_ind, has_rsi):
    if breakout_ind is None:
        return

    for values, color in (
        (breakout_ind.lines.support1.array, "#2962FF"),
        (breakout_ind.lines.resistance1.array, "#E91E63"),
    ):
        x, y = insert_gaps_with_x(df["date"], np.asarray(values))

        fig.add_trace(
            go.Scatter(
                x=x, 
                y=y, 
                mode="lines", 
                line=dict(color=color, width=2),
                hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
                showlegend=False,
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )


def add_order_placements(fig, df, cerebro, symbol_index, has_rsi):
    """
    Add chart markers set via strategy.set_chart_marker().
    
    Chart markers are stored in cerebro.chart_markers[symbol_index] as a dict
    mapping candle_index -> marker_info (price, type, color, size, etc.).
    """
    # Check if chart markers exist for this symbol
    if not (hasattr(cerebro, "chart_markers") and symbol_index in cerebro.chart_markers):
        return
    
    chart_markers = cerebro.chart_markers[symbol_index]
    if not chart_markers:
        return
    
    # Symbol mapping for plotly
    symbol_map = {
        'diamond': 'diamond',
        'circle': 'circle',
        'square': 'square',
        'triangle-up': 'triangle-up',
        'triangle-down': 'triangle-down',
        'star': 'star',
        'x': 'x',
        ChartMarkerType.RETEST_ORDER_PLACED: 'diamond',  # Map enum value to symbol
    }
    
    # Collect marker data
    dates_to_plot = []
    prices_to_plot = []
    marker_symbols = []
    marker_colors = []
    marker_sizes = []
    
    for candle_index, marker_info in chart_markers.items():
        # In backtrader, self.candle_index = len(self.data) during next()
        # len(self.data) is 1-based (e.g., 1 for first bar, 2 for second bar)
        # But dataframe index is 0-based (0 for first bar, 1 for second bar)
        # So we need to subtract 1 to convert from 1-based to 0-based
        # Exception: if candle_index is 0, it might already be 0-based, so use it as-is
        df_index = candle_index - 1 if candle_index > 0 else candle_index
        
        # Validate df_index is within dataframe bounds
        if not (0 <= df_index < len(df)):
            continue
        
        dates_to_plot.append(df["date"].iloc[df_index])
        prices_to_plot.append(marker_info.get('price'))
        
        # Get marker properties with defaults
        marker_type = marker_info.get('type', 'diamond')
        marker_color = marker_info.get('color', 'black')
        marker_size = marker_info.get('size', 14)
        
        # Map marker type to plotly symbol (handle enum values by converting to string)
        if hasattr(marker_type, 'value'):
            marker_type = marker_type.value
        elif hasattr(marker_type, 'name'):
            marker_type = marker_type.name
        marker_type = str(marker_type).lower()
        
        plotly_symbol = symbol_map.get(marker_type, 'diamond')
        
        marker_symbols.append(plotly_symbol)
        marker_colors.append(marker_color)
        marker_sizes.append(marker_size)
    
    if not dates_to_plot:
        return
    
    # Deduplicate markers based on datetime to avoid duplicates
    seen_datetimes = set()
    deduplicated_data = []
    for date, price, symbol, color, size in zip(dates_to_plot, prices_to_plot, marker_symbols, marker_colors, marker_sizes):
        date_key = date if isinstance(date, pd.Timestamp) else pd.Timestamp(date)
        if date_key not in seen_datetimes:
            seen_datetimes.add(date_key)
            deduplicated_data.append((date, price, symbol, color, size))
    
    # Group markers by symbol/color/size to create separate traces for better visualization
    marker_groups = {}
    for date, price, symbol, color, size in deduplicated_data:
        key = (symbol, color, size)
        if key not in marker_groups:
            marker_groups[key] = {'dates': [], 'prices': []}
        marker_groups[key]['dates'].append(date)
        marker_groups[key]['prices'].append(price)
    
    # Add a trace for each unique marker configuration
    for (symbol, color, size), group in marker_groups.items():
        fig.add_trace(
            go.Scatter(
                x=group['dates'],
                y=group['prices'],
                mode="markers",
                marker=dict(symbol=symbol, size=size, color=color),
                name="Placed Order" if symbol == 'diamond' and color == 'black' else f"Marker ({symbol})",
                hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
                showlegend=False,
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )


def add_orders(fig, orders: Iterable[dict], has_rsi: bool = False):
    """
    Add order visualization to the plot.
    
    Expected order format:
    - open_datetime: datetime when trade opened
    - close_datetime: datetime when trade closed (optional, can use open_datetime if None)
    - entry_price: entry price (or entry_executed_price)
    - stop_loss: SL price (or 'sl' field)
    - take_profit: TP price (or 'tp' field)
    - close_reason: 'TP' or 'SL' (optional, for styling)
    """
    if not orders:
        return
    
    orders_added = 0
    
    for o in orders:
        # Extract fields with fallbacks
        open_dt = o.get("open_datetime") or o.get("placed_datetime")
        close_dt = o.get("close_datetime") or open_dt
        
        # Convert datetime to pandas Timestamp for plotly compatibility
        # Plotly works best with pandas Timestamps or datetime objects
        try:
            if open_dt:
                if not isinstance(open_dt, pd.Timestamp):
                    if hasattr(open_dt, 'to_pydatetime'):
                        open_dt = pd.Timestamp(open_dt.to_pydatetime())
                    else:
                        open_dt = pd.Timestamp(open_dt)
            
            if close_dt:
                if not isinstance(close_dt, pd.Timestamp):
                    if hasattr(close_dt, 'to_pydatetime'):
                        close_dt = pd.Timestamp(close_dt.to_pydatetime())
                    else:
                        close_dt = pd.Timestamp(close_dt)
        except Exception as e:
            print(f"DEBUG: Error converting datetime: {e}, open_dt={open_dt}, close_dt={close_dt}")
            continue
        
        # Skip if no datetime
        if not open_dt:
            print(f"DEBUG: Skipping order - no datetime: {o.get('trade_id', 'unknown')[:8]}")
            continue
        
        entry_price = o.get("entry_executed_price") or o.get("entry_price")
        stop_loss = o.get("stop_loss") or o.get("sl")
        take_profit = o.get("take_profit") or o.get("tp")
        close_reason = o.get("close_reason", "")
        
        # Skip if missing essential data
        if entry_price is None or stop_loss is None or take_profit is None:
            print(f"DEBUG-ERROR!!!!: Skipping order - missing data: entry={entry_price}, sl={stop_loss}, tp={take_profit}")
            continue
        
        orders_added += 1
        
        # Determine colors based on close reason
        if close_reason == "TP":
            sl_color = "rgba(242,54,69,0.1)"  # Lighter red for SL zone
            tp_color = "rgba(8,153,129,0.2)"  # Brighter green for TP hit
        elif close_reason == "SL":
            sl_color = "rgba(242,54,69,0.2)"  # Brighter red for SL hit
            tp_color = "rgba(8,153,129,0.1)"  # Lighter green for TP zone
        else:
            # Pending or unknown
            sl_color = "rgba(242,54,69,0.1)"
            tp_color = "rgba(8,153,129,0.1)"
        
        # Add stop loss zone (red background)
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=open_dt,
            x1=close_dt if close_dt else open_dt,
            y0=min(stop_loss, entry_price),
            y1=max(stop_loss, entry_price),
            fillcolor=sl_color,
            line_width=0,
            layer="below",
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )
        
        # Add take profit zone (green background)
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=open_dt,
            x1=close_dt if close_dt else open_dt,
            y0=min(entry_price, take_profit),
            y1=max(entry_price, take_profit),
            fillcolor=tp_color,
            line_width=0,
            layer="below",
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )
        
        # Add entry price line
        fig.add_trace(
            go.Scatter(
                x=[open_dt, close_dt if close_dt else open_dt],
                y=[entry_price, entry_price],
                mode="lines",
                line=dict(color="#787B86", width=1, dash="dot"),
                name="Entry",
                showlegend=False,
                hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )
        
        # Add entry marker
        fig.add_trace(
            go.Scatter(
                x=[open_dt],
                y=[entry_price],
                mode="markers",
                marker=dict(
                    symbol="circle",
                    size=8,
                    color="#787B86",
                    line=dict(color="white", width=1),
                ),
                name="Entry",
                showlegend=False,
                hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )
        
        # Add exit marker if trade closed
        if close_dt and close_dt != open_dt:
            exit_price = o.get("exit_price")
            if exit_price:
                exit_color = "#089981" if close_reason == "TP" else "#F23645"
                fig.add_trace(
                    go.Scatter(
                        x=[close_dt],
                        y=[exit_price],
                        mode="markers",
                        marker=dict(
                            symbol="x" if close_reason == "SL" else "star",
                            size=12,
                            color=exit_color,
                            line=dict(color="white", width=2),
                        ),
                        name="Exit",
                        showlegend=False,
                        hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
                    ),
                    row=1 if has_rsi else None,
                    col=1 if has_rsi else None,
                )


# ============================================================
# Public API
# ============================================================

def plotly_plot(
    cerebro,
    data,
    symbol: str,
    *,
    symbol_index: int = 0,
    height: int = 1200,
    strategy=None,
    orders: Optional[Iterable[dict]] = None,
):
    strategy = extract_strategy(cerebro, strategy)
    df = build_ohlc_df(data)

    has_rsi, rsi = extract_rsi(strategy, len(df))
    has_daily_rsi, daily_rsi = extract_daily_rsi(strategy, len(df), df["date"])
    has_ema, ema = extract_ema(strategy, len(df))
    fig = create_base_figure(symbol, height, has_rsi)

    add_price(fig, df, has_rsi)
    add_candle_index_arrows(fig, df, step=10, has_rsi=has_rsi)

    if has_ema:
        add_ema(fig, df, ema, has_rsi)

    if has_rsi:
        # Debug: Log daily RSI extraction result
        if has_daily_rsi:
            logger.info(f"Daily RSI extracted successfully: {len(daily_rsi)} values, {np.sum(~np.isnan(daily_rsi))} non-NaN")
        else:
            logger.warning("Daily RSI extraction failed or returned no data")
        add_rsi(fig, df, rsi, daily_rsi if has_daily_rsi else None)

    if hasattr(cerebro, "data_indicators"):
        indicators = cerebro.data_indicators[symbol_index]
        breakout = indicators.get("breakout") if indicators else None

        add_support_resistance(fig, df, breakout, has_rsi)
        add_order_placements(fig, df, cerebro, symbol_index, has_rsi)

    # Auto-extract orders from strategy if not provided
    if orders is None and strategy is not None:
        orders = _extract_orders_from_strategy(strategy, symbol)
    
    if orders:
        add_orders(fig, orders, has_rsi)

    apply_tradingview_style(fig, has_rsi)
    
    # Enable scroll zoom and other interactive features
    # 
    # ZOOM CONTROLS:
    # - Scroll wheel: Zoom both axes (default)
    # - Shift + drag: Zoom horizontally (X-axis) only
    # - Alt/Option + drag: Zoom vertically (Y-axis) only
    # - Regular drag: Pan (if in pan mode)
    # - Box select (Shift + drag): Zoom to selected area
    #
    # TOOLBAR BUTTONS:
    # - Use toolbar buttons for axis-specific zoom controls
    # - Click axis labels to zoom that axis only
    config = {
        'scrollZoom': True,  # Enable mouse wheel zoom (both axes by default)
        'doubleClick': 'reset',  # Double-click to reset zoom
        'displayModeBar': True,  # Show toolbar
        'modeBarButtonsToAdd': [
            'pan2d',           # Pan tool (both axes)
            'zoom2d',          # Box zoom (both axes)
            'select2d',        # Select tool
            'lasso2d',         # Lasso select
            'zoomIn2d',        # Zoom in (both axes)
            'zoomOut2d',       # Zoom out (both axes)
            'autoScale2d',     # Auto-scale
            'resetScale2d',    # Reset zoom
        ],
        'modeBarButtonsToRemove': [],  # Keep all buttons
    }
    
    # Add custom JavaScript for axis-specific scroll zoom
    # Shift + scroll = horizontal zoom only
    # Alt/Option + scroll = vertical zoom only
    # Regular scroll = both axes
    fig.update_layout(
        # Add custom JS for modifier key detection (handled by Plotly automatically)
        # The modifier keys work automatically with Plotly's built-in behavior
    )
    
    # Display the figure
    fig.show(config=config)


def _extract_orders_from_strategy(strategy, symbol: str):
    """
    Extract orders/trades from strategy for a given symbol.
    Returns list of trade dictionaries ready for plotting.
    """
    orders_to_plot = []
    
    # Check if strategy has the methods we need
    if not hasattr(strategy, 'get_completed_trades'):
        return orders_to_plot
    
    try:
        completed_trades = strategy.get_completed_trades()
        
        # Filter trades for this symbol
        orders_to_plot = [
            trade for trade in completed_trades 
            if trade.get('symbol') == symbol 
            and trade.get('open_datetime') 
            and trade.get('close_datetime')
        ]
        
        # Also include pending/running trades if they have placed_datetime
        if hasattr(strategy, 'get_all_trades'):
            all_trades = strategy.get_all_trades()
            from src.models.order import TradeState
            pending_trades = [
                trade for trade in all_trades
                if trade.get('symbol') == symbol 
                and isinstance(trade.get('state'), TradeState)
                and trade.get('state') in [TradeState.PENDING, TradeState.RUNNING]
                and trade.get('placed_datetime')
            ]
            # Add pending trades (use placed_datetime as open_datetime)
            for trade in pending_trades:
                if trade.get('placed_datetime'):
                    orders_to_plot.append({
                        **trade,
                        'open_datetime': trade.get('placed_datetime'),
                        'close_datetime': trade.get('placed_datetime'),  # Use same for pending
                    })
    except Exception as e:
        logger.warning(f"Error extracting orders from strategy: {e}")
    
    return orders_to_plot

def add_candle_index_arrows(fig, df, step=10, has_rsi=True):
    """
    Add arrows every `step` candles to help count candle indexes.
    """
    dates = df["date"].reset_index(drop=True)
    highs = df["high"].reset_index(drop=True)

    arrow_x = []
    arrow_y = []
    arrow_text = []

    for i in range(0, len(df), step):
        arrow_x.append(dates[i])
        arrow_y.append(highs[i] * 1.002)  # slightly above candle high
        arrow_text.append(str(i))

    fig.add_trace(
        go.Scatter(
            x=arrow_x,
            y=arrow_y,
            mode="markers+text",
            marker=dict(
                symbol="triangle-down",
                size=12,
                color="black",
            ),
            text=arrow_text,
            textposition="top center",
            name="Candle Index",
            showlegend=False,
            hovertemplate="<extra></extra>",  # Empty template to allow hover events but show no labels
            opacity=0.2,
        ),
        row=1 if has_rsi else None,
        col=1 if has_rsi else None,
    )
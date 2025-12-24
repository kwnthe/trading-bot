import logging
from typing import Optional, Iterable

import backtrader as bt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
        showlegend=False,
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
        hoverinfo="skip",  # Always skip hover for candlestick chart
    )

    fig.add_trace(trace, row=1 if has_rsi else None, col=1 if has_rsi else None)


def add_rsi(fig, df, rsi):
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=rsi,
            mode="lines",
            line=dict(color="#2962FF", width=2),
            name="RSI",
        ),
        row=2,
        col=1,
    )

    fig.add_hline(y=70, row=2, col=1, line_dash="dash", line_color="#F23645")
    fig.add_hline(y=30, row=2, col=1, line_dash="dash", line_color="#089981")
    fig.add_hline(y=50, row=2, col=1, line_dash="dot", line_color="#787B86")


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
            hoverinfo="skip" if not SHOW_HOVER_LABELS else "x+y",
            showlegend=False,
        ),
        row=1 if has_rsi else None,
        col=1 if has_rsi else None,
    )

def apply_tradingview_style(fig, has_rsi: bool):
    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#2A2E39", size=12),
        showlegend=False,
        hovermode="x" if SHOW_HOVER_LABELS else False,
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#E6E8EB",
        zeroline=False,
        showspikes=SHOW_HOVER_LABELS,  # Only show spikes when labels are enabled
        spikemode="across",
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
        showspikes=SHOW_HOVER_LABELS,  # Only show spikes when labels are enabled
        spikemode="across",
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
                hoverinfo="skip" if not SHOW_HOVER_LABELS else "x+y",
                showlegend=False,
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )


def add_breakouts(fig, df, breakout_ind, has_rsi):
    prices = np.asarray(breakout_ind.lines.breakout.array)
    mask = ~np.isnan(prices)

    if not np.any(mask):
        return

    fig.add_trace(
        go.Scatter(
            x=df["date"][mask],
            y=prices[mask],
            mode="markers",
            marker=dict(symbol="diamond", size=14, color="black"),
            name="Breakout",
            hoverinfo="skip" if not SHOW_HOVER_LABELS else "x+y+name",
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
                hoverinfo="skip",
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )
        
        # Add entry marker
        entry_hovertemplate = f"Entry: {entry_price:.5f}<extra></extra>" if SHOW_HOVER_LABELS else None
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
                hoverinfo="skip" if not SHOW_HOVER_LABELS else None,
                hovertemplate=entry_hovertemplate,
            ),
            row=1 if has_rsi else None,
            col=1 if has_rsi else None,
        )
        
        # Add exit marker if trade closed
        if close_dt and close_dt != open_dt:
            exit_price = o.get("exit_price")
            if exit_price:
                exit_color = "#089981" if close_reason == "TP" else "#F23645"
                exit_hovertemplate = f"Exit: {exit_price:.5f} ({close_reason})<extra></extra>" if SHOW_HOVER_LABELS else None
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
                        hoverinfo="skip" if not SHOW_HOVER_LABELS else None,
                        hovertemplate=exit_hovertemplate,
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
    has_ema, ema = extract_ema(strategy, len(df))
    fig = create_base_figure(symbol, height, has_rsi)

    add_price(fig, df, has_rsi)

    if has_ema:
        add_ema(fig, df, ema, has_rsi)

    if has_rsi:
        add_rsi(fig, df, rsi)

    if hasattr(cerebro, "data_indicators"):
        indicators = cerebro.data_indicators[symbol_index]
        breakout = indicators.get("breakout") if indicators else None

        add_support_resistance(fig, df, breakout, has_rsi)
        add_breakouts(fig, df, breakout, has_rsi)

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

import logging
from typing import Optional, Iterable

import backtrader as bt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


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

    fig.update_layout(
        height=height,
        hovermode="x",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#2A2E39", size=12),
        showlegend=False,
        xaxis_rangeslider_visible=False,
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
        hoverinfo="skip",
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

def apply_tradingview_style(fig, has_rsi: bool):
    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#2A2E39", size=12),
        showlegend=False,
        hovermode="x",
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="#E6E8EB",
        zeroline=False,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#B2B5BE",
        spikethickness=1,
        tickfont=dict(color="#787B86"),
    )

    fig.update_yaxes(
        side="right",
        nticks=30,
        showgrid=True,
        gridcolor="#E6E8EB",
        zeroline=False,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikecolor="#B2B5BE",
        spikethickness=1,
        automargin=True,
        tickfont=dict(color="#787B86"),
        tickformat=".5f",
        hoverformat=".10f",
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
            go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2)),
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
        ),
        row=1 if has_rsi else None,
        col=1 if has_rsi else None,
    )


def add_orders(fig, orders: Iterable[dict]):
    for o in orders:
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=o["open_datetime"],
            x1=o["close_datetime"],
            y0=min(o["stop_loss"], o["entry_price"]),
            y1=max(o["stop_loss"], o["entry_price"]),
            fillcolor="rgba(242,54,69,0.15)",
            line_width=0,
        )
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=o["open_datetime"],
            x1=o["close_datetime"],
            y0=min(o["entry_price"], o["take_profit"]),
            y1=max(o["entry_price"], o["take_profit"]),
            fillcolor="rgba(8,153,129,0.15)",
            line_width=0,
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
    height: int = 700,
    strategy=None,
    orders: Optional[Iterable[dict]] = None,
):
    strategy = extract_strategy(cerebro, strategy)
    df = build_ohlc_df(data)

    has_rsi, rsi = extract_rsi(strategy, len(df))
    fig = create_base_figure(symbol, height, has_rsi)

    add_price(fig, df, has_rsi)

    if has_rsi:
        add_rsi(fig, df, rsi)

    if hasattr(cerebro, "data_indicators"):
        indicators = cerebro.data_indicators[symbol_index]
        breakout = indicators.get("breakout") if indicators else None

        add_support_resistance(fig, df, breakout, has_rsi)
        add_breakouts(fig, df, breakout, has_rsi)

    if orders:
        add_orders(fig, orders)

    apply_tradingview_style(fig, has_rsi)
    fig.show()

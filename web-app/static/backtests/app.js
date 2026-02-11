async function fetchJson(url) {
  const res = await fetch(url, { headers: { "Accept": "application/json" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function renderStats(statsEl, stats) {
  const rows = Object.entries(stats || {}).map(([k, v]) => {
    const vv = (typeof v === "number") ? (Number.isFinite(v) ? v : String(v)) : String(v);
    return `<div class="statRow"><span class="muted"><b>${k}:</b> ${vv}</span></div>`;
  });
  statsEl.innerHTML = `<h3>Stats</h3>${rows.join("")}`;
  statsEl.style.display = "block";
}

function createChart(container) {
  const crosshairNormal =
    (LightweightCharts && LightweightCharts.CrosshairMode && LightweightCharts.CrosshairMode.Normal !== undefined)
      ? LightweightCharts.CrosshairMode.Normal
      : 0; // fallback (Normal)
  const chart = LightweightCharts.createChart(container, {
    layout: { background: { color: "#0b1220" }, textColor: "#e5e7eb" },
    grid: { vertLines: { color: "rgba(255,255,255,0.06)" }, horzLines: { color: "rgba(255,255,255,0.06)" } },
    timeScale: { timeVisible: true, secondsVisible: false },
    rightPriceScale: { borderColor: "rgba(255,255,255,0.12)" },
    crosshair: {
      // Prevent snapping (“magnet”) to a series (e.g. EMA)
      mode: crosshairNormal,
    },
  });

  // lightweight-charts v5 removed addCandlestickSeries/addLineSeries in favor of addSeries(...)
  const candleOpts = {
    upColor: "#22c55e",
    downColor: "#ef4444",
    borderVisible: false,
    wickUpColor: "#22c55e",
    wickDownColor: "#ef4444",
  };

  const candles = (typeof chart.addCandlestickSeries === "function")
    ? chart.addCandlestickSeries(candleOpts)
    : chart.addSeries(LightweightCharts.CandlestickSeries, candleOpts);

  return { chart, candles, seriesMarkers: null, resizeObserver: null, mount: container };
}

function addLineSeriesCompat(chart, options) {
  if (typeof chart.addLineSeries === "function") return chart.addLineSeries(options);
  return chart.addSeries(LightweightCharts.LineSeries, options);
}

function clearChart(chartObj, container) {
  if (!chartObj) return;
  if (chartObj.resizeObserver) {
    try { chartObj.resizeObserver.disconnect(); } catch (e) {}
    chartObj.resizeObserver = null;
  }
  // lightweight-charts doesn't offer "remove all series" cleanly; recreate chart instead.
  // On some versions, chart.remove() doesn't fully clear DOM nodes; also clear the container.
  try {
    chartObj.chart.remove();
  } catch (e) {
    // ignore
  }
  if (container) container.replaceChildren();
}

function resizeChartToContainer(chartObj) {
  if (!chartObj || !chartObj.chart || !chartObj.mount) return;
  if (typeof chartObj.chart.resize !== "function") return;
  const rect = chartObj.mount.getBoundingClientRect();
  const w = Math.floor(rect.width);
  const h = Math.floor(rect.height);
  if (w > 0 && h > 0) chartObj.chart.resize(w, h);
}

function attachAutoResize(chartObj) {
  if (!chartObj || !chartObj.mount) return;
  if (typeof ResizeObserver !== "function") return;
  chartObj.resizeObserver = new ResizeObserver(() => resizeChartToContainer(chartObj));
  chartObj.resizeObserver.observe(chartObj.mount);
  resizeChartToContainer(chartObj);
}

function setMarkersCompat(chartObj, markers) {
  if (!chartObj || !chartObj.candles) return;
  const m = markers || [];

  // v4
  if (typeof chartObj.candles.setMarkers === "function") {
    chartObj.candles.setMarkers(m);
    return;
  }

  // v5+: markers are a separate primitive
  if (LightweightCharts && typeof LightweightCharts.createSeriesMarkers === "function") {
    if (!chartObj.seriesMarkers) {
      chartObj.seriesMarkers = LightweightCharts.createSeriesMarkers(chartObj.candles, m);
    } else if (typeof chartObj.seriesMarkers.setMarkers === "function") {
      chartObj.seriesMarkers.setMarkers(m);
    }
  }
}

function addZoneSegments(chart, segments, color) {
  (segments || []).forEach(seg => {
    const s = addLineSeriesCompat(chart, { color, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    s.setData([
      { time: seg.startTime, value: seg.value },
      { time: seg.endTime, value: seg.value },
    ]);
  });
}

function addBaselineSeriesCompat(chart, options) {
  if (typeof chart.addBaselineSeries === "function") return chart.addBaselineSeries(options);
  return chart.addSeries(LightweightCharts.BaselineSeries, options);
}

function colorsForCloseReason(closeReason) {
  // Mirrors src/utils/plot copy.py add_orders() styling
  if (closeReason === "TP") {
    return { sl: "rgba(242,54,69,0.1)", tp: "rgba(8,153,129,0.2)" };
  }
  if (closeReason === "SL") {
    return { sl: "rgba(242,54,69,0.2)", tp: "rgba(8,153,129,0.1)" };
  }
  return { sl: "rgba(242,54,69,0.1)", tp: "rgba(8,153,129,0.1)" };
}

function addOrderBoxes(chart, orderBoxes) {
  (orderBoxes || []).forEach((b) => {
    if (!b || !b.openTime || !b.closeTime) return;
    const entry = Number(b.entry);
    const sl = Number(b.sl);
    const tp = Number(b.tp);
    if (!Number.isFinite(entry) || !Number.isFinite(sl) || !Number.isFinite(tp)) return;

    const { sl: slColor, tp: tpColor } = colorsForCloseReason(String(b.closeReason || ""));

    // SL zone (red)
    const slSeries = addBaselineSeriesCompat(chart, {
      baseValue: { type: "price", price: entry },
      topFillColor1: slColor,
      topFillColor2: slColor,
      bottomFillColor1: slColor,
      bottomFillColor2: slColor,
      topLineColor: "rgba(0,0,0,0)",
      bottomLineColor: "rgba(0,0,0,0)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    slSeries.setData([
      { time: b.openTime, value: sl },
      { time: b.closeTime, value: sl },
    ]);

    // TP zone (green)
    const tpSeries = addBaselineSeriesCompat(chart, {
      baseValue: { type: "price", price: entry },
      topFillColor1: tpColor,
      topFillColor2: tpColor,
      bottomFillColor1: tpColor,
      bottomFillColor2: tpColor,
      topLineColor: "rgba(0,0,0,0)",
      bottomLineColor: "rgba(0,0,0,0)",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    tpSeries.setData([
      { time: b.openTime, value: tp },
      { time: b.closeTime, value: tp },
    ]);
  });
}

async function main() {
  const jobId = window.BACKTEST_JOB_ID;
  const statusEl = document.getElementById("status");
  const stdoutEl = document.getElementById("stdout");
  const stderrEl = document.getElementById("stderr");
  const chartEl = document.getElementById("chart");
  const chartPanelEl = document.getElementById("chartPanel");
  const fullscreenBtn = document.getElementById("fullscreenBtn");
  const statsEl = document.getElementById("stats");
  const symbolSelect = document.getElementById("symbolSelect");

  let chartObj = null;
  let renderedOnce = false;
  let lastResult = null;
  let currentSymbol = null;

  function setSymbolOptions(symbols, preferred) {
    symbolSelect.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join("");
    if (!symbols.length) return null;
    const next = (preferred && symbols.includes(preferred)) ? preferred : symbols[0];
    symbolSelect.value = next;
    return next;
  }

  async function renderSymbol(symbol) {
    if (!lastResult) return;
    const sym = (lastResult.symbols || {})[symbol];
    if (!sym) return;

    if (chartObj) clearChart(chartObj, chartEl);
    // Mount chart into a fresh child node to avoid any leftover canvases
    // from older lightweight-charts versions.
    const mount = document.createElement("div");
    mount.style.width = "100%";
    mount.style.height = "100%";
    chartEl.replaceChildren(mount);
    chartObj = createChart(mount);
    attachAutoResize(chartObj);

    chartObj.candles.setData(sym.candles || []);
    setMarkersCompat(chartObj, sym.markers || []);

    addOrderBoxes(chartObj.chart, sym.orderBoxes || []);

    if (sym.ema && sym.ema.length) {
      const ema = addLineSeriesCompat(chartObj.chart, { color: "#FF9800", lineWidth: 2 });
      ema.setData(sym.ema);
    }

    const zones = sym.zones || {};
    addZoneSegments(chartObj.chart, zones.resistanceSegments, "rgba(242, 54, 69, 0.9)");
    addZoneSegments(chartObj.chart, zones.supportSegments, "rgba(8, 153, 129, 0.9)");

    chartObj.chart.timeScale().fitContent();
    renderStats(statsEl, lastResult.stats);
  }

  async function renderResult(result) {
    lastResult = result;
    const symbols = Object.keys(result.symbols || {});
    if (!symbols.length) return;
    currentSymbol = setSymbolOptions(symbols, currentSymbol || symbolSelect.value);
    if (!currentSymbol) return;
    await renderSymbol(currentSymbol);
  }

  symbolSelect.addEventListener("change", () => {
    currentSymbol = symbolSelect.value;
    renderSymbol(currentSymbol);
  });

  async function tick() {
    const st = await fetchJson(`/api/jobs/${jobId}/status/`);
    statusEl.textContent = st.status || "unknown";
    stdoutEl.textContent = st.stdout_tail || "";
    stderrEl.textContent = st.stderr_tail || "";

    if (st.error) {
      statusEl.textContent = `${st.status} (${st.error})`;
    }

    if (st.has_result && !renderedOnce) {
      const result = await fetchJson(st.result_url);
      renderedOnce = true;
      await renderResult(result);
    }

    if (st.status === "running" || st.status === "queued") {
      setTimeout(tick, 1200);
    }
  }

  // Fullscreen handling
  function updateFullscreenButton() {
    if (!fullscreenBtn) return;
    setTimeout(() => resizeChartToContainer(chartObj), 50);
  }
  if (fullscreenBtn && chartPanelEl) {
    fullscreenBtn.addEventListener("click", () => {
      if (!document.fullscreenElement) {
        if (chartPanelEl.requestFullscreen) chartPanelEl.requestFullscreen();
      } else {
        if (document.exitFullscreen) document.exitFullscreen();
      }
    });
    document.addEventListener("fullscreenchange", updateFullscreenButton);
  }

  tick().catch(err => {
    statusEl.textContent = `error (${err})`;
  });
}

main();


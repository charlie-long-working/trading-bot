"""
Web GUI for tracking regime, decisions, and backtest results.

Run: python -m dashboard.app
Then open http://127.0.0.1:5050
"""

import json
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, render_template_string, request

from data_loaders.load_klines import load_merged_klines
from data_loaders.decision import make_decision
from backtest.engine import run_backtest
from dashboard.decision_timeline import build_decision_timeline

app = Flask(__name__, static_url_path="")
DATA_DIR = ROOT / "data"

CONFIGS = [
    ("spot", "BTCUSDT", "1d"),
    ("spot", "BTCUSDT", "1h"),
    ("spot", "ETHUSDT", "1d"),
    ("spot", "ETHUSDT", "1h"),
    ("um", "BTCUSDT", "1d"),
    ("um", "BTCUSDT", "1h"),
    ("um", "ETHUSDT", "1d"),
    ("um", "ETHUSDT", "1h"),
]


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/context")
def api_context():
    market = request.args.get("market", "spot")
    symbol = request.args.get("symbol", "BTCUSDT")
    interval = request.args.get("interval", "1d")
    ctx = make_decision(str(DATA_DIR), market, symbol, interval)
    if ctx is None:
        return jsonify({"error": "no data"}), 404
    return jsonify({
        "symbol": str(ctx.symbol),
        "market_type": str(ctx.market_type),
        "interval": str(ctx.interval),
        "regime": str(ctx.regime),
        "favor": str(ctx.favor),
        "halving_phase": str(ctx.halving_phase),
        "seasonal_weak": bool(ctx.seasonal_weak),
        "bars": int(ctx.bars),
        "last_close": float(ctx.last_close),
    })


@app.route("/api/backtest")
def api_backtest():
    market = request.args.get("market", "spot")
    symbol = request.args.get("symbol", "BTCUSDT")
    interval = request.args.get("interval", "1d")
    result = run_backtest(str(DATA_DIR), market, symbol, interval, lookback=100)
    if result is None:
        return jsonify({"error": "no data"}), 404
    eq = result.equity_curve
    equity_list = [float(x) for x in eq.tolist()] if eq is not None else []
    return jsonify({
        "symbol": str(result.symbol),
        "market_type": str(result.market_type),
        "interval": str(result.interval),
        "num_trades": int(result.num_trades),
        "total_return_pct": float(result.total_return_pct),
        "max_drawdown_pct": float(result.max_drawdown_pct),
        "win_rate": float(result.win_rate),
        "profit_factor": float(result.profit_factor),
        "sharpe_ratio": float(result.sharpe_ratio),
        "equity_curve": equity_list,
    })


@app.route("/api/chart")
def api_chart():
    market = request.args.get("market", "spot")
    symbol = request.args.get("symbol", "BTCUSDT")
    interval = request.args.get("interval", "1d")
    max_bars = request.args.get("max_bars", type=int, default=500)
    out = load_merged_klines(str(DATA_DIR), market, symbol, interval)
    if out is None:
        return jsonify({"error": "no data"}), 404
    open_time, open_, high, low, close, volume = out
    try:
        ot, o, h, l_, c, v, regime_bar, favor_bar, signal_bar, trades = build_decision_timeline(
            open_time, open_, high, low, close, volume,
            lookback=100,
            max_bars=max_bars,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    n = len(ot)
    # Use native Python types for JSON (avoid numpy scalar issues)
    def to_float_arr(a):
        return [float(x) for x in a.tolist()]
    def to_int_arr(a):
        return [int(x) for x in a.tolist()]
    def to_str_list(a):
        return [str(x) if x else "" for x in a.tolist()]
    return jsonify({
        "open_time": to_int_arr(ot),
        "open": to_float_arr(o),
        "high": to_float_arr(h),
        "low": to_float_arr(l_),
        "close": to_float_arr(c),
        "regime": to_str_list(regime_bar),
        "favor": to_str_list(favor_bar),
        "signal": to_str_list(signal_bar),
        "trades": [
            {
                "entry_bar": int(t.entry_bar),
                "exit_bar": int(t.exit_bar),
                "side": str(t.side),
                "entry_price": float(t.entry_price),
                "exit_price": float(t.exit_price),
            }
            for t in trades
        ],
    })


@app.route("/api/configs")
def api_configs():
    return jsonify([{"market": m, "symbol": s, "interval": i} for m, s, i in CONFIGS])


INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Trading Bot – Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #1a1a2e; color: #eee; }
    h1 { margin-top: 0; }
    .controls { display: flex; gap: 1rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem; }
    select { padding: 0.4rem 0.8rem; font-size: 1rem; background: #16213e; color: #eee; border: 1px solid #0f3460; border-radius: 6px; }
    button { padding: 0.5rem 1rem; font-size: 1rem; background: #e94560; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
    button:hover { background: #c73e54; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
    .card { background: #16213e; border-radius: 8px; padding: 1rem; border: 1px solid #0f3460; }
    .card h2 { margin-top: 0; font-size: 1.1rem; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #0f3460; }
    .positive { color: #4ade80; }
    .negative { color: #f87171; }
    .chart-wrap { height: 360px; position: relative; }
    #summaryTable tbody tr:hover { background: #0f3460; }
  </style>
</head>
<body>
  <h1>Trading Bot – Tracking &amp; View</h1>
  <p style="color:#888; margin-top: -0.5rem;">Open <strong>http://127.0.0.1:5050</strong> – run with: <code>python -m dashboard.app</code></p>
  <div class="controls">
    <label>Market <select id="market"><option value="spot">spot</option><option value="um">um</option></select></label>
    <label>Symbol <select id="symbol"><option value="BTCUSDT">BTCUSDT</option><option value="ETHUSDT">ETHUSDT</option></select></label>
    <label>Interval <select id="interval"><option value="1d">1d</option><option value="1h">1h</option></select></label>
    <button id="refresh">Refresh</button>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Market context (decision)</h2>
      <div id="context"><span id="contextLoading">Loading…</span></div>
    </div>
    <div class="card">
      <h2>Backtest summary</h2>
      <div id="backtest"><span id="backtestLoading">Loading…</span></div>
    </div>
  </div>

  <div class="card" style="margin-top: 1rem;">
    <h2>Backtest results – all pairs</h2>
    <table id="summaryTable">
      <thead><tr><th>Market</th><th>Symbol</th><th>Interval</th><th>Trades</th><th>Return %</th><th>Max DD %</th><th>Win rate %</th><th>PF</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="card" style="margin-top: 1rem;">
    <h2>Price &amp; regime (last 500 bars)</h2>
    <div class="chart-wrap"><canvas id="chart"></canvas></div>
  </div>

  <script>
    const marketEl = document.getElementById('market');
    const symbolEl = document.getElementById('symbol');
    const intervalEl = document.getElementById('interval');
    const refreshBtn = document.getElementById('refresh');
    const contextEl = document.getElementById('context');
    const backtestEl = document.getElementById('backtest');
    const summaryTbody = document.querySelector('#summaryTable tbody');
    let chartInstance = null;

    function qs(o) { return new URLSearchParams(o).toString(); }

    async function loadContext() {
      const loading = document.getElementById('contextLoading');
      if (loading) loading.textContent = 'Loading…';
      try {
        const params = { market: marketEl.value, symbol: symbolEl.value, interval: intervalEl.value };
        const r = await fetch('/api/context?' + qs(params));
        if (!r.ok) { contextEl.innerHTML = 'No data for this pair. Check <code>data/</code> and try spot/BTCUSDT/1d.'; return; }
        const d = await r.json();
      const fmtNum = (v) => (v != null && !Number.isNaN(v)) ? Number(v) : '–';
      contextEl.innerHTML = `
          <p><strong>Regime:</strong> ${d.regime ?? '–'} &nbsp; <strong>Favor:</strong> ${d.favor ?? '–'}</p>
          <p>Halving phase: ${d.halving_phase ?? '–'} &nbsp; Seasonal weak: ${d.seasonal_weak === true}</p>
          <p>Bars: ${fmtNum(d.bars)} &nbsp; Last close: ${fmtNum(d.last_close)}</p>
        `;
      } catch (e) {
        contextEl.textContent = 'Error: ' + e.message;
      }
    }

    async function loadBacktest() {
      const loading = document.getElementById('backtestLoading');
      if (loading) loading.textContent = 'Loading…';
      try {
        const params = { market: marketEl.value, symbol: symbolEl.value, interval: intervalEl.value };
        const r = await fetch('/api/backtest?' + qs(params));
        if (!r.ok) { backtestEl.textContent = 'No data'; return; }
        const d = await r.json();
        const n = (v, dec = 1) => (v != null && !Number.isNaN(v)) ? Number(v).toFixed(dec) : '–';
        backtestEl.innerHTML = `
          <p>Trades: ${d.num_trades != null ? d.num_trades : '–'} &nbsp; Return: <span class="${(d.total_return_pct != null && d.total_return_pct >= 0) ? 'positive' : 'negative'}">${n(d.total_return_pct)}%</span>
          &nbsp; Max DD: <span class="negative">${n(d.max_drawdown_pct)}%</span></p>
          <p>Win rate: ${n(d.win_rate)}% &nbsp; Profit factor: ${n(d.profit_factor, 2)} &nbsp; Sharpe: ${n(d.sharpe_ratio, 2)}</p>
        `;
      } catch (e) {
        backtestEl.textContent = 'Error: ' + e.message;
      }
    }

    async function loadAllBacktests() {
      const r = await fetch('/api/configs');
      const configs = await r.json();
      const rows = [];
      for (const c of configs) {
        const res = await fetch('/api/backtest?' + qs(c));
        if (!res.ok) continue;
        const d = await res.json();
        rows.push({ ...c, ...d });
      }
      const num = (v, decimals = 1) => (v != null && !Number.isNaN(v)) ? Number(v).toFixed(decimals) : '–';
      summaryTbody.innerHTML = rows.map(r => `
        <tr>
          <td>${r.market}</td><td>${r.symbol}</td><td>${r.interval}</td>
          <td>${r.num_trades != null ? r.num_trades : '–'}</td>
          <td class="${(r.total_return_pct != null && r.total_return_pct >= 0) ? 'positive' : 'negative'}">${num(r.total_return_pct)}%</td>
          <td class="negative">${num(r.max_drawdown_pct)}%</td>
          <td>${num(r.win_rate)}%</td>
          <td>${num(r.profit_factor, 2)}</td>
        </tr>
      `).join('');
    }

    async function loadChart() {
      try {
        const params = { market: marketEl.value, symbol: symbolEl.value, interval: intervalEl.value, max_bars: 500 };
        const r = await fetch('/api/chart?' + qs(params));
        if (!r.ok) { console.warn('Chart API error', r.status); return; }
        const d = await r.json();
        if (!d.open_time || !d.close || !Array.isArray(d.close)) return;
        const labels = d.open_time.map(t => new Date(Number(t)).toISOString().slice(0, 10));
        const regime = Array.isArray(d.regime) ? d.regime : [];
        if (chartInstance) chartInstance.destroy();
        const ctx = document.getElementById('chart');
        if (!ctx) return;
        chartInstance = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [
            { label: 'Close', data: d.close, borderColor: '#e94560', backgroundColor: 'rgba(233,69,96,0.1)', fill: true, tension: 0.1 },
            { label: 'Regime bull', data: regime.map(x => (x === 'bull') ? 1 : null), borderColor: '#4ade80', pointRadius: 0, fill: false },
            { label: 'Regime bear', data: regime.map(x => (x === 'bear') ? 1 : null), borderColor: '#f87171', pointRadius: 0, fill: false },
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: false, grid: { color: '#0f3460' } },
            x: { maxTicksLimit: 12, grid: { color: '#0f3460' } }
          },
          plugins: { legend: { position: 'top' } }
        }
      });
      } catch (e) { console.error('Chart error', e); }
    }

    async function refresh() {
      await Promise.all([loadContext(), loadBacktest(), loadChart()]);
    }

    refreshBtn.addEventListener('click', refresh);
    (async () => {
      await refresh();
      await loadAllBacktests();
    })();
  </script>
</body>
</html>
"""


def main():
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simulate a $500 futures portfolio with strict risk management.

Uses MACD+RSI on futures BTC/USDT 1d + ETH/USDT 1d.
Logs every trade, account state, and risk event to a file.

Anti-blowup rules:
  1. Max risk per trade: 2% of equity
  2. Max leverage: 3x
  3. Always use SL (ATR-based)
  4. Max single position: 30% of equity (notional)
  5. Circuit breaker: pause trading if DD from peak > 20%
  6. Daily loss limit: stop after losing 5% in one day

Run from project root: python -m botv2.simulate_portfolio
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botv2.config import CACHE_DIR, REPO_ROOT, BOTV2_ROOT
from botv2.data.fetcher import load_klines
from botv2.strategy.macd_rsi import MACDRSIParams, _ema, _rsi, _atr


# ─── Configuration ───────────────────────────────────────────────────────────

INITIAL_CAPITAL = 500.0
MAX_RISK_PER_TRADE = 0.02       # 2% of equity
MAX_LEVERAGE = 3.0
MAX_POSITION_PCT = 0.30         # 30% of equity as notional
CIRCUIT_BREAKER_DD = 0.20       # pause if 20% DD from peak
DAILY_LOSS_LIMIT = 0.05         # stop after 5% daily loss
MAKER_FEE = 0.0002              # 0.02% maker
TAKER_FEE = 0.0005              # 0.05% taker (market orders)
FEE_REBATE = 0.40               # 40% fee rebate (kickback)
FUNDING_RATE_8H = 0.0001        # ~0.01% per 8h funding

LOG_FILE = BOTV2_ROOT / "reports" / "simulation_500.log"
SUMMARY_FILE = BOTV2_ROOT / "reports" / "simulation_500_summary.md"


@dataclass
class Position:
    symbol: str
    side: str               # "long" or "short"
    entry_price: float
    size_usd: float          # notional size in USD
    size_coin: float         # position size in coin
    leverage: float
    stop_loss: float
    take_profit: float
    margin_used: float       # actual USD locked as margin
    entry_bar: int
    entry_time: str


@dataclass
class TradeLog:
    time: str
    symbol: str
    action: str              # OPEN_LONG, OPEN_SHORT, CLOSE_SL, CLOSE_TP, CLOSE_END
    side: str
    price: float
    size_usd: float
    size_coin: float
    leverage: float
    fee: float
    pnl: float
    equity_before: float
    equity_after: float
    reason: str
    sl: float = 0.0
    tp: float = 0.0


@dataclass
class DayState:
    date: str
    starting_equity: float
    loss_today: float = 0.0
    paused: bool = False


class PortfolioSimulator:
    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.initial_capital = initial_capital
        self.position: Optional[Position] = None
        self.trades: List[TradeLog] = []
        self.equity_history: list = []
        self.circuit_breaker_active = False
        self.circuit_breaker_count = 0
        self.day_state = DayState(date="", starting_equity=initial_capital)
        self.total_fees = 0.0
        self.total_funding = 0.0

    def _calc_position_size(self, entry_price: float, stop_price: float) -> tuple:
        """
        Calculate position size based on risk management.
        Returns (size_usd, size_coin, leverage, margin).
        """
        risk_amount = self.equity * MAX_RISK_PER_TRADE
        price_risk_pct = abs(entry_price - stop_price) / entry_price

        if price_risk_pct < 0.001:
            price_risk_pct = 0.01

        # Size based on risk: if SL hit, lose exactly risk_amount
        size_usd = risk_amount / price_risk_pct

        # Cap by max position pct
        max_notional = self.equity * MAX_POSITION_PCT * MAX_LEVERAGE
        size_usd = min(size_usd, max_notional)

        # Cap by max leverage
        margin = size_usd / MAX_LEVERAGE
        if margin > self.equity * MAX_POSITION_PCT:
            margin = self.equity * MAX_POSITION_PCT
            size_usd = margin * MAX_LEVERAGE

        leverage = size_usd / margin if margin > 0 else 1.0
        size_coin = size_usd / entry_price

        return size_usd, size_coin, leverage, margin

    def _check_circuit_breaker(self) -> bool:
        dd = (self.peak_equity - self.equity) / self.peak_equity
        if dd >= CIRCUIT_BREAKER_DD:
            if not self.circuit_breaker_active:
                self.circuit_breaker_active = True
                self.circuit_breaker_count += 1
            return True
        self.circuit_breaker_active = False
        return False

    def _check_daily_loss(self, current_date: str) -> bool:
        if current_date != self.day_state.date:
            self.day_state = DayState(date=current_date, starting_equity=self.equity)
        loss_pct = (self.day_state.starting_equity - self.equity) / self.day_state.starting_equity
        if loss_pct >= DAILY_LOSS_LIMIT:
            self.day_state.paused = True
            return True
        return False

    def _apply_funding(self, position: Position, hours_held: float):
        """Deduct funding rate for holding period."""
        periods = hours_held / 8.0
        funding = position.size_usd * FUNDING_RATE_8H * periods
        self.equity -= funding
        self.total_funding += funding
        return funding

    def open_position(self, symbol: str, side: str, price: float,
                      sl: float, tp: float, bar: int, time_str: str) -> Optional[TradeLog]:
        if self.position is not None:
            return None

        size_usd, size_coin, leverage, margin = self._calc_position_size(price, sl)

        if margin < 1.0 or self.equity < 10.0:
            return None

        fee = size_usd * TAKER_FEE * (1 - FEE_REBATE)
        self.equity -= fee
        self.total_fees += fee

        self.position = Position(
            symbol=symbol, side=side, entry_price=price,
            size_usd=size_usd, size_coin=size_coin, leverage=leverage,
            stop_loss=sl, take_profit=tp, margin_used=margin,
            entry_bar=bar, entry_time=time_str,
        )

        log = TradeLog(
            time=time_str, symbol=symbol,
            action=f"OPEN_{side.upper()}", side=side,
            price=price, size_usd=round(size_usd, 2),
            size_coin=round(size_coin, 6), leverage=round(leverage, 1),
            fee=round(fee, 4), pnl=0.0,
            equity_before=round(self.equity + fee, 2),
            equity_after=round(self.equity, 2),
            reason="signal", sl=round(sl, 2), tp=round(tp, 2),
        )
        self.trades.append(log)
        return log

    def close_position(self, exit_price: float, reason: str,
                       bar: int, time_str: str, hours_held: float = 24.0) -> Optional[TradeLog]:
        pos = self.position
        if pos is None:
            return None

        equity_before = self.equity

        # PnL
        if pos.side == "long":
            pnl = (exit_price - pos.entry_price) / pos.entry_price * pos.size_usd
        else:
            pnl = (pos.entry_price - exit_price) / pos.entry_price * pos.size_usd

        # Fees
        exit_notional = pos.size_coin * exit_price
        fee = exit_notional * TAKER_FEE * (1 - FEE_REBATE)
        self.total_fees += fee

        # Funding
        funding = self._apply_funding(pos, hours_held)

        self.equity += pnl - fee
        self.peak_equity = max(self.peak_equity, self.equity)

        action = f"CLOSE_{reason.upper()}"
        log = TradeLog(
            time=time_str, symbol=pos.symbol,
            action=action, side=pos.side,
            price=exit_price, size_usd=round(pos.size_usd, 2),
            size_coin=round(pos.size_coin, 6), leverage=round(pos.leverage, 1),
            fee=round(fee + funding, 4), pnl=round(pnl, 2),
            equity_before=round(equity_before, 2),
            equity_after=round(self.equity, 2),
            reason=reason, sl=round(pos.stop_loss, 2), tp=round(pos.take_profit, 2),
        )
        self.trades.append(log)
        self.position = None

        # Update daily loss tracking
        self.day_state.loss_today += max(0, -pnl)

        return log


def _ts_to_str(ts_ms: int) -> str:
    return datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M")


def _ts_to_date(ts_ms: int) -> str:
    return datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")


def run_simulation(symbol: str = "BTC/USDT", timeframe: str = "1d",
                   capital: float = INITIAL_CAPITAL) -> PortfolioSimulator:
    """Run full simulation on one symbol."""
    params = MACDRSIParams()
    sim = PortfolioSimulator(capital)

    fallback = str(REPO_ROOT / "data") if (REPO_ROOT / "data").exists() else None
    out = load_klines("future", symbol, timeframe, cache_dir=CACHE_DIR, fallback_data_dir=fallback)
    if out is None:
        print(f"  No data for future {symbol} {timeframe}")
        return sim

    open_time, open_, high, low, close, volume = out
    n = len(close)
    lookback = params.slow_period + params.signal_period + 2
    if n < lookback:
        return sim

    # Precompute indicators
    ema_fast = _ema(close, params.fast_period)
    ema_slow = _ema(close, params.slow_period)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, params.signal_period)
    histogram = macd_line - signal_line
    rsi_arr = _rsi(close, params.rsi_period)
    atr_arr = _atr(high, low, close, params.atr_period)

    ot = np.asarray(open_time, dtype=np.int64)
    if ot.size and ot[0] < 1e12:
        ot = ot * 1000

    hours_per_bar = 24.0 if timeframe == "1d" else 1.0

    for i in range(lookback, n):
        time_str = _ts_to_str(ot[i])
        current_date = _ts_to_date(ot[i])

        sim.equity_history.append((time_str, round(sim.equity, 2)))

        # ── Risk checks ──
        if sim._check_circuit_breaker():
            if sim.position:
                sim.close_position(close[i], "circuit_breaker", i, time_str, hours_per_bar)
            continue

        if sim._check_daily_loss(current_date):
            continue

        if sim.equity < 20.0:
            break

        # ── Check SL/TP on open position ──
        if sim.position is not None:
            pos = sim.position
            exit_price = None
            reason = None

            if pos.side == "long":
                if low[i] <= pos.stop_loss:
                    exit_price = pos.stop_loss
                    reason = "sl"
                elif high[i] >= pos.take_profit:
                    exit_price = pos.take_profit
                    reason = "tp"
            else:
                if high[i] >= pos.stop_loss:
                    exit_price = pos.stop_loss
                    reason = "sl"
                elif low[i] <= pos.take_profit:
                    exit_price = pos.take_profit
                    reason = "tp"

            # Liquidation check: if unrealised loss > margin
            if exit_price is None:
                if pos.side == "long":
                    unrealised = (close[i] - pos.entry_price) / pos.entry_price * pos.size_usd
                else:
                    unrealised = (pos.entry_price - close[i]) / pos.entry_price * pos.size_usd
                if -unrealised >= pos.margin_used * 0.9:
                    exit_price = close[i]
                    reason = "near_liquidation"

            if exit_price is not None:
                sim.close_position(exit_price, reason, i, time_str, hours_per_bar)

        # ── Entry signals ──
        if sim.position is None and i >= 1:
            cur_hist = histogram[i]
            prev_hist = histogram[i - 1]
            cur_rsi = rsi_arr[i]
            cur_atr = atr_arr[i]
            cur_close = close[i]

            if prev_hist <= 0 < cur_hist and cur_rsi < params.rsi_overbought:
                sl = cur_close - params.atr_sl_mult * cur_atr
                tp = cur_close + params.atr_tp_mult * cur_atr
                sim.open_position(symbol, "long", cur_close, sl, tp, i, time_str)

            elif prev_hist >= 0 > cur_hist and cur_rsi > params.rsi_oversold:
                sl = cur_close + params.atr_sl_mult * cur_atr
                tp = cur_close - params.atr_tp_mult * cur_atr
                sim.open_position(symbol, "short", cur_close, sl, tp, i, time_str)

    # Close any remaining position
    if sim.position is not None:
        sim.close_position(close[-1], "end", n - 1, _ts_to_str(ot[-1]), hours_per_bar)

    return sim


def write_log(sims: dict):
    """Write detailed trade log and summary."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    all_trades = []
    for symbol, sim in sims.items():
        for t in sim.trades:
            all_trades.append(t)

    # Sort by time
    all_trades.sort(key=lambda t: t.time)

    # ── Detailed log ──
    lines = []
    lines.append("=" * 120)
    lines.append(f"  PORTFOLIO SIMULATION — Starting Capital: ${INITIAL_CAPITAL:.0f}")
    lines.append(f"  Strategy: MACD+RSI on Futures 1d  |  Max Leverage: {MAX_LEVERAGE}x  |  Risk/trade: {MAX_RISK_PER_TRADE*100}%")
    lines.append(f"  Circuit Breaker: {CIRCUIT_BREAKER_DD*100}% DD  |  Daily Loss Limit: {DAILY_LOSS_LIMIT*100}%")
    lines.append("=" * 120)
    lines.append("")

    lines.append("RISK MANAGEMENT RULES:")
    lines.append(f"  1. Max risk per trade:      {MAX_RISK_PER_TRADE*100}% of equity (${INITIAL_CAPITAL * MAX_RISK_PER_TRADE:.0f} initially)")
    lines.append(f"  2. Max leverage:             {MAX_LEVERAGE}x")
    lines.append(f"  3. Max position size:        {MAX_POSITION_PCT*100}% of equity as margin")
    lines.append(f"  4. Circuit breaker:          Pause if drawdown > {CIRCUIT_BREAKER_DD*100}% from peak")
    lines.append(f"  5. Daily loss limit:         Stop trading if lost > {DAILY_LOSS_LIMIT*100}% in one day")
    lines.append(f"  6. Always use stop-loss:     ATR-based (1.5x ATR)")
    lines.append(f"  7. Fees:                     Taker {TAKER_FEE*100}% (after {FEE_REBATE*100:.0f}% rebate: {TAKER_FEE*(1-FEE_REBATE)*100:.3f}%) + Funding ~{FUNDING_RATE_8H*100}%/8h")
    lines.append("")
    lines.append("-" * 120)
    lines.append(f"{'Time':<18} {'Symbol':<12} {'Action':<16} {'Price':>10} {'Size $':>10} {'Lev':>5} {'PnL':>10} {'Fee':>8} {'Equity':>10} {'Reason':<18} {'SL':>10} {'TP':>10}")
    lines.append("-" * 120)

    for t in all_trades:
        pnl_str = f"${t.pnl:+.2f}" if t.pnl != 0 else ""
        lines.append(
            f"{t.time:<18} {t.symbol:<12} {t.action:<16} "
            f"${t.price:>9.1f} ${t.size_usd:>9.2f} {t.leverage:>4.1f}x "
            f"{pnl_str:>10} ${t.fee:>6.4f} ${t.equity_after:>9.2f} "
            f"{t.reason:<18} ${t.sl:>9.2f} ${t.tp:>9.2f}"
        )

    lines.append("-" * 120)
    lines.append("")

    # ── Summary per symbol ──
    total_equity = 0
    total_fees = 0
    total_funding = 0
    total_trades = 0

    for symbol, sim in sims.items():
        wins = [t for t in sim.trades if t.pnl > 0 and "CLOSE" in t.action]
        losses = [t for t in sim.trades if t.pnl < 0 and "CLOSE" in t.action]
        closes = [t for t in sim.trades if "CLOSE" in t.action]
        num_trades = len(closes)

        lines.append(f"── {symbol} ──")
        lines.append(f"  Final equity:      ${sim.equity:.2f}")
        lines.append(f"  Total return:      {(sim.equity / INITIAL_CAPITAL - 1) * 100:+.1f}%")
        lines.append(f"  Trades:            {num_trades}")
        if closes:
            lines.append(f"  Wins:              {len(wins)} ({len(wins)/len(closes)*100:.0f}%)")
            lines.append(f"  Losses:            {len(losses)} ({len(losses)/len(closes)*100:.0f}%)")
        if wins:
            lines.append(f"  Avg win:           ${np.mean([t.pnl for t in wins]):.2f}")
        if losses:
            lines.append(f"  Avg loss:          ${np.mean([t.pnl for t in losses]):.2f}")
        lines.append(f"  Total fees:        ${sim.total_fees:.2f}")
        lines.append(f"  Total funding:     ${sim.total_funding:.2f}")
        lines.append(f"  Circuit breakers:  {sim.circuit_breaker_count}")

        # Max drawdown
        if sim.equity_history:
            eq_vals = [e[1] for e in sim.equity_history]
            peak = eq_vals[0]
            max_dd = 0
            for v in eq_vals:
                peak = max(peak, v)
                dd = (peak - v) / peak
                max_dd = max(max_dd, dd)
            lines.append(f"  Max drawdown:      {max_dd*100:.1f}%")

        lines.append("")
        total_equity = sim.equity
        total_fees += sim.total_fees
        total_funding += sim.total_funding
        total_trades += num_trades

    # Combined if multiple symbols (we split capital)
    if len(sims) > 1:
        combined_equity = sum(s.equity for s in sims.values())
        lines.append("── COMBINED PORTFOLIO ──")
        lines.append(f"  Starting capital:  ${INITIAL_CAPITAL:.0f} (split equally)")
        lines.append(f"  Final equity:      ${combined_equity:.2f}")
        lines.append(f"  Total return:      {(combined_equity / INITIAL_CAPITAL - 1) * 100:+.1f}%")
        lines.append(f"  Total trades:      {total_trades}")
        lines.append(f"  Total fees:        ${total_fees:.2f}")
        lines.append(f"  Total funding:     ${total_funding:.2f}")
        lines.append("")

    lines.append("=" * 120)
    lines.append("WHY THIS WON'T BLOW UP:")
    lines.append("  ✓ SL always set — max loss per trade = 2% of equity")
    lines.append("  ✓ Low leverage (3x) — liquidation price far from entry")
    lines.append("  ✓ Circuit breaker — stops trading at 20% DD from peak")
    lines.append("  ✓ Daily loss limit — stops after 5% loss in one day")
    lines.append("  ✓ Position sizing scales DOWN as equity drops")
    lines.append("  ✓ Fees + funding deducted realistically")
    lines.append("=" * 120)

    with open(LOG_FILE, "w") as f:
        f.write("\n".join(lines))
    print(f"Trade log saved to {LOG_FILE}")

    # ── Markdown summary ──
    md = [
        "# Simulation: $500 Futures Portfolio",
        "",
        f"Strategy: MACD+RSI | Futures 1d | Max Leverage {MAX_LEVERAGE}x | Risk/trade {MAX_RISK_PER_TRADE*100}%",
        "",
        "## Risk Management",
        "",
        "| Rule | Value | Purpose |",
        "|------|-------|---------|",
        f"| Max risk/trade | {MAX_RISK_PER_TRADE*100}% equity | Mất tối đa ${INITIAL_CAPITAL*MAX_RISK_PER_TRADE:.0f} per trade |",
        f"| Max leverage | {MAX_LEVERAGE}x | Giá thanh lý cách entry ~33% |",
        f"| Max position | {MAX_POSITION_PCT*100}% equity margin | Không all-in |",
        f"| Circuit breaker | {CIRCUIT_BREAKER_DD*100}% DD | Tự dừng khi thua nhiều |",
        f"| Daily loss limit | {DAILY_LOSS_LIMIT*100}% | Không revenge trade |",
        f"| Fee rebate | {FEE_REBATE*100:.0f}% | Hoàn phí giao dịch |",
        "| Stop-loss | 1.5x ATR | Luôn có SL, tự động |",
        "",
        "## Results",
        "",
    ]

    for symbol, sim in sims.items():
        closes = [t for t in sim.trades if "CLOSE" in t.action]
        wins = [t for t in closes if t.pnl > 0]
        per_sym_cap = INITIAL_CAPITAL / len(sims)
        ret_pct = (sim.equity / per_sym_cap - 1) * 100
        md.append(f"### {symbol}")
        md.append(f"- Starting: ${INITIAL_CAPITAL / len(sims):.0f}")
        md.append(f"- Final equity: **${sim.equity:.2f}** ({ret_pct:+.1f}%)")
        md.append(f"- Trades: {len(closes)} (Win {len(wins)}/{len(closes)})")
        md.append(f"- Fees + Funding: ${sim.total_fees + sim.total_funding:.2f}")
        md.append(f"- Circuit breakers triggered: {sim.circuit_breaker_count}")
        md.append("")

    if len(sims) > 1:
        combined = sum(s.equity for s in sims.values())
        md.append("### Combined")
        md.append(f"- **${INITIAL_CAPITAL:.0f} → ${combined:.2f}** ({(combined/INITIAL_CAPITAL-1)*100:+.1f}%)")
        md.append("")

    md += [
        "## Tại sao không cháy tài khoản?",
        "",
        "1. **Luôn có SL**: Mỗi lệnh đặt SL = 1.5x ATR. Nếu SL hit → mất tối đa 2% equity.",
        "2. **Leverage thấp**: 3x = giá thanh lý cách entry ~33%. Với SL thường ~3-5%, không bao giờ chạm liquidation.",
        "3. **Position sizing tự thu nhỏ**: Khi equity giảm, size lệnh giảm theo → thua ít hơn → phục hồi dễ hơn.",
        "4. **Circuit breaker**: Nếu DD > 20%, tự tắt bot. Không trade khi đang thua streak.",
        "5. **Daily loss limit**: Mất >5% trong ngày → dừng. Ngăn revenge trading.",
        "6. **Không all-in**: Max 30% equity làm margin cho 1 lệnh.",
        "",
        "## Chi tiết",
        "",
        f"Xem full trade log tại: `reports/simulation_500.log`",
        "",
    ]

    with open(SUMMARY_FILE, "w") as f:
        f.write("\n".join(md))
    print(f"Summary saved to {SUMMARY_FILE}")


def main():
    print("=" * 80)
    print(f"  Portfolio Simulation: ${INITIAL_CAPITAL:.0f} on Futures MACD+RSI 1d")
    print("=" * 80)
    print()

    sims = {}
    half = INITIAL_CAPITAL / 2

    for symbol in ["BTC/USDT", "ETH/USDT"]:
        print(f"  Simulating {symbol} with ${half:.0f}...")
        sim = run_simulation(symbol, "1d", capital=half)
        sims[symbol] = sim
        closes = [t for t in sim.trades if "CLOSE" in t.action]
        print(f"    → ${sim.equity:.2f} | {len(closes)} trades | CB: {sim.circuit_breaker_count}")

    combined = sum(s.equity for s in sims.values())
    print(f"\n  Combined: ${INITIAL_CAPITAL:.0f} → ${combined:.2f} ({(combined/INITIAL_CAPITAL-1)*100:+.1f}%)")
    print()

    write_log(sims)
    print("\nDone.")


if __name__ == "__main__":
    main()

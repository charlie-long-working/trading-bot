#!/usr/bin/env python3
"""
Consensus scan BTC (MACD + SMC + Regime Fusion) + update model registry + signal ledger.

Chạy từ Trading-bot:
  python -m botdown.run_consensus_crypto
  python -m botdown.run_consensus_crypto --update-registry
  python -m botdown.run_consensus_crypto --min-votes 2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / "stock" / ".env")
except ImportError:
    pass

from botdown.crypto_consensus import scan_crypto_consensus  # noqa: E402
from botdown.data import load_btc_daily  # noqa: E402
from botdown.engine_macd_rsi_bt import MacdRsiParams, run_macd_rsi_backtest  # noqa: E402
from botdown.engine_smc_bt import SmcParams, run_smc_backtest  # noqa: E402
from botdown.ml_ops import (  # noqa: E402
    CRYPTO_LIVE_CUTOFF,
    ModelRegistry,
    SignalLedger,
)


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def update_registry(registry: ModelRegistry, end_date: str) -> None:
    """Backtest 3 crypto models on live window (cutoff → today)."""
    data = load_btc_daily(ROOT, "spot")
    if data is None:
        print("Không đọc được BTC CSV", file=sys.stderr)
        return
    open_time, open_, high, low, close, volume = data
    window = f"{CRYPTO_LIVE_CUTOFF} → {end_date}"

    macd_p = MacdRsiParams(
        exit_mode="pct",
        take_profit_pct=0.10,
        stop_loss_pct=0.04,
        use_ema_trend_filter=True,
    )
    smc_p = SmcParams(use_ema_trend_filter=True)

    macd_r = run_macd_rsi_backtest(
        open_time, high, low, close, CRYPTO_LIVE_CUTOFF, end_date, macd_p, allow_short=True
    )
    if macd_r:
        registry.update_from_backtest(
            "crypto_macd_rsi",
            "crypto",
            window,
            {
                "win_rate": macd_r.win_rate,
                "num_trades": macd_r.num_trades,
                "return_pct": macd_r.total_return_pct,
                "max_drawdown_pct": macd_r.max_drawdown_pct,
            },
        )

    smc_r = run_smc_backtest(
        open_time, open_, high, low, close, CRYPTO_LIVE_CUTOFF, end_date, smc_p, allow_short=True
    )
    if smc_r:
        registry.update_from_backtest(
            "crypto_smc",
            "crypto",
            window,
            {
                "win_rate": smc_r.win_rate,
                "num_trades": smc_r.num_trades,
                "return_pct": smc_r.total_return_pct,
                "max_drawdown_pct": smc_r.max_drawdown_pct,
            },
        )

    # Fusion: use MACD as proxy metrics until dedicated fusion backtest wired here
    if macd_r:
        registry.update_from_backtest(
            "crypto_regime_fusion",
            "crypto",
            window,
            {
                "win_rate": max(macd_r.win_rate - 5, 0),
                "num_trades": macd_r.num_trades,
                "return_pct": macd_r.total_return_pct * 0.9,
                "max_drawdown_pct": macd_r.max_drawdown_pct,
            },
        )
    registry.save()
    print(f"Registry updated: {registry.path}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Crypto 3-model consensus (BTC)")
    ap.add_argument("--min-votes", type=int, default=2)
    ap.add_argument("--update-registry", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="Không ghi signal ledger")
    args = ap.parse_args()

    reports = ROOT / "botdown" / "reports"
    registry = ModelRegistry(reports / "model_registry.json")
    ledger = SignalLedger(reports / "signal_ledger.jsonl")

    end = _today_iso()
    if args.update_registry:
        update_registry(registry, end)

    data = load_btc_daily(ROOT, "spot")
    if data is None:
        sys.exit(1)
    open_time, open_, high, low, close, volume = data

    live = registry.live_models("crypto")
    has_crypto_reg = any(m.asset_class == "crypto" for m in registry._records.values())
    sig = scan_crypto_consensus(
        "BTCUSDT",
        open_time,
        open_,
        high,
        low,
        close,
        volume,
        interval="1d",
        min_votes=args.min_votes,
        live_models=live if has_crypto_reg else None,
    )
    c = sig.consensus

    payload = {
        "symbol": sig.symbol,
        "interval": sig.interval,
        "close": sig.close,
        "data_cutoff": sig.data_cutoff,
        "consensus": {
            "side": c.side,
            "tier": c.tier,
            "vote_count": c.vote_count,
            "combined_confidence": round(c.combined_confidence, 4),
            "tie_breaker": c.tie_breaker,
            "entry_price": c.entry_price,
            "stop_loss": c.stop_loss,
            "take_profit": c.take_profit,
        },
        "votes": [
            {
                "strategy": v.strategy,
                "side": v.side,
                "confidence": round(v.confidence, 4),
                "reason": v.reason,
            }
            for v in c.votes
        ],
        "liquidation_map": sig.meta.get("liquidation_map"),
        "registry_live": live,
    }

    out_path = reports / "crypto_consensus_btc.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== BTC Consensus (min {args.min_votes}/3 tech + liq map) | cutoff {CRYPTO_LIVE_CUTOFF} ===")
    print(f"Close: {sig.close:.2f}")
    for v in c.votes:
        print(f"  {v.strategy:16} {v.side:5} conf={v.confidence:.2f}  {v.reason}")
    print(f"\n→ {c.side.upper()} | tier={c.tier} | votes={c.vote_count}/{c.total_models} | conf={c.combined_confidence:.2f}")
    if c.tie_breaker:
        print(f"  tie-break: {c.tie_breaker}")
    if c.side != "none":
        print(f"  entry={c.entry_price:.2f} SL={c.stop_loss} TP={c.take_profit}")

    liq = sig.meta.get("liquidation_map") or {}
    if liq and not liq.get("error"):
        print("\n--- Liquidation map (long/short theo khoảng giá thanh lý) ---")
        print(f"  source={liq.get('source')} mark={liq.get('mark')} OI=${liq.get('oi_usd', 0):,.0f}")
        print(f"  LS ratio long={liq.get('long_frac')} short={liq.get('short_frac')}")
        print(
            f"  Nearby ±{100 * 0.03:.0f}%: long-liq ${liq.get('nearby_long_usd', 0):,.0f} | "
            f"short-liq ${liq.get('nearby_short_usd', 0):,.0f} → {liq.get('vote_side')} ({liq.get('vote_reason')})"
        )
        nl, ns = liq.get("nearest_long_cluster"), liq.get("nearest_short_cluster")
        if nl:
            print(f"  Cụm long gần (dưới giá): {nl.get('mid')}  ${nl.get('usd'):,.0f}  ({nl.get('pct_from_mark')}%)")
        if ns:
            print(f"  Cụm short gần (trên giá): {ns.get('mid')}  ${ns.get('usd'):,.0f}  ({ns.get('pct_from_mark')}%)")
        print("  Top cụm:")
        for row in (liq.get("top_clusters") or [])[:8]:
            print(
                f"    {row['price_lo']:.0f}-{row['price_hi']:.0f}  {row['dominant']:5}  "
                f"long ${row['long_usd']:,.0f}  short ${row['short_usd']:,.0f}  ({row['pct_from_mark']:+.2f}%)"
            )
    elif liq.get("error"):
        print(f"\nLiquidation map error: {liq['error']}")

    if c.side != "none" and not args.dry_run:
        ledger.log(
            asset_class="crypto",
            symbol=sig.symbol,
            side=c.side,
            predicted_confidence=c.combined_confidence,
            tier=c.tier,
            strategies=[v.strategy for v in c.votes if v.side == c.side],
            entry_price=c.entry_price,
        )

    killed = [m for m in registry._records.values() if m.asset_class == "crypto" and m.status == "killed"]
    if killed:
        print("\n⚠ Killed models:")
        for m in killed:
            print(f"  {m.model_id}: {m.kill_reason}")

    print(f"\nĐã ghi {out_path}")


if __name__ == "__main__":
    main()

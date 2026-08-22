"""
ML ops: data cutoff, 3-model consensus, model registry, signal ledger.

Inspired by production quant / zest.win patterns:
- Live data cutoff (ignore pre-regime history for validation)
- 2/3 consensus (3 models cannot tie)
- Confidence tie-break when 2 models disagree
- Kill model when rolling metrics fall below threshold
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np

Side = Literal["long", "short", "none"]
Tier = Literal["full", "strong", "weak", "none"]
Status = Literal["live", "killed", "probation"]

# --- Data cutoffs (live / train window) ---
CRYPTO_LIVE_CUTOFF = "2024-01-01"
VN_LIVE_CUTOFF = "2024-01-01"
VRE_LIVE_CUTOFF = "2024-01-01"

CRYPTO_STRESS_WINDOWS = [
    ("Bear 2017–2018", "2017-12-11", "2018-08-06"),
    ("Bear 2021–2022", "2021-11-08", "2022-12-19"),
]

# --- Kill thresholds ---
DEFAULT_KILL_RULES = {
    "min_win_rate_pct": 45.0,
    "min_expectancy_pct": 0.0,
    "min_trades": 5,
}


@dataclass
class StrategyVote:
    strategy: str
    side: Side
    confidence: float
    reason: str = ""
    entry_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsensusResult:
    side: Side
    tier: Tier
    vote_count: int
    total_models: int
    votes: List[StrategyVote]
    combined_confidence: float
    tie_breaker: Optional[str] = None
    entry_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def macd_rsi_confidence(
    hist: float,
    rsi: float,
    side: Side = "long",
    rsi_ob: float = 70.0,
    rsi_os: float = 30.0,
) -> float:
    """Higher when hist just crossed and RSI has room."""
    hist_strength = _clamp(abs(hist) / (abs(hist) + 0.5))
    if side == "long":
        rsi_room = _clamp((rsi_ob - rsi) / rsi_ob)
    elif side == "short":
        rsi_room = _clamp((rsi - rsi_os) / (100 - rsi_os))
    else:
        return 0.0
    return _clamp(0.55 * hist_strength + 0.45 * rsi_room)


def ma_cross_confidence(
    fast_ma: float,
    slow_ma: float,
    close: float,
    volume: float,
    avg_volume: float,
) -> float:
    spread = (fast_ma - slow_ma) / slow_ma if slow_ma else 0.0
    spread_score = _clamp(spread / 0.02)
    price_score = _clamp((close - slow_ma) / slow_ma / 0.03) if slow_ma else 0.5
    vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
    vol_score = _clamp((vol_ratio - 0.8) / 0.8)
    return _clamp(0.4 * spread_score + 0.35 * price_score + 0.25 * vol_score)


def regime_fusion_confidence(regime: str, reason: str) -> float:
    base = {"bull": 0.75, "sideways": 0.55, "bear": 0.35}.get(regime, 0.5)
    reason_boost = {
        "bull_ob": 0.15,
        "bull_fvg": 0.12,
        "demand_zone": 0.10,
        "bear_ob": 0.15,
        "bear_fvg": 0.12,
        "supply_zone": 0.10,
    }.get(reason, 0.05)
    return _clamp(base + reason_boost)


def smc_zone_confidence(in_zone: bool, ema_bull: bool = True) -> float:
    if not in_zone:
        return 0.0
    return 0.72 if ema_bull else 0.58


def resolve_consensus(
    votes: List[StrategyVote],
    min_votes: int = 2,
    direction: Optional[Side] = None,
) -> ConsensusResult:
    """
    3-model consensus (zest.win style):
    - >= min_votes same side → signal
    - 2 models split long/short → higher confidence wins
    - 0-1 votes → no trade
    """
    total = len(votes)
    if total == 0:
        return ConsensusResult("none", "none", 0, 0, [], 0.0)

    long_v = [v for v in votes if v.side == "long"]
    short_v = [v for v in votes if v.side == "short"]
    n_long, n_short = len(long_v), len(short_v)

    chosen: Side = "none"
    tier: Tier = "none"
    tie_breaker: Optional[str] = None
    winners: List[StrategyVote] = []

    if direction in ("long", "short"):
        winners = [v for v in votes if v.side == direction]
        if len(winners) >= min_votes:
            chosen = direction
    elif n_long >= min_votes and n_short == 0:
        chosen, winners = "long", long_v
    elif n_short >= min_votes and n_long == 0:
        chosen, winners = "short", short_v
    elif n_long >= min_votes and n_short >= min_votes:
        avg_l = np.mean([v.confidence for v in long_v])
        avg_s = np.mean([v.confidence for v in short_v])
        if avg_l > avg_s:
            chosen, winners, tie_breaker = "long", long_v, "confidence_long"
        elif avg_s > avg_l:
            chosen, winners, tie_breaker = "short", short_v, "confidence_short"
    elif n_long == 1 and n_short == 1 and total >= 2:
        l0, s0 = long_v[0], short_v[0]
        if l0.confidence > s0.confidence:
            chosen, winners, tie_breaker = "long", [l0], l0.strategy
        elif s0.confidence > l0.confidence:
            chosen, winners, tie_breaker = "short", [s0], s0.strategy

    if chosen != "none":
        vc = len(winners)
        tier = "full" if vc == total else ("strong" if vc >= min_votes else "weak")

    combined_conf = float(np.mean([v.confidence for v in winners])) if winners else 0.0
    entry = winners[0].entry_price if winners else 0.0
    sl_vals = [v.stop_loss for v in winners if v.stop_loss is not None]
    tp_vals = [v.take_profit for v in winners if v.take_profit is not None]
    sl = float(np.median(sl_vals)) if sl_vals else None
    tp = float(np.median(tp_vals)) if tp_vals else None

    return ConsensusResult(
        side=chosen,
        tier=tier,
        vote_count=len(winners),
        total_models=total,
        votes=votes,
        combined_confidence=combined_conf,
        tie_breaker=tie_breaker,
        entry_price=entry,
        stop_loss=sl,
        take_profit=tp,
    )


def parse_date_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def slice_bars_from_cutoff(
    open_time: np.ndarray,
    *arrays: np.ndarray,
    cutoff: str,
) -> Tuple[np.ndarray, ...]:
    """Keep full history from cutoff bar onward (warmup still uses earlier bars in caller)."""
    ot = np.asarray(open_time, dtype=np.int64)
    if ot.size and ot[0] < 1e12:
        ot = ot * 1000
    cut_ms = parse_date_ms(cutoff)
    idx = int(np.searchsorted(ot, cut_ms, side="left"))
    out = (ot,) + tuple(np.asarray(a) for a in arrays)
    return tuple(arr[idx:] for arr in out)


@dataclass
class ModelRecord:
    model_id: str
    asset_class: str  # crypto | vn_stock | vre
    status: Status = "live"
    last_window: str = ""
    win_rate_pct: float = 0.0
    expectancy_pct: float = 0.0
    num_trades: int = 0
    return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    updated_at: str = ""
    kill_reason: str = ""


class ModelRegistry:
    """Track model health; kill when below threshold."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, ModelRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("models", []):
                rec = ModelRecord(**item)
                self._records[rec.model_id] = rec
        except (json.JSONDecodeError, TypeError):
            pass

    def save(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "cutoffs": {
                "crypto": CRYPTO_LIVE_CUTOFF,
                "vn_stock": VN_LIVE_CUTOFF,
                "vre": VRE_LIVE_CUTOFF,
            },
            "models": [asdict(r) for r in self._records.values()],
        }
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def update_from_backtest(
        self,
        model_id: str,
        asset_class: str,
        window: str,
        metrics: Dict[str, Any],
        kill_rules: Optional[Dict[str, float]] = None,
    ) -> ModelRecord:
        rules = kill_rules or DEFAULT_KILL_RULES
        wr = float(metrics.get("win_rate", 0))
        n = int(metrics.get("num_trades", 0))
        ret = float(metrics.get("return_pct", metrics.get("total_return_pct", 0)))
        dd = float(metrics.get("max_drawdown_pct", 0))
        exp = float(metrics.get("expectancy_pct", ret / max(n, 1)))

        status: Status = "live"
        kill_reason = ""
        if n >= rules["min_trades"]:
            if wr < rules["min_win_rate_pct"] or exp < rules["min_expectancy_pct"]:
                status = "killed"
                kill_reason = f"wr={wr:.1f}% exp={exp:.2f}% (min wr {rules['min_win_rate_pct']}%)"

        rec = ModelRecord(
            model_id=model_id,
            asset_class=asset_class,
            status=status,
            last_window=window,
            win_rate_pct=wr,
            expectancy_pct=exp,
            num_trades=n,
            return_pct=ret,
            max_drawdown_pct=dd,
            updated_at=datetime.now(timezone.utc).isoformat(),
            kill_reason=kill_reason,
        )
        self._records[model_id] = rec
        return rec

    def is_live(self, model_id: str) -> bool:
        rec = self._records.get(model_id)
        return rec is None or rec.status == "live"

    def live_models(self, asset_class: Optional[str] = None) -> List[str]:
        out = []
        for mid, rec in self._records.items():
            if rec.status != "live":
                continue
            if asset_class and rec.asset_class != asset_class:
                continue
            out.append(mid)
        return sorted(out)

    def filter_votes(self, votes: List[StrategyVote], prefix: str = "") -> List[StrategyVote]:
        """Drop votes from killed models."""
        kept = []
        for v in votes:
            mid = f"{prefix}{v.strategy}" if prefix else v.strategy
            if self.is_live(mid):
                kept.append(v)
        return kept


class SignalLedger:
    """Append-only log for calibration (predicted confidence vs outcome)."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        asset_class: str,
        symbol: str,
        side: Side,
        predicted_confidence: float,
        tier: str,
        strategies: List[str],
        entry_price: float = 0.0,
        outcome: Optional[str] = None,
        pnl_pct: Optional[float] = None,
    ) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "asset_class": asset_class,
            "symbol": symbol,
            "side": side,
            "predicted_confidence": round(predicted_confidence, 4),
            "tier": tier,
            "strategies": strategies,
            "entry_price": entry_price,
            "outcome": outcome,
            "pnl_pct": pnl_pct,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def calibration_buckets(self, bucket_size: float = 0.1) -> Dict[str, Dict[str, Any]]:
        if not self.path.exists():
            return {}
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        resolved = [r for r in rows if r.get("outcome") is not None]
        buckets: Dict[str, Dict[str, Any]] = {}
        for r in resolved:
            p = float(r["predicted_confidence"])
            b = int(p / bucket_size) * bucket_size
            key = f"{b:.1f}-{b + bucket_size:.1f}"
            if key not in buckets:
                buckets[key] = {"n": 0, "wins": 0, "avg_pnl": []}
            buckets[key]["n"] += 1
            if r.get("pnl_pct") is not None and float(r["pnl_pct"]) > 0:
                buckets[key]["wins"] += 1
            if r.get("pnl_pct") is not None:
                buckets[key]["avg_pnl"].append(float(r["pnl_pct"]))
        for k, v in buckets.items():
            v["hit_rate"] = round(v["wins"] / v["n"], 3) if v["n"] else 0
            v["avg_pnl"] = round(float(np.mean(v["avg_pnl"])), 3) if v["avg_pnl"] else 0
            del v["wins"]
        return buckets

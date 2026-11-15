---
name: trading-bot
description: >-
  Navigate and change the Trading-bot crypto repo (botdown engines, OI+USDT.D
  Telegram alerts on GitHub Actions, OKX Regime Fusion bot, MACD+RSI backtest/live
  bot, TradingView webhook, Binance Vision crawler, Streamlit OI dashboard). Use
  when editing Trading-bot, botdown, data_loaders, OI alerts, OKX bot, Binance/Gate
  fallbacks, or when the user mentions crypto live alerts / GHA oi-telegram — for
  OI scenario math use crypto-oi-usdtd; not for VN stocks (vn-stock) or gold (precious-metals).
---

# Trading-bot (crypto)

Repo: `Documents/Cursor/Trading-bot` (git, **public**: `charlie-long-working/trading-bot`).
Read this first instead of scanning the tree. Deep dives: [architecture.md](architecture.md), [entrypoints.md](entrypoints.md), `docs/ARCHITECTURE.md`.
OI playbook math → skill `crypto-oi-usdtd`. VN → `vn-stock`. Vàng/bạc → `precious-metals`.

## Agent rules

1. `PYTHONPATH=.` từ gốc repo, `.venv/bin/python` (3.13). Đọc `botdown/reports/` trước khi chạy lại.
2. Nhà chính: `botdown/` + `data_loaders/`. Không mở rộng `archive/`.
3. Không tạo Telegram client / webhook / engine MACD thứ hai (`notify/telegram.py` là duy nhất).
4. GHA: đừng giả định Binance `fapi` / `api.binance.com` chạy (451) — dùng fallback trong `oi_history.py`.
5. **Repo khác import từ đây**: `stock` và `precious-metals` dùng `botdown.engine_macd_rsi_bt` (kể cả `_ema`, `_rsi_wilder`), `engine_smc_bt`, `ml_ops`, `crypto_consensus`; `real-estate` dùng `data_loaders.liquidation_map`. Đổi tên/chữ ký → sửa cả repo kia. Để repo private sẽ cần `TB_CHECKOUT_TOKEN` ở CI của chúng.
6. Test Telegram luôn `--dry-run`. Lệnh đặt lệnh thật (OKX/ccxt) mặc định dry-run — không tắt nếu user chưa yêu cầu.

## Trạng thái (15/11/2026)

- **Swing 1D/1W chạy local**: launchd `com.cursor.swing-crypto` 07:10 VN hằng ngày → `botdown/run_swing_signals.py` (OI G/K/I trên nến ngày đã đóng, TP8/SL3/10 nến, chỉ báo khi kịch bản vừa bật + MACD+RSI pct EMA) + bản tin xu hướng tuần BTC/ETH. Module chung cho cả stock/precious-metals: `botdown/swing_common.py` (đổi API thì sửa 3 repo). Log `~/Library/Logs/swing/crypto.log`, dedupe `data/swing/swing_sent.json`. H1/H4 vẫn ở GitHub Actions.

- OI alerts **bật lại 15/11/2026** (bị `disabled_inactivity` 22/10–15/11). Repo public: 60 ngày không push GitHub lại tắt — bật bằng `gh workflow enable oi-telegram-alerts.yml`. Cron `45 * * * *` bị giãn còn ~5 lần/ngày.
- Đã sửa 15/11 (`9da9903`): text Telegram được `html.escape` — trước đó cảnh báo K bị Telegram từ chối (`<` thô) mà job vẫn xanh. Thêm text mới vào tin HTML thì luôn escape.
- Cache local cũ: `data/macro/usdt_d_daily.csv` dừng 2026-08-22 và loader không kiểm tra ngày cuối → scan local (dashboard, `run_oi_telegram` trên máy) dùng USDT.D phẳng. GHA không bị vì mỗi lần chạy không có cache.
- `run_okx_bot._size_to_sz` làm tròn số hợp đồng về 0 với `--size-usdt 100` (BTC/ETH); cần khoá OKX kể cả `--paper`.
- Dockerfile hỏng (CMD trỏ `dashboard.app` đã chuyển vào `archive/`).
- Hai bộ tên env OKX: `run_okx_bot` đọc `OKX_SECRET_KEY/OKX_PASSPHRASE/OKX_DEMO`; ccxt (`exchange_factory`) đọc `OKX_API_SECRET/OKX_API_PASSPHRASE/OKX_SANDBOX`.

## Where to change what

| Task | Touch |
|------|--------|
| Live OI alert text / I+K | `botdown/oi_live_signal.py` |
| OI dashboard | `botdown/dashboard_oi_playbook.py` (`python run_strategy_dashboard.py`, :8501) |
| OI scenarios A–K | `botdown/oi_liq_strategy.py` |
| Fetch OI/klines/funding | `data_loaders/oi_history.py` |
| USDT.D | `data_loaders/usdt_d.py` |
| Liquidation map | `data_loaders/liquidation_map.py` |
| Telegram send | `notify/telegram.py` + `botdown/run_oi_telegram.py` |
| Cron | `.github/workflows/oi-telegram-alerts.yml` |
| OKX Fusion live | `run_okx_bot.py`, `signals/okx_signal.py`, `exchange/okx_client.py`, `strategy/*` |
| MACD backtest (SoT) | `botdown/engine_macd_rsi_bt.py`, `botdown/run_backtest_macd_rsi.py` |
| MACD live ccxt | `botdown/bot_macd_rsi.py`, `botdown/exchange_factory.py` |
| TradingView → OKX | `botdown/tradingview_okx_webhook.py` |
| Downtrend short MTF | `botdown/bot.py`, `botdown/strategy*.py`, `engine*.py` |
| Consensus / registry | `botdown/crypto_consensus.py`, `botdown/ml_ops.py` |
| Pine | `tradingview/*.pine` |

## Quick commands

```bash
cd /Users/namnguyen/Documents/Cursor/Trading-bot
export PYTHONPATH=.
PY=.venv/bin/python
$PY -m botdown.run_oi_telegram --dry-run --interval 1h --no-liq
$PY -m botdown.run_oi_scenarios --interval 1h,4h --refresh
$PY -m botdown.run_liquidation_map --symbol BTCUSDT
$PY -m botdown.run_backtest_macd_rsi --interval 1d --exit pct --tp-pct 0.10 --sl-pct 0.04
$PY run_okx_signal_only.py --symbols BTCUSDT --market swap --interval 1h
gh workflow list ; gh run list --limit 10
```

## Trace OI alert

GHA run → `run_oi_telegram` → `build_oi_panel_recent` (nguồn: vision klines / Gate OI / Gate funding) → `enrich_features` → I/K → `format_oi_telegram` → `notify.telegram` (xem log `SEND FAIL`).

Khi thêm entrypoint hoặc file nguồn sự thật: thêm một dòng vào `docs/ARCHITECTURE.md` và [entrypoints.md](entrypoints.md).

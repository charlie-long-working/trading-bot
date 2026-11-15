# Trading-bot

Crypto trading: **OI + USDT.D Telegram alerts**, OKX Regime Fusion bot, MACD/RSI backtests.

VN stocks → [`stock/`](../stock). VRE / BĐS → [`real-estate/`](../real-estate).  
**Agents:** read `.cursor/skills/trading-bot/SKILL.md` (also under workspace `.cursor/skills/`).  
**Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Setup

```bash
cd /Users/namnguyen/Documents/Cursor/Trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Telegram / OKX / optional FRED
export PYTHONPATH=.
```

## Most-used commands

```bash
# Live playbook dashboard (I+K, TP/SL, scan BTC/ETH)
python run_strategy_dashboard.py
# hoặc: PYTHONPATH=. streamlit run botdown/dashboard_oi_playbook.py

# Live OI alerts (same as GitHub Actions)
python -m botdown.run_oi_telegram --dry-run --interval auto

# Static web snapshot → GitHub Pages (see "Static web" below)
scripts/publish_static.sh

# OI scenario research
python -m botdown.run_oi_scenarios --interval 1h,4h

# OKX Fusion bot
python run_okx_bot.py

# MACD backtest
python -m botdown.run_backtest_macd_rsi --interval 1d --exit pct --tp-pct 0.10 --sl-pct 0.04
```

## Layout (short)

| Path | Role |
|------|------|
| `botdown/` | Engines, OI live/scenarios, MACD bot |
| `data_loaders/` | Exchange/API I/O |
| `strategy/` `signals/` `exchange/` | Regime Fusion + OKX |
| `notify/` | Telegram |
| `data/` | Caches |
| `archive/` | Legacy (botv2, old dashboard/webhooks) — do not extend |
| `.github/workflows/oi-telegram-alerts.yml` | Hourly OI → Telegram |
| `web/` + `scripts/*static*` | Static OI playbook site (GitHub Pages) |

## Secrets (GHA)

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` only for OI alerts. OKX keys stay local/VPS.

## Static web

Bản web tĩnh của dashboard OI playbook (I+K), chạy song song với Streamlit:
**https://charlie-long-working.github.io/trading-bot/**

### Kiến trúc

```
launchd (Mac, 15 phút) → scripts/publish_static.sh
  ├─ scripts/export_static_snapshot.py      scan BTC/ETH × 1h/4h (botdown/oi_snapshot.py, chung với Streamlit)
  │    ├─ allowlist + sanitize()            botdown/static_snapshot.py
  │    ├─ web/data/latest.json              ghi atomic (tmp → rename); scan lỗi toàn bộ → giữ file cũ
  │    └─ var/static-history/<UTC>.json     LOCAL, gitignored, tự xoá file > 30 ngày
  ├─ tests/test_static_snapshot_privacy.py  dừng nếu lộ path/username/token/field ngoài allowlist
  ├─ rsync web/ → var/gh-pages-wt           worktree detached, ngoài cây code (gitignored)
  └─ commit --amend (đúng 1 commit) → git push --force-with-lease origin <sha>:gh-pages
```

- `web/index.html`, `style.css`, `app.js` cố định, không build step. Mỗi lần chạy chỉ `data/latest.json` đổi.
- Trang tự fetch `data/latest.json?t=<now>` mỗi 5 phút, banner "Data cũ" khi quá 2× chu kỳ (`refresh_minutes` trong JSON), giờ hiển thị theo Asia/Ho_Chi_Minh. Chart: Lightweight Charts 4.2.0 từ jsDelivr (pin version + SRI).
- `gh-pages` chỉ chứa `index.html style.css app.js .nojekyll data/latest.json`; script dừng nếu có file khác. Chỉ push `refs/heads/gh-pages`, không bao giờ đụng `main`. Commit bằng `git config user.email` (phải là `@users.noreply.github.com`).
- Log: `~/Library/Logs/trading-bot-static.log` (local). Lock: `var/publish_static.lock/` (không chạy chồng).

### Chạy tay

```bash
.venv/bin/python scripts/export_static_snapshot.py          # chỉ xuất data
.venv/bin/python -m unittest tests.test_static_snapshot_privacy -v
.venv/bin/python -m http.server 8000 --directory web         # xem local: http://localhost:8000
scripts/publish_static.sh --no-push                          # thử, không push
scripts/publish_static.sh                                    # xuất + push gh-pages
```

### Bật / tắt lịch (launchd)

```bash
sed "s#/ABS/PATH/TO/Trading-bot#$PWD#g" deploy/com.tradingbot.static.plist.example \
  > ~/Library/LaunchAgents/com.tradingbot.static.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tradingbot.static.plist   # bật
launchctl kickstart -k gui/$(id -u)/com.tradingbot.static                              # chạy ngay
launchctl bootout gui/$(id -u)/com.tradingbot.static                                   # tắt
```

Mặc định 15 phút (`StartInterval` 900). Muốn khớp nhịp OI alert (:35 mỗi giờ) thì đổi sang `StartCalendarInterval` Minute 35 và `STATIC_REFRESH_MINUTES=60` (hướng dẫn trong file plist).
Nếu log báo `Operation not permitted` khi đọc `~/Documents`, cấp Full Disk Access cho `/bin/bash` (System Settings → Privacy & Security). Push dùng SSH remote `origin`, nên key phải dùng được không cần nhập passphrase (ssh-agent/Keychain).

### Xoá lịch sử local

```bash
rm -rf var/static-history/            # snapshot cũ (không bao giờ lên git)
rm -f ~/Library/Logs/trading-bot-static.log
git worktree remove --force var/gh-pages-wt   # tạo lại ở lần publish sau
```

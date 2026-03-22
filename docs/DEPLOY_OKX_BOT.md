# Đẩy bot OKX chạy tự động 24/7

**Lưu ý:** OKX **không** host code bot của bạn. Bot là script Python chạy trên **máy bạn** hoặc **VPS (server)**; nó gọi API OKX để lấy nến và đặt lệnh. Để bot chạy tự động 24/7, bạn cần một máy chạy liên tục (máy tính để bật 24/7, hoặc VPS trên mây).

---

## 1. Cách hoạt động

```
[VPS / máy của bạn]                    [OKX]
     run_okx_bot.py --interval-minutes 60
           │
           ├── GET candles ──────────────────► OKX API
           │◄──────────────────────────────── Nến 1h
           ├── Tính tín hiệu (regime + fusion)
           ├── Nếu có signal: POST place order ──► OKX API
           │◄──────────────────────────────── Order OK
           └── Sleep 60 phút → lặp lại
```

- Bot chạy **trên server của bạn**, **không** “đẩy lên OKX”.
- OKX chỉ nhận **API request** (candles, place order) từ bot.

---

## 2. Chế độ chạy lặp (daemon)

Bot hỗ trợ chạy lặp mỗi N phút:

```bash
# Chạy 1 lần rồi thoát (mặc định)
python run_okx_bot.py --symbols BTCUSDT --market swap --size-usdt 100

# Chạy mỗi 60 phút (phù hợp nến 1h) — chạy mãi đến khi tắt
python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --size-usdt 100 --interval-minutes 60
```

- **`--interval-minutes 0`** (mặc định): chạy một lần rồi thoát.
- **`--interval-minutes 60`**: mỗi 60 phút kiểm tra tín hiệu một lần, phù hợp khung nến 1h.

Để bot chạy 24/7, bạn cần giữ process này chạy liên tục: dùng **VPS + systemd** (hoặc **cron** nếu chỉ cần chạy đúng giờ).

---

## 3. Deploy lên VPS (Linux)

### 3.1. Chuẩn bị VPS

- Thuê VPS (DigitalOcean, AWS EC2, Vultr, …) — Ubuntu 22.04 LTS khuyến nghị.
- SSH vào: `ssh root@<ip>` (hoặc user có quyền sudo).

### 3.2. Cài đặt trên VPS

```bash
# Cập nhật và cài Python + git
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# Tạo user chạy bot (khuyến nghị, không chạy bằng root)
sudo useradd -m -s /bin/bash botokx
sudo su - botokx

# Clone repo (hoặc upload code bằng scp/rsync)
git clone <url-repo-cua-ban> Trading-bot
cd Trading-bot

# Virtual env và dependency
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.3. Cấu hình .env trên VPS

```bash
# Vẫn trong thư mục Trading-bot, user botokx
nano .env
```

Điền (không commit file này):

```env
OKX_API_KEY=...
OKX_SECRET_KEY=...
OKX_PASSPHRASE=...
# OKX_DEMO=1   # Bỏ comment nếu dùng tài khoản Demo
```

Lưu và thoát.

### 3.4. Chạy bằng systemd (tự chạy khi boot, restart khi lỗi)

Tạo file service (chạy với user `botokx`, path điều chỉnh theo thư mục thật):

```bash
sudo nano /etc/systemd/system/okx-bot.service
```

Nội dung (sửa `User`, `WorkingDirectory`, `ExecStart` cho đúng):

```ini
[Unit]
Description=OKX Trading Bot (regime + fusion)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botokx
WorkingDirectory=/home/botokx/Trading-bot
Environment=PATH=/home/botokx/Trading-bot/.venv/bin:/usr/bin
ExecStart=/home/botokx/Trading-bot/.venv/bin/python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --size-usdt 100 --interval-minutes 60
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

Kích hoạt và chạy:

```bash
sudo systemctl daemon-reload
sudo systemctl enable okx-bot
sudo systemctl start okx-bot
sudo systemctl status okx-bot
```

Xem log:

```bash
sudo journalctl -u okx-bot -f
```

Dừng bot:

```bash
sudo systemctl stop okx-bot
```

### 3.5. Cách khác: cron (chạy đúng phút mỗi giờ)

Nếu bạn muốn chạy **đúng 1 lần mỗi giờ** (ví dụ phút 5):

```bash
crontab -u botokx -e
```

Thêm dòng (chạy lúc phút 5 mỗi giờ):

```
5 * * * * cd /home/botokx/Trading-bot && .venv/bin/python run_okx_bot.py --symbols BTCUSDT,ETHUSDT --market swap --size-usdt 100 >> /home/botokx/Trading-bot/logs/cron.log 2>&1
```

Tạo thư mục log: `mkdir -p /home/botokx/Trading-bot/logs`.

---

## 4. Checklist trước khi chạy thật

| Việc | Ghi chú |
|------|--------|
| Thử `--paper` trên máy local | `run_okx_bot.py ... --paper` |
| Chạy thử `--interval-minutes 1` vài chu kỳ | Xem log có lỗi không |
| .env trên VPS không commit lên git | Kiểm tra `.gitignore` có `.env` |
| API key OKX chỉ bật Trade + Read | Không cần Withdraw cho bot |
| Size nhỏ lúc đầu | Ví dụ `--size-usdt 50` |

---

## 5. Tóm tắt

- **OKX không chạy bot giúp bạn** — bot chạy trên máy/VPS của bạn, gọi API OKX.
- **Chạy tự động 24/7:** dùng `--interval-minutes 60` và cho process chạy trong **systemd** (hoặc cron) trên VPS.
- File systemd mẫu: **`deploy/okx-bot.service.example`** — copy vào `/etc/systemd/system/okx-bot.service` và sửa `User`, `WorkingDirectory`, `ExecStart` cho đúng path trên VPS.

# Lambda: TradingView webhook → OKX

Luồng: **TradingView Alert (Webhook)** → **Lambda Function URL** (HTTPS) → **OKX API** (swap USDT).

## 1. Chuẩn bị

- Tài khoản AWS, quyền tạo Lambda + Function URL.
- OKX: API Key + Secret + **Passphrase**, quyền trade (swap).
- TradingView: gói có **Webhook** trong alert.
- Chuỗi bí mật ngẫu nhiên dài cho `TV_WEBHOOK_SECRET`.

## 2. Đóng gói deployment zip

Trên máy có Python 3.11+ (nên trùng **runtime** Lambda, ví dụ `python3.11`):

```bash
cd Trading-bot/botdown/lambda
rm -rf package deployment.zip
mkdir -p package
pip install -r requirements.txt -t package --platform manylinux2014_x86_64 --python-version 3.11 --only-binary=:all: 2>/dev/null \
  || pip install -r requirements.txt -t package
cp lambda_function.py package/
cd package && zip -r ../deployment.zip . && cd ..
```

Nếu `zip` quá lớn (>50MB) hoặc lỗi kiến trúc, dùng **Lambda container image** hoặc build trên **Amazon Linux 2** / **CloudShell**.

Giới hạn tham khảo: zip upload trực tiếp ~50MB; unzipped ~250MB.

## 3. Tạo Lambda (Console)

1. **Lambda** → Create function → Author from scratch  
   - Runtime: **Python 3.11** (hoặc 3.12 nếu bạn cài package cho đúng version).
2. **Upload** `deployment.zip`: Code → Upload from → .zip file.
3. **Handler**: `lambda_function.lambda_handler`
4. **Timeout**: 30 s (đủ cho cold start + OKX).
5. **Memory**: 256 MB trở lên.

## 4. Biến môi trường

Configuration → Environment variables:

| Key | Ví dụ |
|-----|--------|
| `TV_WEBHOOK_SECRET` | chuỗi bí mật |
| `OKX_API_KEY` | |
| `OKX_API_SECRET` | |
| `OKX_API_PASSPHRASE` | |
| `OKX_TDMODE` | `cross` hoặc `isolated` |
| `OKX_SYMBOL` | `BTC/USDT:USDT` |
| `OKX_NOTIONAL_USD` | `100` |
| `OKX_LEVERAGE` | `1` |

**Không** gắn VPC (trừ khi bạn biết cần NAT) — mặc định Lambda ra internet được, gọi OKX OK.

## 5. Function URL

1. Lambda → **Configuration** → **Function URL** → Create.  
2. Auth: **NONE** (public URL) — bảo vệ bằng `TV_WEBHOOK_SECRET` trên query hoặc JSON.  
   Hoặc dùng **IAM** nếu bạn có proxy ký request (TradingView không ký IAM).
3. Copy URL, dạng:  
   `https://xxxx.lambda-url.ap-southeast-1.on.aws/`

## 6. TradingView

**Webhook URL** (ví dụ):

```
https://xxxx.lambda-url....on.aws/?secret=YOUR_TV_WEBHOOK_SECRET
```

**Message** (JSON):

```json
{"cmd":"long"}
```

hoặc `short`, `close`. Nếu không gắn `secret` trên URL:

```json
{"secret":"YOUR_TV_WEBHOOK_SECRET","cmd":"long"}
```

Alert từ indicator Pine: dùng `alertcondition` với message `{"cmd":"long"}`.

## 7. Kiểm tra

Browser hoặc curl (GET ping):

```bash
curl "https://YOUR_FUNCTION_URL/"
```

Kỳ vọng JSON có `"ping":"tv-okx-lambda"`.

POST thử (thay secret):

```bash
curl -X POST "https://YOUR_FUNCTION_URL/?secret=YOUR_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"cmd":"close"}'
```

## 8. Chi phí & lưu ý

- Vài trăm webhook/tháng: thường nằm trong free tier hoặc vài cent.  
- **Cold start**: lần đầu sau idle có thể ~1–3s; TradingView thường chấp nhận.  
- **Bảo mật**: secret mạnh, không commit URL/secret lên git; có thể rotate key OKX định kỳ.  
- **Hedge / two-way** trên OKX: handler giả định **net một chiều**; nếu lỗi, cần chỉnh `fetch_positions` / `posSide`.

## 9. IaC (tuỳ chọn)

Có thể tái tạo bằng **SAM** / **Terraform** / **CDK** — bản README này chỉ mô tả console cho nhanh.

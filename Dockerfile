# Trading-bot: Binance crawler + macro/regime strategy + dashboard
# Python 3.12 slim
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (excluding .dockerignore entries)
COPY . .

# Dashboard listens on 0.0.0.0 so host can access; default port 5000
ENV HOST=0.0.0.0
ENV PORT=5000
EXPOSE 5000

# Default: run dashboard. Override for crawler/telegram/backtest:
#   docker run ... python crawl_binance_klines.py --market-type spot --symbols BTCUSDT ...
#   docker run ... python run_telegram_signal.py
#   docker run ... python run_backtest.py
CMD ["python", "-c", "from dashboard.app import app; import os; app.run(host=os.environ.get('HOST','0.0.0.0'), port=int(os.environ.get('PORT','5000')), debug=False)"]

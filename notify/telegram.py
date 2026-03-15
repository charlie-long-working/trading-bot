"""
Gửi tin nhắn lên Telegram qua Bot API.

Cấu hình: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (trong .env hoặc môi trường).
- Tạo bot: @BotFather -> /newbot -> lấy token.
- Lấy chat_id: gửi /start cho bot, mở https://api.telegram.org/bot<TOKEN>/getUpdates.
"""

import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from dotenv import load_dotenv
    # Load .env từ thư mục project (cấp trên notify/)
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

import requests


def _get_config() -> tuple[Optional[str], Optional[str]]:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    return token or None, chat_id or None


def send_message(
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Gửi tin nhắn tới nhóm/chat Telegram.
    Returns (True, None) nếu thành công, (False, "lý do") nếu thất bại.
    """
    token, chat_id = _get_config()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN chưa set trong .env"
    if not chat_id:
        return False, "TELEGRAM_CHAT_ID chưa set trong .env"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            body = r.text
            try:
                j = r.json()
                body = j.get("description", body)
            except Exception:
                pass
            return False, f"Telegram API: {r.status_code} - {body}"
        return True, None
    except Exception as e:
        return False, str(e)

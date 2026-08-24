import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BINGX_API_KEY = os.getenv("BINGX_API_KEY", "")
    BINGX_SECRET_KEY = os.getenv("BINGX_SECRET_KEY", "")
    BINGX_BASE_URL = os.getenv("BINGX_BASE_URL", "https://open-api.bingx.com").rstrip("/")
    
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    _allowed_users_str = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    TELEGRAM_ALLOWED_USER_IDS = [
        int(uid.strip()) for uid in _allowed_users_str.split(",") if uid.strip().isdigit()
    ]
    
    DEFAULT_SPLIT_COUNT = int(os.getenv("DEFAULT_SPLIT_COUNT", "10"))
    DEFAULT_MARGIN_TYPE = os.getenv("DEFAULT_MARGIN_TYPE", "ISOLATED").upper()

# Dynamic runtime config
current_config = {
    "split_count": Config.DEFAULT_SPLIT_COUNT,  # e.g., 10, 20, 30
    "margin_type": Config.DEFAULT_MARGIN_TYPE,  # ISOLATED or CROSSED
    "total_trade_amount": None,  # None = use account balance %, float = fixed total USDT margin base
}

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
    
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    _gemini_models_raw = os.getenv("GEMINI_MODELS", os.getenv("GEMINI_MODEL", "gemini-3.6-flash,gemini-2.5-flash,gemini-1.5-flash"))
    GEMINI_MODELS = [m.strip() for m in _gemini_models_raw.split(",") if m.strip()]
    
    DEFAULT_SPLIT_COUNT = int(os.getenv("DEFAULT_SPLIT_COUNT", "10"))
    DEFAULT_MARGIN_TYPE = os.getenv("DEFAULT_MARGIN_TYPE", "ISOLATED").upper()

# Dynamic runtime config
current_config = {
    "split_count": Config.DEFAULT_SPLIT_COUNT,  # e.g., 10, 20, 30
    "margin_type": Config.DEFAULT_MARGIN_TYPE,  # ISOLATED or CROSSED
    "total_trade_amount": None,  # None = use account balance %, float = fixed total USDT margin base
    "gemini_models": list(Config.GEMINI_MODELS),  # Dynamic list of models to try in order
}

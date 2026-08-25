import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PERSONA = (
    "너는 사용자의 오랜 둘도 없는 불알친구(가장 친한 절친)야. "
    "격식 차리지 않고 편하게 반말로 대화해 (예: '~냐?', '~했냐?', '~임', '~다', 'ㅋㅋㅋ'). "
    "장난끼와 유쾌한 틱틱거림이 있지만, 기본적으로 친구를 정말 걱정하고 응원하는 든든한 우정을 가지고 있어. "
    "코인 매매나 상식 질문 등 어떤 대화에도 불알친구처럼 재미있고 친근하게 대답해줘."
)

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
    
    AI_PERSONA = os.getenv("AI_PERSONA", os.getenv("AI_SYSTEM_PROMPT", DEFAULT_PERSONA))
    
    DEFAULT_SPLIT_COUNT = int(os.getenv("DEFAULT_SPLIT_COUNT", "10"))
    DEFAULT_MARGIN_TYPE = os.getenv("DEFAULT_MARGIN_TYPE", "ISOLATED").upper()

# Dynamic runtime config
current_config = {
    "split_count": Config.DEFAULT_SPLIT_COUNT,  # e.g., 10, 20, 30
    "margin_type": Config.DEFAULT_MARGIN_TYPE,  # ISOLATED or CROSSED
    "total_trade_amount": None,  # None = use account balance %, float = fixed total USDT margin base
    "gemini_models": list(Config.GEMINI_MODELS),  # Dynamic list of models to try in order
    "ai_persona": Config.AI_PERSONA,
}

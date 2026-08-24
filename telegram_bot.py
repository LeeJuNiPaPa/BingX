import re
import logging
import asyncio
import datetime
import requests
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from config import Config, current_config
from parser import parse_signal_text, TradeSignal
from trader import OrderEngine

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

engine = OrderEngine()

def detect_price_query(text: str) -> Optional[str]:
    coin_map = {
        "비트코인": "BTC-USDT", "비트": "BTC-USDT", "BTC": "BTC-USDT", "BITCOIN": "BTC-USDT",
        "이더리움": "ETH-USDT", "이더": "ETH-USDT", "ETH": "ETH-USDT", "ETHEREUM": "ETH-USDT",
        "솔라나": "SOL-USDT", "솔": "SOL-USDT", "SOL": "SOL-USDT", "SOLANA": "SOL-USDT",
        "리플": "XRP-USDT", "XRP": "XRP-USDT", "RIPPLE": "XRP-USDT",
        "도지": "DOGE-USDT", "DOGE": "DOGE-USDT", "DOGECOIN": "DOGE-USDT",
        "에이다": "ADA-USDT", "ADA": "ADA-USDT",
        "수이": "SUI-USDT", "SUI": "SUI-USDT",
        "아발란체": "AVAX-USDT", "AVAX": "AVAX-USDT",
        "체인링크": "LINK-USDT", "LINK": "LINK-USDT",
        "앱토스": "APT-USDT", "APT": "APT-USDT",
    }
    keywords = ["얼마", "시세", "가격", "usdt", "USDT", "price", "몇"]
    if any(kw in text.lower() for kw in keywords):
        for name, sym in coin_map.items():
            if re.search(r'\b' + re.escape(name) + r'\b', text, re.IGNORECASE) or name.lower() in text.lower():
                return sym
    return None

def format_ticker_response(symbol: str, ticker_data: dict) -> str:
    if ticker_data.get("code") == 0 and "data" in ticker_data:
        data = ticker_data["data"]
        last_price = float(data.get("lastPrice", 0))
        change_pct = float(data.get("priceChangePercent", 0))
        high_p = float(data.get("highPrice", 0))
        low_p = float(data.get("lowPrice", 0))
        
        coin_name = symbol.split("-")[0]
        emoji = "🟢" if change_pct >= 0 else "🔴"
        sign = "+" if change_pct >= 0 else ""
        
        return (
            f"💎 **{symbol} 실시간 시세 (BingX)**\n\n"
            f"• **현재가**: **{last_price:,.2f} USDT** (1 {coin_name} ≈ `{last_price:,.2f}` USDT)\n"
            f"• **24시간 변동률**: {sign}{change_pct:.2f}% {emoji}\n"
            f"• **24시간 고가**: {high_p:,.2f} USDT\n"
            f"• **24시간 저가**: {low_p:,.2f} USDT"
        )
    return f"⚠️ {symbol} 시세 정보를 조회할 수 없습니다."

def answer_general_question(text: str) -> str:
    cleaned = text.strip()

    # 1. Optional OpenAI API call if key configured
    if Config.OPENAI_API_KEY:
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {Config.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a friendly Telegram AI assistant. Answer concisely and accurately in Korean with appropriate emojis."},
                        {"role": "user", "content": cleaned}
                    ],
                    "max_tokens": 500
                },
                timeout=10
            ).json()
            if "choices" in resp and resp["choices"]:
                return resp["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"OpenAI API call error: {e}")

    # 2. Optional Gemini API call if key configured
    if Config.GEMINI_API_KEY:
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={Config.GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": cleaned}]}]
                },
                timeout=10
            ).json()
            if "candidates" in resp and resp["candidates"]:
                return resp["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning(f"Gemini API call error: {e}")

    # 3. Built-in Knowledge Base Engine
    capitals = {
        "대한민국": "서울(Seoul) 🇰🇷",
        "한국": "서울(Seoul) 🇰🇷",
        "미국": "워싱턴 D.C.(Washington, D.C.) 🇺🇸",
        "일본": "도쿄(Tokyo) 🇯🇵",
        "중국": "베이징(Beijing) 🇨🇳",
        "영국": "런던(London) 🇬🇧",
        "프랑스": "파리(Paris) 🇫🇷",
        "독일": "베를린(Berlin) 🇩🇪",
        "베트남": "하노이(Hanoi) 🇻🇳",
        "캐나다": "오타와(Ottawa) 🇨🇦",
        "호주": "캔버라(Canberra) 🇦🇺",
        "이탈리아": "로마(Rome) 🇮🇹",
        "스페인": "마드리드(Madrid) 🇪🇸",
    }
    if "수도" in cleaned:
        for country, cap in capitals.items():
            if country in cleaned:
                return f"📍 **{country}의 수도는 '{cap}'입니다.**"
        return "🗺️ **수도 질문 안내**: '대한민국 수도', '미국 수도' 처럼 국가명을 포함하여 물어보시면 수도를 알려드립니다!"

    # Greetings
    if re.search(r'안녕|반가|하이|hello|hi\b', cleaned, re.IGNORECASE):
        return "👋 **안녕하세요!** BingX 선물 자동 매매 & 시세/대화 도우미 봇입니다. 무엇을 도와드릴까요?"

    # Bot Identity
    if re.search(r'누구|이름|너는', cleaned, re.IGNORECASE):
        return "🤖 저는 **BingX 자동 매매 & 실시간 코인 시세 / 대화 도우미 봇**입니다!"

    # Math Calculations
    math_match = re.match(r'^\s*(\d+(?:\.\d+)?)\s*([\+\-\*/])\s*(\d+(?:\.\d+)?)\s*$', cleaned)
    if math_match:
        n1 = float(math_match.group(1))
        op = math_match.group(2)
        n2 = float(math_match.group(3))
        res = n1 + n2 if op == '+' else (n1 - n2 if op == '-' else (n1 * n2 if op == '*' else (n1 / n2 if n2 != 0 else '0 나누기 불가')))
        return f"🔢 **계산 결과**: `{n1} {op} {n2} = {res}`"

    # Date / Time
    if any(kw in cleaned for kw in ["몇 시", "몇시", "오늘 날짜", "현재 시간"]):
        now_str = datetime.datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
        return f"⏰ **현재 시간**: `{now_str}`"

    # Default Fallback
    return (
        f"💬 **대화 및 사용 안내**:\n"
        f"입력해주신 내용: *\"{cleaned}\"*\n\n"
        f"💡 **이런 질문과 명령을 해보세요**:\n"
        f"• **실시간 시세 조회**: `1ETH가 몇 USDT?`, `비트코인 얼마?`, `솔라나 시세`\n"
        f"• **지식 & 대화**: `대한민국의 수도는?`, `지금 몇 시야?`, `123 + 456`\n"
        f"• **매매 시그널 전송**: `비트코인 롱 10배 1차매수...` 시그널 전송 시 분할 지정가 매매 카드가 생성됩니다.\n\n"
        f"*(💡 `.env` 파일에 `OPENAI_API_KEY` 또는 `GEMINI_API_KEY`를 설정하시면 AI의 무제한 지식 대화 기능도 활용하실 수 있습니다!)*"
    )

# Store pending signals per user_id: {user_id: TradeSignal}
pending_signals: Dict[int, TradeSignal] = {}
# Store custom amount overrides for pending signals per user_id: {user_id: Optional[float]}
pending_signal_amounts: Dict[int, Optional[float]] = {}
# Store telegram message IDs of approval cards to edit when amount is updated
pending_message_ids: Dict[int, int] = {}

def check_authorized(user_id: int) -> bool:
    if not Config.TELEGRAM_ALLOWED_USER_IDS:
        return True
    return user_id in Config.TELEGRAM_ALLOWED_USER_IDS

def get_config_keyboard():
    split_cnt = current_config["split_count"]
    margin_type = current_config["margin_type"]

    def split_btn(val):
        label = f"✅ {val}등분" if split_cnt == val else f"{val}등분"
        return InlineKeyboardButton(label, callback_data=f"set_split_{val}")

    def margin_btn(m_type):
        is_sel = margin_type == m_type
        label = f"✅ {m_type}" if is_sel else m_type
        return InlineKeyboardButton(label, callback_data=f"set_margin_{m_type}")

    keyboard = [
        [split_btn(5), split_btn(10), split_btn(20)],
        [split_btn(30), split_btn(50)],
        [margin_btn("ISOLATED"), margin_btn("CROSSED")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_config_message_text():
    trade_amt = current_config.get("total_trade_amount")
    amt_str = f"**{trade_amt:,.1f} USDT** (직접 입력 고정값)" if trade_amt else "**계좌 사용 가능 잔고 %**"
    
    return (
        "⚙️ **매매 환경 설정 (`/con` / `/config`)**\n\n"
        f"• **현재 분할 매수 개수**: **{current_config['split_count']}등분**\n"
        f"• **현재 기본 매매 금액**: {amt_str}\n"
        f"• **현재 마진 모드**: **{current_config['margin_type']}**\n"
        f"• **매매 방식**: 🛡️ 시그널 파싱 후 승인 대기 카드 표시\n\n"
        "💡 **직접 금액 설정 안내**:\n"
        "• `/con 500` -> 기본 매매 금액을 **500 USDT**로 직접 설정\n"
        "• `/con auto` -> 계좌 잔고 % 기준으로 원복\n"
        "• 시그널 메시지에 `500u` 또는 `500USDT` 입력 시 해당 시그널에 바로 적용"
    )

def get_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 계좌 잔고 조회 (/bal)", callback_data="menu_bal")],
        [InlineKeyboardButton("⚙️ 매매 환경 설정 (/con)", callback_data="menu_con")],
        [InlineKeyboardButton("ℹ️ 이용 안내 및 시그널 예시 (/help)", callback_data="menu_help")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_menu_message_text():
    return (
        "📌 **BingX 자동 매매 봇 명령어 메뉴 (`l`)**\n\n"
        "원하시는 기능을 아래 버튼으로 터치하세요:"
    )

def render_preview_card(signal: TradeSignal, user_id: int):
    bal_info = engine.client.get_balance()
    avail_margin = bal_info.get("availableMargin", 1000.0)
    split_cnt = current_config["split_count"]
    side_emoji = "🟢 LONG" if signal.position_side == "LONG" else "🔴 SHORT"

    # Base margin determination
    custom_amt = pending_signal_amounts.get(user_id)
    if custom_amt is not None:
        base_margin = custom_amt
        mode_label = f"직접 입력금액 `{custom_amt:,.1f}` USDT"
    elif signal.total_amount:
        base_margin = signal.total_amount
        mode_label = f"시그널 텍스트 감지금액 `{signal.total_amount:,.1f}` USDT"
    elif current_config.get("total_trade_amount") is not None:
        base_margin = current_config["total_trade_amount"]
        mode_label = f"설정된 기본금액 `{base_margin:,.1f}` USDT"
    else:
        base_margin = avail_margin
        mode_label = "계좌 잔고 % 기준"

    if base_margin > avail_margin and not bal_info.get("is_mock"):
        base_margin = avail_margin

    total_portion = sum(e.portion_pct for e in signal.entries)
    total_allocated_margin = base_margin * (total_portion / 100.0)
    total_position_val = total_allocated_margin * signal.leverage
    total_order_cnt = len(signal.entries) * split_cnt

    contract_info = engine.client.get_contract_info(signal.symbol)
    price_prec = contract_info.get("pricePrecision", 2)
    qty_prec = contract_info.get("quantityPrecision", 3)

    tier_details = []
    for entry in signal.entries:
        tier_margin = base_margin * (entry.portion_pct / 100.0)
        tier_pos = tier_margin * signal.leverage
        
        p_range = f"{entry.start_price:,.{price_prec}f} ~ {entry.end_price:,.{price_prec}f}" if entry.start_price != entry.end_price else f"{entry.start_price:,.{price_prec}f}"
        mid_price = (entry.start_price + entry.end_price) / 2.0
        sub_pos = tier_pos / split_cnt
        sub_qty = round(sub_pos / mid_price, qty_prec) if mid_price > 0 else 0

        tier_details.append(
            f"  ▶ **{entry.step}차 매수** (비중 {entry.portion_pct:.0f}% | 증거금 `{tier_margin:,.2f}` USDT)\n"
            f"     - 범위: `{p_range}` USDT ({split_cnt}분할)\n"
            f"     - 1건당 가격/수량: ~`{sub_pos:,.2f}` USDT"
        )

    tp_str = f"`{signal.take_profit:,.{price_prec}f}` USDT" if signal.take_profit else "대기"
    sl_str = f"`{signal.stop_loss:,.{price_prec}f}` USDT" if signal.stop_loss else "대기"

    preview_msg = (
        f"📥 **매매 시그널 분석 완료 (승인 대기 중)** ⏳\n\n"
        f"• **종목**: `{signal.symbol}`\n"
        f"• **포지션**: {side_emoji} ({signal.leverage}배 레버리지)\n"
        f"• **분할 매수 설정**: {split_cnt}등분 (총 {total_order_cnt}개 지정가 주문)\n"
        f"• **매매 금액 기준**: {mode_label}\n"
        f"• **총 예상 할당 증거금**: `{total_allocated_margin:,.2f}` USDT (포지션 가치 `{total_position_val:,.2f}` USDT)\n"
        f"• **계좌 사용 가능 잔고**: {avail_margin:,.2f} USDT\n\n"
        f"📋 **매매 내역 상세**:\n"
        + "\n".join(tier_details) + "\n\n"
        f"• **익절가**: {tp_str} | **손절가**: {sl_str}\n\n"
        f"❓ **위 매매 내역으로 BingX에 실제 주문을 전송하시겠습니까?**\n"
        f"*(금액 변경 시 USDT를 입력하시면 됩니다.)*"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ 승인 (주문 실행)", callback_data="confirm_trade"),
            InlineKeyboardButton("❌ 취소", callback_data="cancel_trade"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    return preview_msg, reply_markup

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    msg = (
        "🤖 **BingX 자연어 자동 매매 텔레그램 봇**에 오신 것을 환영합니다!\n\n"
        "🛡️ **안전 승인 매매 모드 활성화됨**:\n"
        "시그널 메시지를 전송하시면 바로 매매되지 않고, **매매 내역 상세를 미리 보여드린 후 [승인] 버튼을 누르실 때만 주문이 전송**됩니다.\n\n"
        "📌 **시그널 예시** (금액 직접 입력 지원):\n"
        "```\n"
        "비트코인 롱 10배 500u 🔼\n"
        "1차매수 76.5~77.4K 비중20%\n"
        "2차매수 74.5~75.4K 비중20%\n"
        "3차매수 72.5~73.4K 비중20%\n"
        "익절가 대기\n"
        "손절가 대기\n"
        "```\n\n"
        "⚙️ **주요 명령어 & 약어**:\n"
        "• `l` 또는 `/l` - 터치 버튼 메뉴 호출\n"
        "• `/con` 또는 `/config` - 설정 확인 및 분할 수 변경\n"
        "• `/con 500` - 기본 매매 금액을 500 USDT로 직접 설정\n"
        "• `/bal` 또는 `/balance` - BingX 선물 계좌 잔고 및 증거금 조회\n"
        "• `/help` - 도움말 보기"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_command(update, context)

async def l_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    await update.message.reply_text(
        get_menu_message_text(),
        reply_markup=get_menu_keyboard(),
        parse_mode="Markdown"
    )

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    args = context.args
    if args:
        if args[0].lower() == "auto":
            current_config["total_trade_amount"] = None
            await update.message.reply_text("✅ 기본 매매 금액 기준이 **계좌 잔고 %**로 변경되었습니다.", parse_mode="Markdown")
            return
        elif args[0].replace(",", "").replace(".", "").isdigit():
            val = float(args[0].replace(",", ""))
            current_config["total_trade_amount"] = val
            await update.message.reply_text(f"✅ 기본 매매 금액이 **{val:,.1f} USDT**로 지정되었습니다.", parse_mode="Markdown")
            return

    await update.message.reply_text(
        get_config_message_text(),
        reply_markup=get_config_keyboard(),
        parse_mode="Markdown"
    )

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    bal = engine.client.get_balance()
    mode_str = " (모의 시뮬레이션)" if bal.get("is_mock") else ""
    msg = (
        f"💰 **BingX 선물 계좌 잔고 리포트{mode_str}**\n\n"
        f"• **총 잔고 (Equity)**: {bal.get('equity', 0):,.2f} USDT\n"
        f"• **사용 가능 증거금 (Available Margin)**: {bal.get('availableMargin', 0):,.2f} USDT\n"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_signal_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_authorized(user_id):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        return

    text = update.message.text
    if not text:
        return

    clean_text = text.strip()
    
    # 1. Single letter 'l' command fallback
    if clean_text.lower() == "l":
        await l_command(update, context)
        return

    # 2. Check if user typed a direct amount for an existing pending signal (e.g., "500", "500u", "500usdt")
    num_match = re.match(r'^(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:USDT|usdt|u|U|\$|달러)?$', clean_text)
    if num_match and user_id in pending_signals and user_id in pending_message_ids:
        new_amt = float(num_match.group(1).replace(",", ""))
        pending_signal_amounts[user_id] = new_amt
        signal = pending_signals[user_id]
        msg_id = pending_message_ids[user_id]

        preview_msg, reply_markup = render_preview_card(signal, user_id)
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg_id,
                text=preview_msg,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✏️ 매매 금액이 **{new_amt:,.1f} USDT**로 업데이트되었습니다.", parse_mode="Markdown")
            return
        except Exception as e:
            logger.warning(f"Failed to edit pending card: {e}")

    # 3. Check for Crypto Price / Ticker Inquiry (e.g. "1ETH가 몇 USDT", "비트코인 얼마", "ETH 시세")
    sym = detect_price_query(clean_text)
    if sym and not any(kw in clean_text for kw in ["매수", "매도", "진입", "손절", "익절", "비중", "1차", "2차"]):
        ticker_res = engine.client.get_ticker(sym)
        reply = format_ticker_response(sym, ticker_res)
        await update.message.reply_text(reply, parse_mode="Markdown")
        return

    # 4. Check for Trading Signal
    is_signal = any(kw in clean_text for kw in ["차매수", "차진입", "1차", "2차", "진입가", "비중"]) or (
        ("롱" in clean_text or "숏" in clean_text or "LONG" in clean_text or "SHORT" in clean_text) and ("~" in clean_text or "K" in clean_text)
    )

    if is_signal:
        try:
            signal = parse_signal_text(clean_text)
            if signal.entries:
                pending_signals[user_id] = signal
                pending_signal_amounts[user_id] = signal.total_amount

                preview_msg, reply_markup = render_preview_card(signal, user_id)
                sent_msg = await update.message.reply_text(preview_msg, reply_markup=reply_markup, parse_mode="Markdown")
                pending_message_ids[user_id] = sent_msg.message_id
                return
        except Exception as e:
            logger.exception("Failed to process signal preview")

    # 5. General Conversation / Knowledge QA
    reply = answer_general_question(clean_text)
    await update.message.reply_text(reply, parse_mode="Markdown")

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not check_authorized(user_id):
        await query.edit_message_text("⛔ 접근 권한이 없습니다.")
        return

    data = query.data

    # 1. Main menu buttons handling
    if data == "menu_bal":
        bal = engine.client.get_balance()
        mode_str = " (모의 시뮬레이션)" if bal.get("is_mock") else ""
        msg = (
            f"💰 **BingX 선물 계좌 잔고 리포트{mode_str}**\n\n"
            f"• **총 잔고 (Equity)**: {bal.get('equity', 0):,.2f} USDT\n"
            f"• **사용 가능 증거금 (Available Margin)**: {bal.get('availableMargin', 0):,.2f} USDT\n"
        )
        await query.edit_message_text(msg, reply_markup=get_menu_keyboard(), parse_mode="Markdown")
        return

    if data == "menu_con":
        await query.edit_message_text(
            get_config_message_text(),
            reply_markup=get_config_keyboard(),
            parse_mode="Markdown"
        )
        return

    if data == "menu_help":
        msg = (
            "🤖 **BingX 자연어 자동 매매 텔레그램 봇 도움말**\n\n"
            "📌 **시그널 작성 양식 예시** (금액 직접 입력 가능):\n"
            "```\n"
            "비트코인 롱 10배 500u 🔼\n"
            "1차매수 76.5~77.4K 비중20%\n"
            "2차매수 74.5~75.4K 비중20%\n"
            "3차매수 72.5~73.4K 비중20%\n"
            "익절가 대기\n"
            "손절가 대기\n"
            "```\n\n"
            "💡 **사용법**:\n"
            "1. 시그널 메시지를 전송합니다.\n"
            "2. 봇이 매매 상세 내역 카드를 응답합니다.\n"
            "3. 금액 변경 시 `300` 또는 `300u` 라고 치시면 금액이 즉시 재계산됩니다.\n"
            "4. **[ ✅ 승인 ]** 버튼을 누르시면 BingX로 지정가 분할 주문이 전송됩니다!"
        )
        await query.edit_message_text(msg, reply_markup=get_menu_keyboard(), parse_mode="Markdown")
        return

    # 2. Config buttons handling
    if data.startswith("set_split_"):
        val = int(data.replace("set_split_", ""))
        current_config["split_count"] = val
        await query.edit_message_text(
            get_config_message_text(),
            reply_markup=get_config_keyboard(),
            parse_mode="Markdown"
        )
        return

    if data.startswith("set_margin_"):
        m_type = data.replace("set_margin_", "").upper()
        current_config["margin_type"] = m_type
        await query.edit_message_text(
            get_config_message_text(),
            reply_markup=get_config_keyboard(),
            parse_mode="Markdown"
        )
        return

    # 3. Trade confirmation / cancellation buttons handling
    if data == "cancel_trade":
        if user_id in pending_signals:
            del pending_signals[user_id]
        if user_id in pending_signal_amounts:
            del pending_signal_amounts[user_id]
        if user_id in pending_message_ids:
            del pending_message_ids[user_id]
        await query.edit_message_text("❌ **매매 주문이 취소되었습니다.**", parse_mode="Markdown")
        return

    if data == "confirm_trade":
        signal = pending_signals.get(user_id)
        if not signal:
            await query.edit_message_text("⚠️ 대기 중인 매매 시그널이 없거나 이미 처리되었습니다.")
            return

        split_cnt = current_config["split_count"]
        custom_amt = pending_signal_amounts.get(user_id)
        side_emoji = "🟢 LONG" if signal.position_side == "LONG" else "🔴 SHORT"

        await query.edit_message_text("🔄 **승인 확인됨! BingX에 주문을 전송하고 있습니다...**", parse_mode="Markdown")

        # Execute Trade
        res = engine.execute_signal(signal, custom_split_count=split_cnt, custom_total_amount=custom_amt)

        # Clear pending signal
        if user_id in pending_signals:
            del pending_signals[user_id]
        if user_id in pending_signal_amounts:
            del pending_signal_amounts[user_id]
        if user_id in pending_message_ids:
            del pending_message_ids[user_id]

        report_lines = [
            f"✅ **주문 실행 완료!**{' (모의 테스트)' if res.is_mock else ''}\n",
            f"• **종목**: `{res.symbol}` | **방향**: {side_emoji} | **레버리지**: {res.leverage}배",
            f"• **계좌 사용 가능 증거금**: {res.account_balance:,.2f} USDT",
            f"• **총 생성된 주문 수**: {sum(s.split_count for s in res.step_summaries)} 개 ({split_cnt}등분/차수)\n",
            "📋 **차수별 분할 지정가 주문 체결 상세**:"
        ]

        for s in res.step_summaries:
            first_p = s.orders[0]["price"]
            last_p = s.orders[-1]["price"]
            unit_qty = s.orders[0]["quantity"]
            report_lines.append(
                f"  ▶ **{s.step}차 매수**: {s.allocated_margin_usdt:,.2f} USDT (포지션 {s.total_position_usdt:,.2f} USDT)\n"
                f"     - 가격 범위: {first_p:,.1f} ~ {last_p:,.1f} USDT ({s.split_count}분할)\n"
                f"     - 주문 1건당 수량: {unit_qty} {res.symbol.split('-')[0]}"
            )

        if res.errors:
            report_lines.append("\n⚠️ **오류 내역**:")
            for err in res.errors:
                report_lines.append(f"  • {err}")

        await query.edit_message_text("\n".join(report_lines), parse_mode="Markdown")

def main():
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    token = Config.TELEGRAM_BOT_TOKEN
    if not token or "your_" in token:
        print("="*60)
        print("⚠️ [경고] TELEGRAM_BOT_TOKEN 이 .env 파일에 설정되지 않았습니다.")
        print("="*60)

    app = Application.builder().token(token if token and "your_" not in token else "INVALID_TOKEN").build()

    app.add_handler(CommandHandler(["start"], start_command))
    app.add_handler(CommandHandler(["help"], help_command))
    app.add_handler(CommandHandler(["l", "L"], l_command))
    app.add_handler(CommandHandler(["config", "con"], config_command))
    app.add_handler(CommandHandler(["balance", "bal"], balance_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_signal_message))
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    print("🚀 BingX Telegram Trading Bot 이 실행되었습니다. (Ctrl+C 로 종료)")
    app.run_polling()

if __name__ == "__main__":
    main()

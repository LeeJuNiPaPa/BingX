import re
import logging
import asyncio
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

    if len(clean_text) < 5:
        return

    try:
        # 3. Parse Signal
        signal = parse_signal_text(clean_text)
        
        if not signal.entries:
            await update.message.reply_text("⚠️ 메세지에서 매수 가격 범위(1차매수 등)를 찾을 수 없습니다.")
            return

        # Store pending signal for this user
        pending_signals[user_id] = signal
        pending_signal_amounts[user_id] = signal.total_amount

        preview_msg, reply_markup = render_preview_card(signal, user_id)
        sent_msg = await update.message.reply_text(preview_msg, reply_markup=reply_markup, parse_mode="Markdown")
        pending_message_ids[user_id] = sent_msg.message_id

    except Exception as e:
        logger.exception("Failed to process signal preview")
        await update.message.reply_text(f"❌ 시그널 처리 중 오류가 발생했습니다:\n`{e}`", parse_mode="Markdown")

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

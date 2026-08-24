import re
from typing import List, Optional
from pydantic import BaseModel, Field

class EntryTier(BaseModel):
    step: int
    start_price: float
    end_price: float
    portion_pct: float  # e.g. 20.0 means 20%

class TradeSignal(BaseModel):
    raw_text: str
    symbol: str  # e.g. "BTC-USDT"
    position_side: str  # "LONG" or "SHORT"
    leverage: int  # e.g. 10
    entries: List[EntryTier] = Field(default_factory=list)
    take_profit: Optional[float] = None
    stop_loss: Optional[float] = None
    total_amount: Optional[float] = None  # e.g. 500.0 USDT

SYMBOL_MAP = {
    "비트코인": "BTC-USDT",
    "비트": "BTC-USDT",
    "BTC": "BTC-USDT",
    "BITCOIN": "BTC-USDT",
    "이더리움": "ETH-USDT",
    "이더": "ETH-USDT",
    "ETH": "ETH-USDT",
    "ETHEREUM": "ETH-USDT",
    "솔라나": "SOL-USDT",
    "SOL": "SOL-USDT",
    "리플": "XRP-USDT",
    "XRP": "XRP-USDT",
    "도지": "DOGE-USDT",
    "DOGE": "DOGE-USDT",
}

def parse_price_str(price_str: str) -> float:
    """
    Parses strings like '76.5K', '76.5k', '76,500', '76500' into standard float numbers.
    """
    cleaned = price_str.strip().replace(",", "")
    has_k = False
    if cleaned.upper().endswith("K"):
        has_k = True
        cleaned = cleaned[:-1]
    
    val = float(cleaned)
    if has_k:
        val *= 1000.0
    return val

def parse_signal_text(text: str) -> TradeSignal:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        raise ValueError("Empty signal message")

    full_text = " ".join(lines)

    # 1. Symbol Detection
    symbol = None
    for kw, sym in SYMBOL_MAP.items():
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE) or kw in text:
            symbol = sym
            break

    if not symbol:
        # Fallback regex for uppercase ticker like "XAU" or "LINK-USDT"
        match_sym = re.search(r'([A-Z0-9]{2,10})(-USDT)?', full_text)
        if match_sym:
            raw_sym = match_sym.group(1).upper()
            if raw_sym not in ["LONG", "SHORT", "BUY", "SELL"]:
                symbol = f"{raw_sym}-USDT"

    if not symbol:
        symbol = "BTC-USDT"  # Default fallback if not recognized

    # 2. Position Side (LONG / SHORT)
    position_side = "LONG"
    if re.search(r'숏|SHORT|SELL|🔽|⬇️', full_text, re.IGNORECASE):
        position_side = "SHORT"
    elif re.search(r'롱|LONG|BUY|🔼|⬆️', full_text, re.IGNORECASE):
        position_side = "LONG"

    # 3. Leverage
    leverage = 10  # default
    lev_match = re.search(r'(\d+)\s*(?:배|x|X)', full_text)
    if lev_match:
        leverage = int(lev_match.group(1))

    # 4. Entry Tiers
    entries: List[EntryTier] = []
    
    # Line by line pattern for 1차매수, 2차매수...
    for line in lines:
        # Check for N차 매수 / N차 진입 / N차
        tier_match = re.search(r'(\d+)차(?:\s*매수|\s*진입)?', line)
        if tier_match:
            step = int(tier_match.group(1))
            
            # Extract portion percentage
            portion_match = re.search(r'(?:비중\s*)?(\d+(?:\.\d+)?)\s*%', line)
            portion_pct = float(portion_match.group(1)) if portion_match else 20.0
            
            # Extract price range or single price
            # e.g., 76.5~77.4K or 76.5K~77.4K or 76500~77400
            range_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?\s*[kK]?)\s*[\~～\-]\s*(\d+(?:,\d+)*(?:\.\d+)?\s*[kK]?)', line)
            if range_match:
                p1_str = range_match.group(1).strip()
                p2_str = range_match.group(2).strip()
                
                # Handle single K at the end of range, e.g. "76.5~77.4K"
                if not p1_str.upper().endswith("K") and p2_str.upper().endswith("K"):
                    p1_str += "K"

                p1 = parse_price_str(p1_str)
                p2 = parse_price_str(p2_str)
                start_price = min(p1, p2)
                end_price = max(p1, p2)
            else:
                # Single price
                single_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?\s*[kK]?)', line[tier_match.end():])
                if single_match:
                    p = parse_price_str(single_match.group(1))
                    start_price = end_price = p
                else:
                    continue

            entries.append(EntryTier(
                step=step,
                start_price=start_price,
                end_price=end_price,
                portion_pct=portion_pct
            ))

    # Sort entries by step
    entries.sort(key=lambda x: x.step)

    # 5. Take Profit (TP) & Stop Loss (SL)
    tp_price = None
    sl_price = None

    tp_match = re.search(r'(?:익절가?|TP)\s*[:=]?\s*(\d+(?:,\d+)*(?:\.\d+)?\s*[kK]?)', full_text, re.IGNORECASE)
    if tp_match and "대기" not in tp_match.group(0):
        try:
            tp_price = parse_price_str(tp_match.group(1))
        except Exception:
            pass

    sl_match = re.search(r'(?:손절가?|SL)\s*[:=]?\s*(\d+(?:,\d+)*(?:\.\d+)?\s*[kK]?)', full_text, re.IGNORECASE)
    if sl_match and "대기" not in sl_match.group(0):
        try:
            sl_price = parse_price_str(sl_match.group(1))
        except Exception:
            pass

    # 6. Total Trade Amount (USDT)
    total_amount = None
    # Catch explicit unit patterns: e.g. "500u", "500usdt", "500$", "500달러", "총금액 500", "금액 500"
    amt_match = re.search(r'(?:총\s*금액|총\s*투자금?|총\s*증거금|금액|증거금)?\s*[:=]?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:USDT|usdt|u|U|\$|달러)', full_text)
    if not amt_match:
        amt_match = re.search(r'(?:총\s*금액|총\s*투자금?|총\s*증거금|금액)\s*[:=]?\s*(\d+(?:,\d+)*(?:\.\d+)?)', full_text, re.IGNORECASE)

    if amt_match:
        try:
            val = float(amt_match.group(1).replace(",", ""))
            # Ensure extracted value is a plausible USDT margin amount, not leverage (e.g., > 0)
            if val > 0:
                total_amount = val
        except Exception:
            pass

    return TradeSignal(
        raw_text=text,
        symbol=symbol,
        position_side=position_side,
        leverage=leverage,
        entries=entries,
        take_profit=tp_price,
        stop_loss=sl_price,
        total_amount=total_amount
    )

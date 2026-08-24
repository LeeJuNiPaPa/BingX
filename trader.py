import math
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from parser import TradeSignal, EntryTier
from bingx_client import BingXClient
from config import current_config

logger = logging.getLogger(__name__)

class SplitOrderResult(BaseModel):
    step: int
    split_count: int
    allocated_margin_usdt: float
    total_position_usdt: float
    orders: List[Dict[str, Any]]

class TradeExecutionSummary(BaseModel):
    success: bool
    symbol: str
    position_side: str
    leverage: int
    split_count: int
    account_balance: float
    is_mock: bool
    step_summaries: List[SplitOrderResult]
    errors: List[str]

class OrderEngine:
    def __init__(self, client: Optional[BingXClient] = None):
        self.client = client or BingXClient()

    def execute_signal(
        self,
        signal: TradeSignal,
        custom_split_count: Optional[int] = None,
        custom_total_amount: Optional[float] = None
    ) -> TradeExecutionSummary:
        split_count = custom_split_count or current_config.get("split_count", 10)
        margin_type = current_config.get("margin_type", "ISOLATED")

        # 1. Fetch balance
        bal_info = self.client.get_balance()
        available_margin = bal_info.get("availableMargin", 1000.0)
        is_mock = bal_info.get("is_mock", True)

        # Base margin calculation
        if signal.total_amount:
            base_margin = signal.total_amount
        elif custom_total_amount is not None:
            base_margin = custom_total_amount
        elif current_config.get("total_trade_amount") is not None:
            base_margin = current_config["total_trade_amount"]
        else:
            base_margin = available_margin

        if not is_mock and base_margin > available_margin:
            base_margin = available_margin

        errors = []
        step_summaries = []

        # 2. Set Margin Type & Leverage
        self.client.set_margin_type(signal.symbol, margin_type)
        self.client.set_leverage(signal.symbol, signal.leverage, signal.position_side)

        # 3. Contract Precision Info
        contract_info = self.client.get_contract_info(signal.symbol)
        price_prec = contract_info.get("pricePrecision", 2)
        qty_prec = contract_info.get("quantityPrecision", 3)
        min_qty = contract_info.get("minQuantity", 0.001)

        side = "BUY" if signal.position_side == "LONG" else "SELL"

        # 4. Process Entry Tiers
        for entry in signal.entries:
            allocated_margin = base_margin * (entry.portion_pct / 100.0)
            total_pos_value = allocated_margin * signal.leverage
            
            sub_orders = []
            
            if entry.start_price == entry.end_price or split_count <= 1:
                # Single limit order
                price = round(entry.start_price, price_prec)
                raw_qty = total_pos_value / price
                qty = max(round(raw_qty, qty_prec), min_qty)
                
                resp = self.client.place_order(
                    symbol=signal.symbol,
                    order_type="LIMIT",
                    side=side,
                    position_side=signal.position_side,
                    price=price,
                    quantity=qty,
                    take_profit=signal.take_profit,
                    stop_loss=signal.stop_loss
                )
                
                sub_orders.append({
                    "price": price,
                    "quantity": qty,
                    "order_response": resp
                })
            else:
                # N-split grid limit orders
                n = split_count
                price_step = (entry.end_price - entry.start_price) / (n - 1)
                sub_pos_value = total_pos_value / n
                
                for i in range(n):
                    calc_price = entry.start_price + (i * price_step)
                    price = round(calc_price, price_prec)
                    raw_qty = sub_pos_value / price
                    qty = round(raw_qty, qty_prec)
                    if qty < min_qty:
                        qty = min_qty
                    
                    resp = self.client.place_order(
                        symbol=signal.symbol,
                        order_type="LIMIT",
                        side=side,
                        position_side=signal.position_side,
                        price=price,
                        quantity=qty,
                        take_profit=signal.take_profit if i == n - 1 else None,  # Attach TP/SL to last order or overall
                        stop_loss=signal.stop_loss if i == 0 else None
                    )
                    
                    sub_orders.append({
                        "grid_index": i + 1,
                        "price": price,
                        "quantity": qty,
                        "order_response": resp
                    })

            step_summaries.append(SplitOrderResult(
                step=entry.step,
                split_count=len(sub_orders),
                allocated_margin_usdt=round(allocated_margin, 2),
                total_position_usdt=round(total_pos_value, 2),
                orders=sub_orders
            ))

        return TradeExecutionSummary(
            success=len(errors) == 0,
            symbol=signal.symbol,
            position_side=signal.position_side,
            leverage=signal.leverage,
            split_count=split_count,
            account_balance=round(available_margin, 2),
            is_mock=is_mock,
            step_summaries=step_summaries,
            errors=errors
        )

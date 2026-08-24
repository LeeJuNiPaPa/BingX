import time
import hmac
import hashlib
import json
import requests
import logging
from typing import Dict, Any, Optional, List
from config import Config

logger = logging.getLogger(__name__)

class BingXClient:
    def __init__(self, api_key: str = "", secret_key: str = "", base_url: str = ""):
        self.api_key = api_key or Config.BINGX_API_KEY
        self.secret_key = secret_key or Config.BINGX_SECRET_KEY
        self.base_url = (base_url or Config.BINGX_BASE_URL).rstrip("/")
        self.is_configured = bool(self.api_key and self.secret_key and "your_" not in self.api_key)

    def _sign(self, params: Dict[str, Any]) -> str:
        """Generates HMAC-SHA256 signature for BingX API parameters."""
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_configured:
            logger.warning("BingX API key/secret not configured. Running in mock/simulation mode.")
            return {"code": 0, "msg": "Simulation mode (API key missing)", "data": {}}

        if params is None:
            params = {}

        params["timestamp"] = int(time.time() * 1000)
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        full_url = f"{self.base_url}{path}?{query_string}&signature={signature}"

        headers = {
            "X-BX-APIKEY": self.api_key
        }

        try:
            if method.upper() == "GET":
                resp = requests.get(full_url, headers=headers, timeout=10)
            elif method.upper() == "POST":
                resp = requests.post(full_url, headers=headers, timeout=10)
            elif method.upper() == "DELETE":
                resp = requests.delete(full_url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            resp_json = resp.json()
            return resp_json
        except Exception as e:
            logger.error(f"BingX API Request Error ({method} {path}): {e}")
            return {"code": -1, "msg": str(e), "data": {}}

    def get_balance(self) -> Dict[str, Any]:
        """Fetch USDT-M Swap Available Margin & Balance."""
        if not self.is_configured:
            return {"availableMargin": 1000.0, "balance": 1000.0, "equity": 1000.0, "is_mock": True}

        res = self._request("GET", "/openApi/swap/v2/user/balance")
        if res.get("code") == 0 and "data" in res:
            data = res["data"]
            # Swap balance structure
            balance_info = data.get("balance", {})
            return {
                "availableMargin": float(balance_info.get("availableMargin", balance_info.get("balance", 0))),
                "balance": float(balance_info.get("balance", 0)),
                "equity": float(balance_info.get("equity", 0)),
                "is_mock": False
            }
        else:
            logger.warning(f"Failed to fetch balance: {res.get('msg')}. Returning mock balance.")
            return {"availableMargin": 1000.0, "balance": 1000.0, "equity": 1000.0, "is_mock": True, "error": res.get("msg")}

    def set_leverage(self, symbol: str, leverage: int, position_side: str = "LONG") -> Dict[str, Any]:
        """Set leverage for symbol."""
        if not self.is_configured:
            return {"code": 0, "msg": "Mock leverage set successfully"}

        params = {
            "symbol": symbol,
            "leverage": leverage,
            "side": position_side
        }
        return self._request("POST", "/openApi/swap/v2/trade/leverage", params)

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> Dict[str, Any]:
        """Set margin type: ISOLATED or CROSSED."""
        if not self.is_configured:
            return {"code": 0, "msg": "Mock margin type set successfully"}

        params = {
            "symbol": symbol,
            "marginType": margin_type.upper()
        }
        return self._request("POST", "/openApi/swap/v2/trade/marginType", params)

    def place_order(
        self,
        symbol: str,
        order_type: str,
        side: str,  # BUY or SELL
        position_side: str,  # LONG or SHORT
        price: float,
        quantity: float,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None
    ) -> Dict[str, Any]:
        """Place limit/market order on USDT-M Swap."""
        if not self.is_configured:
            return {
                "code": 0,
                "msg": "Mock order placed successfully",
                "data": {
                    "order": {
                        "orderId": f"mock_order_{int(time.time()*1000)}",
                        "symbol": symbol,
                        "price": price,
                        "quantity": quantity,
                        "side": side,
                        "positionSide": position_side
                    }
                }
            }

        params = {
            "symbol": symbol,
            "type": order_type.upper(),  # LIMIT or MARKET
            "side": side.upper(),
            "positionSide": position_side.upper(),
            "price": str(price) if order_type.upper() == "LIMIT" else "0",
            "quantity": str(quantity)
        }

        if take_profit:
            params["takeProfit"] = json.dumps({
                "type": "TAKE_PROFIT_MARKET",
                "stopPrice": float(take_profit),
                "price": float(take_profit),
                "workingType": "MARK_PRICE"
            })
        if stop_loss:
            params["stopLoss"] = json.dumps({
                "type": "STOP_MARKET",
                "stopPrice": float(stop_loss),
                "price": float(stop_loss),
                "workingType": "MARK_PRICE"
            })

        return self._request("POST", "/openApi/swap/v2/trade/order", params)

    def get_contract_info(self, symbol: str) -> Dict[str, Any]:
        """Fetch precision & minimum order rules for contract symbol."""
        # Default safety values for common crypto pairs if API call fails or mock
        defaults = {
            "pricePrecision": 1 if "BTC" in symbol else (2 if "ETH" in symbol else 4),
            "quantityPrecision": 3 if "BTC" in symbol else (2 if "ETH" in symbol else 1),
            "minQuantity": 0.001 if "BTC" in symbol else 0.01,
        }

        if not self.is_configured:
            return defaults

        res = self._request("GET", "/openApi/swap/v2/quote/contracts")
        if res.get("code") == 0 and "data" in res:
            contracts = res["data"]
            for c in contracts:
                if c.get("symbol") == symbol:
                    return {
                        "pricePrecision": int(c.get("pricePrecision", defaults["pricePrecision"])),
                        "quantityPrecision": int(c.get("quantityPrecision", defaults["quantityPrecision"])),
                        "minQuantity": float(c.get("tradeMinQuantity", defaults["minQuantity"]))
                    }
        return defaults

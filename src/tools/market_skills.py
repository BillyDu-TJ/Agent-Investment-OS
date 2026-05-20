# market_skills.py
"""
市场数据技能封装 - 复用 MarketData 核心类

设计原则：
1. 接口原子化 - 每个函数只做一件事
2. 语义化文档 - 清晰的 docstring 供 AI 理解
3. 零异常中断 - 所有错误返回标准字典，不抛异常
"""

from typing import Dict, Any, List, Optional
import pandas as pd
from src.tools.market_data import MarketData


def _guess_target_type(symbol: str) -> str:
    if symbol.startswith("us."):
        return "us_index"
    if symbol.startswith("hk."):
        return "hk_index"
    if symbol.isdigit() and len(symbol) == 6:
        return "otc_fund"
    if symbol in {"sh000001", "sh000300", "sz399006"}:
        return "index"
    return "stock"


def _ensure_symbol_in_targets(market_data: MarketData, symbol: str) -> None:
    existing = {item.get("symbol") for item in market_data.TARGETS}
    if symbol in existing:
        return
    market_data.update_targets(
        [{"name": symbol, "symbol": symbol, "type": _guess_target_type(symbol)}]
    )


def _fetch_single_asset(market_data: MarketData, symbol: str) -> Optional[Dict[str, Any]]:
    target_type = _guess_target_type(symbol)
    if target_type == "hk_index":
        return None
    if target_type == "us_index":
        normalized = symbol.strip()
        if normalized.lower().startswith("us."):
            normalized = "us." + normalized.split(".", 1)[1].upper()
        return market_data.get_us_data_from_tencent(normalized, normalized)
    if target_type == "otc_fund":
        return market_data.get_otc_fund_data(symbol, symbol)
    if target_type == "index":
        return market_data.get_data_from_tencent(symbol, symbol, "index")
    return market_data.get_data_from_tencent(symbol, symbol, "stock")


def fetch_realtime_price(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取指定金融标的的最新实时价格
    
    【适用场景】
    - ReAct AI 需要查询当前价格以计算盈亏
    - 决策前获取最新行情
    
    【能力边界】
    - 支持 A 股、港股、美股指数、场外基金
    - 价格数据可能有 15 分钟延迟（取决于数据源）
    
    【参数】
    - symbol (str, 必填): 金融标的代码
      格式示例：'sh513130', '016452', 'us.NDX', '600519'
    
    【返回】
    - status: "success" | "error"
    - data: {"symbol": str, "price": float, "change_pct": float} | None
    - message: str (仅在 error 时存在)
    """
    try:
        symbol = params.get("symbol")
        if not symbol:
            return {"status": "error", "message": "Missing required parameter: symbol"}

        symbol = str(symbol).strip()
        if symbol.lower().startswith("hk."):
            return {
                "status": "error",
                "message": "暂不支持港股指数代码，请使用对应 ETF 或 A 股/美股指数代码。",
            }
        
        market_data = MarketData()
        asset = _fetch_single_asset(market_data, symbol)
        if not asset:
            return {"status": "error", "message": f"Symbol {symbol} not found or unsupported"}

        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "price": asset.get("close"),
                "change_pct": asset.get("change_pct"),
                "update_time": asset.get("date"),
            },
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to fetch price: {str(e)}"}


def get_technical_indicators(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取指定金融标的的技术指标
    
    【适用场景】
    - ReAct AI 需要技术面分析以辅助决策
    - 判断超买超卖、趋势强度
    
    【能力边界】
    - 仅支持有历史 K 线数据的标的
    - 场外基金技术指标可能不准确（净值更新频率低）
    
    【参数】
    - symbol (str, 必填): 金融标的代码
    - indicators (List[str], 可选): 指标列表
      支持：['ma5', 'ma20', 'rsi', 'macd', 'boll', 'kdj', 'atr']
      默认：['ma5', 'ma20', 'rsi']
    
    【返回】
    - status: "success" | "error"
    - data: {指标名：数值} | None
    - message: str (仅在 error 时存在)
    """
    try:
        symbol = params.get("symbol")
        if not symbol:
            return {"status": "error", "message": "Missing required parameter: symbol"}

        symbol = str(symbol).strip()
        if symbol.lower().startswith("hk."):
            return {
                "status": "error",
                "message": "暂不支持港股指数代码，请使用对应 ETF 或 A 股/美股指数代码。",
            }
        
        indicators = params.get("indicators", ["ma5", "ma20", "rsi"])

        market_data = MarketData()
        asset = _fetch_single_asset(market_data, symbol)
        if not asset:
            return {"status": "error", "message": f"Symbol {symbol} not found or unsupported"}

        raw_indicators = asset.get("indicators")
        if not isinstance(raw_indicators, dict):
            return {"status": "error", "message": "Indicators payload is not a dict"}

        mapping = {
            "ma20": "MA20",
            "ma60": "MA60",
            "ma200": "MA200",
            "rsi": "RSI",
            "macd": "MACD",
            "boll": "Bollinger",
            "kdj": "K",
            "atr": "ATR",
            "vol_ratio": "Vol_Ratio",
        }

        data: Dict[str, Any] = {}
        for name in indicators:
            key = str(name).lower()
            actual = mapping.get(key)
            if not actual:
                data[name] = "N/A"
                continue
            data[name] = raw_indicators.get(actual, "N/A")

        return {"status": "success", "data": data}
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to calculate indicators: {str(e)}"}


def get_volume_analysis(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取指定金融标的的量能异动分析
    
    【适用场景】
    - ReAct AI 需要判断资金流入流出
    - 识别放量突破或缩量回调
    
    【能力边界】
    - 仅支持有成交量数据的标的
    - 场外基金无成交量数据，返回 skipped
    
    【参数】
    - symbol (str, 必填): 金融标的代码
    
    【返回】
    - status: "success" | "skipped" | "error"
    - data: {"volume_ratio": float, "signal": str} | None
    - message: str (仅在 error/skipped 时存在)
    """
    try:
        symbol = params.get("symbol")
        if not symbol:
            return {"status": "error", "message": "Missing required parameter: symbol"}

        symbol = str(symbol).strip()
        if symbol.lower().startswith("hk."):
            return {
                "status": "error",
                "message": "暂不支持港股指数代码，请使用对应 ETF 或 A 股/美股指数代码。",
            }
        
        market_data = MarketData()
        asset = _fetch_single_asset(market_data, symbol)
        if not asset:
            return {"status": "error", "message": f"Symbol {symbol} not found or unsupported"}

        df = market_data.last_dfs.get(symbol)
        if df is None or df.empty:
            return {"status": "skipped", "message": "No volume data available"}

        latest = df.iloc[-1]
        vol_ratio = latest.get("Vol_Ratio")
        if vol_ratio is None or (isinstance(vol_ratio, float) and pd.isna(vol_ratio)):
            return {"status": "skipped", "message": "Vol_Ratio not available"}

        signal = "正常"
        if float(vol_ratio) >= 1.5:
            signal = "放量"
        elif float(vol_ratio) <= 0.7:
            signal = "缩量"

        return {
            "status": "success",
            "data": {"volume_ratio": round(float(vol_ratio), 2), "signal": signal},
        }
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to analyze volume: {str(e)}"}
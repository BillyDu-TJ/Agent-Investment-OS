# market_skills.py
"""
市场数据技能封装 - 复用 MarketData 核心类

设计原则：
1. 接口原子化 - 每个函数只做一件事
2. 语义化文档 - 清晰的 docstring 供 AI 理解
3. 零异常中断 - 所有错误返回标准字典，不抛异常
"""

from typing import Dict, Any, List, Optional
from src.tools.market_data import MarketData


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
        
        market_data = MarketData()
        summary = market_data.get_market_summary()
        
        # 在所有资产类别中查找指定 symbol
        all_assets = (
            summary.get("indices", []) +
            summary.get("us_indices", []) +
            summary.get("funds", []) +
            summary.get("stocks", [])
        )
        
        for asset in all_assets:
            if asset.get("symbol") == symbol:
                return {
                    "status": "success",
                    "data": {
                        "symbol": symbol,
                        "price": asset.get("close"),
                        "change_pct": asset.get("change_pct"),
                        "update_time": asset.get("update_time")
                    }
                }
        
        return {"status": "error", "message": f"Symbol {symbol} not found in market summary"}
        
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
        
        indicators = params.get("indicators", ["ma5", "ma20", "rsi"])
        
        market_data = MarketData()
        result = market_data.calculate_technical_indicators(symbol, indicators)
        
        if result.get("status") == "success":
            return {"status": "success", "data": result.get("data")}
        else:
            return {"status": "error", "message": result.get("message", "Unknown error")}
            
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
        
        market_data = MarketData()
        result = market_data.analyze_volume(symbol)
        
        if result.get("status") == "success":
            return {"status": "success", "data": result.get("data")}
        elif result.get("status") == "skipped":
            return {"status": "skipped", "message": result.get("message")}
        else:
            return {"status": "error", "message": result.get("message", "Unknown error")}
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to analyze volume: {str(e)}"}
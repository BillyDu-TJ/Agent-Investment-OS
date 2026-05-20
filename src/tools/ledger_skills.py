# ledger_skills.py
"""
账本与交易技能封装 - 复用 PortfolioManager 核心类

设计原则：
1. 接口原子化 - 每个函数只做一件事
2. 语义化文档 - 清晰的 docstring 供 AI 理解
3. 零异常中断 - 所有错误返回标准字典，不抛异常
"""

from typing import Dict, Any, List, Optional
import csv
from pathlib import Path
from src.tools.portfolio_manager import PortfolioManager
from src.tools.market_data import MarketData
from src.tools.transaction import TransactionManager

ROOT_DIR = Path(__file__).resolve().parents[2]
TRADE_PATH = ROOT_DIR / "data" / "trade_history.csv"


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_trade_rows() -> List[Dict[str, Any]]:
    if not TRADE_PATH.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with TRADE_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(row)
    return rows


def get_current_portfolio(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取当前持仓组合的完整状态
    
    【适用场景】
    - ReAct AI 需要了解当前持仓以做出调仓决策
    - 计算总盈亏、仓位比例
    
    【能力边界】
    - 返回数据包含用户原始投资理由（reason 字段）
    - 市值计算基于最新行情，可能有延迟
    
    【参数】
    - 无必填参数
    
    【返回】
    - status: "success" | "error"
    - data: {
        "cash": float,
        "total_value": float,
        "positions": [{"symbol": str, "shares": float, "cost": float, ...}],
        "summary": {...}
      } | None
    - message: str (仅在 error 时存在)
    """
    try:
        # 先获取市场数据
        market_data = MarketData()
        summary = market_data.get_market_summary()
        market_summaries = summary.get("indices", [])
        print(type(market_summaries), market_summaries)

        portfolio_manager = PortfolioManager()
        portfolio_status = portfolio_manager.get_portfolio_status(market_summaries)
        print(type(portfolio_status), portfolio_status)

        if not isinstance(portfolio_status, dict):
            return {"status": "error", "message": "Portfolio payload is not a dict"}

        return {"status": "success", "data": portfolio_status}
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to get portfolio: {str(e)}"}


def execute_trade(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行虚拟交易（更新持仓记录）
    
    【适用场景】
    - ReAct AI 做出买卖决策后执行
    - 记录交易流水和投资理由
    
    【能力边界】
    - ⚠️ 此操作会修改 portfolio.yaml 和 trade_history.csv
    - 建议 AI 在执行前确认交易逻辑
    
    【参数】
    - action (str, 必填): "buy" | "sell"
    - symbol (str, 必填): 金融标的代码
    - shares (float, 必填): 交易数量/份额
    - price (float, 必填): 成交价格
    - reason (str, 必填): 交易理由（重要！用于后续复盘）
    
    【返回】
    - status: "success" | "error"
    - data: {"action": str, "symbol": str, "shares": float, ...} | None
    - message: str (仅在 error 时存在)
    """
    try:
        action = params.get("action")
        symbol = params.get("symbol")
        shares = params.get("shares")
        price = params.get("price")
        reason = params.get("reason")
        
        # 参数验证
        if not all([action, symbol, shares, price, reason]):
            missing = []
            if not action: missing.append("action")
            if not symbol: missing.append("symbol")
            if not shares: missing.append("shares")
            if not price: missing.append("price")
            if not reason: missing.append("reason")
            return {"status": "error", "message": f"Missing required parameters: {', '.join(missing)}"}
        
        if action not in ["buy", "sell"]:
            return {"status": "error", "message": f"Invalid action: {action}. Must be 'buy' or 'sell'"}
        
        trade_engine = TransactionManager()
        command = f"/{action} {symbol} {shares} {price}"
        message = trade_engine.execute_command(command)

        if "✅" in message:
            return {
                "status": "success",
                "data": {
                    "action": action,
                    "symbol": symbol,
                    "shares": shares,
                    "price": price,
                    "reason": reason,
                },
                "message": message,
            }

        return {"status": "error", "message": message}
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to execute trade: {str(e)}"}


def get_trade_history(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取交易历史记录
    
    【适用场景】
    - ReAct AI 需要复盘历史交易
    - 查询特定标的的交易流水
    
    【能力边界】
    - 默认返回最近 10 条记录
    - 可按 symbol 过滤
    
    【参数】
    - symbol (str, 可选): 指定标的代码，不填则返回全部
    - limit (int, 可选): 返回记录数量，默认 10
    
    【返回】
    - status: "success" | "error"
    - data: [{"date": str, "action": str, "symbol": str, "shares": float, ...}] | None
    - message: str (仅在 error 时存在)
    """
    try:
        symbol = params.get("symbol")
        limit = params.get("limit", 10)
        
        rows = _load_trade_rows()
        if symbol:
            rows = [row for row in rows if str(row.get("Symbol", "")) == str(symbol)]

        try:
            limit_value = int(limit) if limit is not None else 10
        except (TypeError, ValueError):
            limit_value = 10

        if limit_value > 0:
            rows = rows[-limit_value:]

        history = []
        for row in rows:
            history.append(
                {
                    "date": row.get("Date"),
                    "action": row.get("Action"),
                    "symbol": row.get("Symbol"),
                    "price": _safe_float(row.get("Price")),
                    "shares": _safe_float(row.get("Shares")),
                    "amount": _safe_float(row.get("Amount")),
                    "realized_pnl": _safe_float(row.get("Realized_PnL")),
                    "reason": row.get("Reason") or row.get("reason"),
                }
            )

        return {"status": "success", "data": history}
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to get trade history: {str(e)}"}


def get_trade_reasoning(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取指定标的的历史交易理由（用于复盘）
    
    【适用场景】
    - ReAct AI 需要理解之前的投资逻辑
    - 避免重复犯错
    
    【能力边界】
    - 仅返回有 reason 字段的交易记录
    - 按时间倒序排列
    
    【参数】
    - symbol (str, 必填): 金融标的代码
    - limit (int, 可选): 返回记录数量，默认 5
    
    【返回】
    - status: "success" | "error"
    - data: [{"date": str, "action": str, "reason": str, "outcome": str}] | None
    - message: str (仅在 error 时存在)
    """
    try:
        symbol = params.get("symbol")
        if not symbol:
            return {"status": "error", "message": "Missing required parameter: symbol"}
        
        limit = params.get("limit", 5)
        
        history_result = get_trade_history({"symbol": symbol, "limit": limit})
        if history_result.get("status") != "success":
            return history_result

        reasoning_records = []
        for record in history_result.get("data", []):
            reason = record.get("reason")
            if reason:
                reasoning_records.append(
                    {
                        "date": record.get("date"),
                        "action": record.get("action"),
                        "reason": reason,
                        "shares": record.get("shares"),
                        "price": record.get("price"),
                    }
                )

        if not reasoning_records:
            return {"status": "success", "data": [], "message": "No reason data found"}

        return {"status": "success", "data": reasoning_records}
        
    except Exception as e:
        return {"status": "error", "message": f"Failed to get trade reasoning: {str(e)}"}
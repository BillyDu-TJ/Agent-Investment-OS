# skill_registry.py
"""
技能注册表 - 轻量级方案（无 MCP 依赖）

设计原则：
1. 统一入口 - 所有技能通过此文件导出
2. 标准接口 - 所有技能函数接收 dict 参数，返回 dict 结果
3. 语义化描述 - SKILL_MANIFEST 供 AI 理解可用技能

部署到 OpenClaw 时，只需将此文件中的技能函数注册即可。
"""

from typing import Dict, Any, Callable, Optional  # ✅ 添加 Optional

# 技能导入
from src.tools.market_skills import (
    fetch_realtime_price,
    get_technical_indicators,
    get_volume_analysis
)
from src.tools.macro_skills import (
    get_asset_valuation,
    get_global_macro_snapshot
)
from src.tools.ledger_skills import (
    get_current_portfolio,
    execute_trade,
    get_trade_history,
    get_trade_reasoning
)

# ============================================================================
# SKILL_MANIFEST - 技能描述清单（供 AI 理解可用技能）
# ============================================================================

SKILL_MANIFEST = {
    "market_fetch_price": {
        "description": "获取指定金融标的的最新实时价格",
        "parameters": {
            "symbol": {"type": "string", "description": "金融标的代码，如 'sh513130', '016452', 'us.NDX'"}
        },
        "returns": {
            "status": "success|error",
            "data": {"symbol": "str", "price": "float", "change_pct": "float"}
        }
    },
    "market_get_indicators": {
        "description": "获取指定金融标的的技术指标（MA/RSI/MACD 等）",
        "parameters": {
            "symbol": {"type": "string", "description": "金融标的代码"},
            "indicators": {"type": "array", "description": "指标列表，如 ['ma5', 'rsi', 'macd']"}
        },
        "returns": {
            "status": "success|error",
            "data": {"指标名": "数值"}
        }
    },
    "market_get_volume": {
        "description": "获取指定金融标的的量能异动分析",
        "parameters": {
            "symbol": {"type": "string", "description": "金融标的代码"}
        },
        "returns": {
            "status": "success|skipped|error",
            "data": {"volume_ratio": "float", "signal": "str"}
        }
    },
    "macro_get_valuation": {
        "description": "获取指定金融标的的估值数据（PE/PB/股息率）",
        "parameters": {
            "symbol": {"type": "string", "description": "金融标的代码"},
            "asset_type": {"type": "string", "description": "资产类型，如 'stock', 'index', 'etf'"}
        },
        "returns": {
            "status": "success|skipped|error",
            "data": {"pe": "float", "pb": "float", "dividend_yield": "float"}
        }
    },
    "macro_get_global_snapshot": {
        "description": "获取全球宏观关键指标快照（VIX/汇率/美债收益率）",
        "parameters": {},
        "returns": {
            "status": "success|partial|error",
            "data": {"vix": "object", "usd_cnh": "object", "us_10y_yield": "object"},
            "summary": "str"
        }
    },
    "ledger_get_portfolio": {
        "description": "获取当前持仓组合的完整状态（含市值、盈亏、投资理由）",
        "parameters": {},
        "returns": {
            "status": "success|error",
            "data": {"cash": "float", "total_value": "float", "positions": "array"}
        }
    },
    "ledger_execute_trade": {
        "description": "执行虚拟交易（会修改 portfolio.yaml 和 trade_history.csv）",
        "parameters": {
            "action": {"type": "string", "description": "'buy' 或 'sell'"},
            "symbol": {"type": "string", "description": "金融标的代码"},
            "shares": {"type": "number", "description": "交易数量/份额"},
            "price": {"type": "number", "description": "成交价格"},
            "reason": {"type": "string", "description": "交易理由（重要！用于后续复盘）"}
        },
        "returns": {
            "status": "success|error",
            "data": {"action": "str", "symbol": "str", "shares": "float"}
        }
    },
    "ledger_get_trade_history": {
        "description": "获取交易历史记录",
        "parameters": {
            "symbol": {"type": "string", "description": "指定标的代码（可选）"},
            "limit": {"type": "number", "description": "返回记录数量，默认 10"}
        },
        "returns": {
            "status": "success|error",
            "data": [{"date": "str", "action": "str", "symbol": "str", "shares": "float"}]
        }
    },
    "ledger_get_trade_reasoning": {
        "description": "获取指定标的的历史交易理由（用于复盘）",
        "parameters": {
            "symbol": {"type": "string", "description": "金融标的代码"},
            "limit": {"type": "number", "description": "返回记录数量，默认 5"}
        },
        "returns": {
            "status": "success|error",
            "data": [{"date": "str", "action": "str", "reason": "str"}]
        }
    }
}

# ============================================================================
# 技能函数映射表（供 OpenClaw 注册使用）
# ============================================================================

SKILL_FUNCTIONS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "market_fetch_price": fetch_realtime_price,
    "market_get_indicators": get_technical_indicators,
    "market_get_volume": get_volume_analysis,
    "macro_get_valuation": get_asset_valuation,
    "macro_get_global_snapshot": get_global_macro_snapshot,
    "ledger_get_portfolio": get_current_portfolio,
    "ledger_execute_trade": execute_trade,
    "ledger_get_trade_history": get_trade_history,
    "ledger_get_trade_reasoning": get_trade_reasoning
}


def get_skill_manifest() -> Dict[str, Any]:
    """返回技能描述清单（供 AI 理解可用技能）"""
    return SKILL_MANIFEST


# ✅ 修复：使用 Optional 替代 | None 语法
def get_skill_function(skill_name: str) -> Optional[Callable[[Dict[str, Any]], Dict[str, Any]]]:
    """根据技能名获取对应的函数"""
    return SKILL_FUNCTIONS.get(skill_name)


def list_available_skills() -> list:
    """列出所有可用技能名称"""
    return list(SKILL_FUNCTIONS.keys())
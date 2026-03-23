# src/tools/__init__.py
"""
工具包入口 - 导出所有技能函数

使用方式：
    from src.tools import SKILL_FUNCTIONS, SKILL_MANIFEST
    from src.tools import market_fetch_price, ledger_get_portfolio
"""

from src.tools.skill_registry import (
    SKILL_MANIFEST,
    SKILL_FUNCTIONS,
    get_skill_manifest,
    get_skill_function,
    list_available_skills
)

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

__all__ = [
    # 注册表
    "SKILL_MANIFEST",
    "SKILL_FUNCTIONS",
    "get_skill_manifest",
    "get_skill_function",
    "list_available_skills",
    # Market 技能
    "fetch_realtime_price",
    "get_technical_indicators",
    "get_volume_analysis",
    # Macro 技能
    "get_asset_valuation",
    "get_global_macro_snapshot",
    # Ledger 技能
    "get_current_portfolio",
    "execute_trade",
    "get_trade_history",
    "get_trade_reasoning"
]
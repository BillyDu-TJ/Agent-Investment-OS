# macro_skills.py
"""
宏观与估值技能封装 - 复用 ValuationManager + MacroSentinel 核心类

设计原则：
1. 接口原子化 - 每个函数只做一件事
2. 语义化文档 - 清晰的 docstring 供 AI 理解
3. 零异常中断 - 所有错误返回标准字典，不抛异常
"""

from typing import Dict, Any
from src.tools.valuation import ValuationManager
from src.tools.macro_sentinels import MacroSentinel


def get_asset_valuation(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取指定金融标的的估值数据（PE/PB/股息率等）
    
    【适用场景】
    - ReAct AI 需要基本面分析以判断高估/低估
    - 长期投资决策参考
    
    【能力边界】
    - 权益类资产（股票/指数）：返回 PE/PB/股息率
    - 非权益类（黄金/债券/美股指数/场外基金）：返回 skipped
    - 估值数据可能有 T+1 延迟
    
    【参数】
    - symbol (str, 必填): 金融标的代码
    - asset_type (str, 可选): 资产类型
      支持：'stock', 'index', 'etf', 'us_index', 'gold', 'bond', 'otc_fund'
      默认：'stock'
    
    【返回】
    - status: "success" | "skipped" | "error"
    - data: {"pe": float, "pb": float, "dividend_yield": float} | None
    - message: str (仅在 skipped/error 时存在)
    """
    try:
        symbol = params.get("symbol")
        if not symbol:
            return {"status": "error", "message": "Missing required parameter: symbol"}
        
        valuation_manager = ValuationManager()
        result = valuation_manager.get_valuation(symbol)
        
        # 处理 ValuationManager 的返回格式
        if isinstance(result, dict):
            if result.get("pe") == "N/A" or result.get("status") == "skipped":
                return {"status": "skipped", "message": f"{symbol} 无需估值或无估值数据"}
            else:
                return {"status": "success", "data": result}
        else:
            return {"status": "success", "data": result}
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to get valuation: {str(e)}"}


def get_global_macro_snapshot(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取全球宏观关键指标的综合快照
    
    【适用场景】
    - ReAct AI 需要判断宏观环境风险
    - 系统性风险预警
    
    【能力边界】
    - 支持部分成功（单个指标失败不影响其他指标）
    - 数据更新频率：VIX 实时，汇率实时，美债收益率延迟
    
    【参数】
    - 无必填参数
    
    【返回】
    - status: "success" | "partial" | "error"
    - data: {
        "vix": {"value": float, "level": str},
        "usd_cnh": {"value": float},
        "us_10y_yield": {"value": float}
      } | None
    - summary: str (综合评估)
    - message: str (仅在 error 时存在)
    """
    try:
        macro_sentinel = MacroSentinel()
        
        result = {
            "vix": None,
            "usd_cnh": None,
            "us_10y_yield": None
        }
        success_count = 0
        messages = []
        
        # 获取 VIX
        try:
            vix_data = macro_sentinel.get_vix()
            if vix_data:
                result["vix"] = vix_data
                success_count += 1
        except Exception as e:
            messages.append(f"VIX 获取失败：{str(e)}")
        
        # 获取 USD/CNH
        try:
            usd_cnh_data = macro_sentinel.get_usd_cnh()
            if usd_cnh_data:
                result["usd_cnh"] = usd_cnh_data
                success_count += 1
        except Exception as e:
            messages.append(f"USD/CNH 获取失败：{str(e)}")
        
        # 获取美债收益率
        try:
            us_10y_data = macro_sentinel.get_us_10y_yield()
            if us_10y_data:
                result["us_10y_yield"] = us_10y_data
                success_count += 1
        except Exception as e:
            messages.append(f"美债收益率获取失败：{str(e)}")
        
        # 生成综合评估
        summary = _generate_macro_summary(result)
        
        if success_count == 3:
            return {"status": "success", "data": result, "summary": summary}
        elif success_count > 0:
            return {"status": "partial", "data": result, "summary": summary, "message": "; ".join(messages)}
        else:
            return {"status": "error", "message": "All macro indicators failed: " + "; ".join(messages)}
            
    except Exception as e:
        return {"status": "error", "message": f"Failed to get macro snapshot: {str(e)}"}


def _generate_macro_summary(data: Dict[str, Any]) -> str:
    """生成宏观数据综合评估"""
    summary_parts = []
    
    # VIX 评估
    vix = data.get("vix")
    if vix and vix.get("value"):
        level = vix.get("level", "unknown")
        summary_parts.append(f"VIX={vix.get('value'):.2f} ({level})")
    
    # 汇率评估
    usd_cnh = data.get("usd_cnh")
    if usd_cnh and usd_cnh.get("value"):
        summary_parts.append(f"USD/CNH={usd_cnh.get('value'):.4f}")
    
    # 美债收益率评估
    us_10y = data.get("us_10y_yield")
    if us_10y and us_10y.get("value"):
        summary_parts.append(f"US10Y={us_10y.get('value'):.2f}%")
    
    return " | ".join(summary_parts) if summary_parts else "无可用数据"
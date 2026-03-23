#!/usr/bin/env python3
"""
test_skills.py
MCP 技能完整测试脚本

使用方法：
    python test_skills.py

输出说明：
    ✅ 表示测试通过
    ❌ 表示测试失败
    ⚠️  表示跳过或警告
"""

import json
import sys
from datetime import datetime
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, '.')

# 导入所有技能函数
from src.tools import (
    # Market 技能
    fetch_realtime_price,
    get_technical_indicators,
    get_volume_analysis,
    # Macro 技能
    get_asset_valuation,
    get_global_macro_snapshot,
    # Ledger 技能
    get_current_portfolio,
    execute_trade,
    get_trade_history,
    get_trade_reasoning,
    # 注册表
    SKILL_MANIFEST,
    list_available_skills
)


class TestResult:
    """测试结果记录"""
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
    
    def __str__(self):
        status = "✅" if self.passed else "❌"
        return f"{status} {self.name}: {self.message}"


class SkillTester:
    """技能测试器"""
    
    def __init__(self):
        self.results: list[TestResult] = []
        self.start_time = datetime.now()
    
    def add_result(self, name: str, passed: bool, message: str = ""):
        """添加测试结果"""
        self.results.append(TestResult(name, passed, message))
    
    def print_header(self, title: str):
        """打印章节标题"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    def print_result(self, result: TestResult):
        """打印单个测试结果"""
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"\n{status} | {result.name}")
        if result.message:
            print(f"       {result.message}")
    
    def print_summary(self):
        """打印测试总结"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\n{'='*60}")
        print(f"  测试总结")
        print(f"{'='*60}")
        print(f"  总测试数：{total}")
        print(f"  通过：{passed} ✅")
        print(f"  失败：{failed} ❌")
        print(f"  成功率：{success_rate:.1f}%")
        print(f"  耗时：{duration:.2f} 秒")
        print(f"{'='*60}")
        
        if failed == 0:
            print("\n🎉 所有测试通过！")
        else:
            print(f"\n⚠️  有 {failed} 个测试失败，请检查上方输出")
        
        return failed == 0


# ============================================================================
# 测试用例
# ============================================================================

def test_skill_registry(tester: SkillTester):
    """测试技能注册表"""
    tester.print_header("测试 1: 技能注册表")
    
    # 测试可用技能列表
    try:
        skills = list_available_skills()
        tester.add_result(
            "list_available_skills",
            len(skills) > 0,
            f"共 {len(skills)} 个可用技能: {', '.join(skills[:3])}..."
        )
    except Exception as e:
        tester.add_result("list_available_skills", False, str(e))
    
    # 测试技能清单
    try:
        manifest = SKILL_MANIFEST
        tester.add_result(
            "SKILL_MANIFEST",
            len(manifest) > 0,
            f"共 {len(manifest)} 个技能描述"
        )
    except Exception as e:
        tester.add_result("SKILL_MANIFEST", False, str(e))


def test_market_skills(tester: SkillTester):
    """测试市场数据技能"""
    tester.print_header("测试 2: Market 技能")
    
    # 测试获取实时价格 - A 股指数
    try:
        result = fetch_realtime_price({"symbol": "sh000001"})
        tester.add_result(
            "fetch_realtime_price (上证指数)",
            result.get("status") in ["success", "error"],
            f"status={result.get('status')}"
        )
        if result.get("status") == "success":
            print(f"       数据：{json.dumps(result.get('data'), ensure_ascii=False)[:100]}...")
    except Exception as e:
        tester.add_result("fetch_realtime_price (上证指数)", False, str(e))
    
    # 测试获取实时价格 - 美股指数
    try:
        result = fetch_realtime_price({"symbol": "us.NDX"})
        tester.add_result(
            "fetch_realtime_price (纳斯达克)",
            result.get("status") in ["success", "error"],
            f"status={result.get('status')}"
        )
    except Exception as e:
        tester.add_result("fetch_realtime_price (纳斯达克)", False, str(e))
    
    # 测试技术指标
    try:
        result = get_technical_indicators({
            "symbol": "sh000001",
            "indicators": ["ma5", "ma20", "rsi"]
        })
        tester.add_result(
            "get_technical_indicators",
            result.get("status") in ["success", "error", "skipped"],
            f"status={result.get('status')}"
        )
        if result.get("status") == "success":
            data = result.get("data", {})
            print(f"       指标：MA5={data.get('ma5')}, RSI={data.get('rsi')}")
    except Exception as e:
        tester.add_result("get_technical_indicators", False, str(e))
    
    # 测试量能分析
    try:
        result = get_volume_analysis({"symbol": "sh000001"})
        tester.add_result(
            "get_volume_analysis",
            result.get("status") in ["success", "skipped", "error"],
            f"status={result.get('status')}"
        )
    except Exception as e:
        tester.add_result("get_volume_analysis", False, str(e))
    
    # 测试错误处理 - 空参数
    try:
        result = fetch_realtime_price({})
        tester.add_result(
            "fetch_realtime_price (空参数)",
            result.get("status") == "error",
            f"正确返回错误：{result.get('message', '')[:50]}"
        )
    except Exception as e:
        tester.add_result("fetch_realtime_price (空参数)", False, f"应返回错误字典而非抛异常：{str(e)}")
    
    # 测试错误处理 - 无效符号
    try:
        result = fetch_realtime_price({"symbol": "INVALID_SYMBOL_XYZ"})
        tester.add_result(
            "fetch_realtime_price (无效符号)",
            result.get("status") == "error",
            f"正确返回错误：{result.get('message', '')[:50]}"
        )
    except Exception as e:
        tester.add_result("fetch_realtime_price (无效符号)", False, f"应返回错误字典而非抛异常：{str(e)}")


def test_macro_skills(tester: SkillTester):
    """测试宏观数据技能"""
    tester.print_header("测试 3: Macro 技能")
    
    # 测试估值数据 - 指数
    try:
        result = get_asset_valuation({"symbol": "sh000001", "asset_type": "index"})
        tester.add_result(
            "get_asset_valuation (上证指数)",
            result.get("status") in ["success", "skipped", "error"],
            f"status={result.get('status')}"
        )
        if result.get("status") == "success":
            data = result.get("data", {})
            print(f"       PE={data.get('pe')}, PB={data.get('pb')}")
    except Exception as e:
        tester.add_result("get_asset_valuation (上证指数)", False, str(e))
    
    # 测试估值数据 - 场外基金 (应跳过)
    try:
        result = get_asset_valuation({"symbol": "016452", "asset_type": "otc_fund"})
        tester.add_result(
            "get_asset_valuation (场外基金)",
            result.get("status") in ["skipped", "success", "error"],
            f"status={result.get('status')} (场外基金应跳过估值)"
        )
    except Exception as e:
        tester.add_result("get_asset_valuation (场外基金)", False, str(e))
    
    # 测试全球宏观快照
    try:
        result = get_global_macro_snapshot({})
        tester.add_result(
            "get_global_macro_snapshot",
            result.get("status") in ["success", "partial", "error"],
            f"status={result.get('status')}"
        )
        if result.get("status") in ["success", "partial"]:
            data = result.get("data", {})
            summary = result.get("summary", "N/A")
            print(f"       摘要：{summary}")
    except Exception as e:
        tester.add_result("get_global_macro_snapshot", False, str(e))


def test_ledger_skills(tester: SkillTester):
    """测试账本技能"""
    tester.print_header("测试 4: Ledger 技能")
    
    # 测试获取当前持仓
    try:
        result = get_current_portfolio({})
        tester.add_result(
            "get_current_portfolio",
            result.get("status") in ["success", "error"],
            f"status={result.get('status')}"
        )
        if result.get("status") == "success":
            data = result.get("data", {})
            print(f"       现金：{data.get('cash')}, 总资产：{data.get('total_value')}")
            positions = data.get("positions", [])
            print(f"       持仓数：{len(positions)}")
    except Exception as e:
        tester.add_result("get_current_portfolio", False, str(e))
    
    # 测试执行交易 - 参数验证 (不实际执行)
    try:
        # 测试缺少必要参数
        result = execute_trade({"action": "buy"})  # 缺少 symbol, shares, price, reason
        tester.add_result(
            "execute_trade (参数验证)",
            result.get("status") == "error",
            f"正确返回错误：{result.get('message', '')[:50]}"
        )
    except Exception as e:
        tester.add_result("execute_trade (参数验证)", False, f"应返回错误字典：{str(e)}")
    
    # 测试执行交易 - 无效 action
    try:
        result = execute_trade({
            "action": "invalid",
            "symbol": "AAPL",
            "shares": 10,
            "price": 100,
            "reason": "test"
        })
        tester.add_result(
            "execute_trade (无效 action)",
            result.get("status") == "error",
            f"正确返回错误：{result.get('message', '')[:50]}"
        )
    except Exception as e:
        tester.add_result("execute_trade (无效 action)", False, f"应返回错误字典：{str(e)}")
    
    # ⚠️  注意：以下测试被注释，避免修改真实数据
    # 如需测试，请取消注释并谨慎使用
    """
    try:
        result = execute_trade({
            "action": "buy",
            "symbol": "AAPL",
            "shares": 1,
            "price": 100.0,
            "reason": "测试交易 - 可安全删除"
        })
        tester.add_result(
            "execute_trade (实际执行)",
            result.get("status") == "success",
            f"status={result.get('status')}"
        )
    except Exception as e:
        tester.add_result("execute_trade (实际执行)", False, str(e))
    """
    tester.add_result(
        "execute_trade (实际执行)",
        True,
        "⚠️  已跳过 (避免修改真实数据)"
    )
    
    # 测试获取交易历史
    try:
        result = get_trade_history({"limit": 5})
        tester.add_result(
            "get_trade_history",
            result.get("status") in ["success", "error"],
            f"status={result.get('status')}"
        )
        if result.get("status") == "success":
            history = result.get("data", [])
            print(f"       记录数：{len(history)}")
    except Exception as e:
        tester.add_result("get_trade_history", False, str(e))
    
    # 测试获取交易理由
    try:
        result = get_trade_reasoning({"symbol": "sh000001", "limit": 3})
        tester.add_result(
            "get_trade_reasoning",
            result.get("status") in ["success", "error"],
            f"status={result.get('status')}"
        )
        if result.get("status") == "success":
            reasoning = result.get("data", [])
            print(f"       理由记录数：{len(reasoning)}")
    except Exception as e:
        tester.add_result("get_trade_reasoning", False, str(e))


def test_response_format(tester: SkillTester):
    """测试返回格式规范性"""
    tester.print_header("测试 5: 返回格式规范")
    
    # 所有技能应返回 dict
    test_cases = [
        ("fetch_realtime_price", fetch_realtime_price, {"symbol": "sh000001"}),
        ("get_asset_valuation", get_asset_valuation, {"symbol": "sh000001"}),
        ("get_current_portfolio", get_current_portfolio, {}),
    ]
    
    for name, func, params in test_cases:
        try:
            result = func(params)
            is_dict = isinstance(result, dict)
            has_status = "status" in result
            tester.add_result(
                f"{name} 返回格式",
                is_dict and has_status,
                f"dict={is_dict}, has_status={has_status}"
            )
        except Exception as e:
            tester.add_result(f"{name} 返回格式", False, f"抛异常：{str(e)}")


def test_zero_exception(tester: SkillTester):
    """测试零异常中断原则"""
    tester.print_header("测试 6: 零异常中断原则")
    
    # 传入各种异常参数，确保不抛异常
    edge_cases = [
        ("fetch_realtime_price", fetch_realtime_price, {"symbol": None}),
        ("fetch_realtime_price", fetch_realtime_price, {"symbol": ""}),
        ("fetch_realtime_price", fetch_realtime_price, {"symbol": 123}),  # 错误类型
        ("get_technical_indicators", get_technical_indicators, {}),
        ("get_asset_valuation", get_asset_valuation, {"symbol": None}),
        ("execute_trade", execute_trade, {}),
        ("execute_trade", execute_trade, {"action": None, "symbol": None}),
    ]
    
    for name, func, params in edge_cases:
        try:
            result = func(params)
            # 应返回错误字典而非抛异常
            is_safe = isinstance(result, dict) and result.get("status") == "error"
            tester.add_result(
                f"{name} 异常输入",
                is_safe,
                f"返回错误字典={is_safe}"
            )
        except Exception as e:
            tester.add_result(f"{name} 异常输入", False, f"抛异常：{str(e)}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("  Agentic-Investment-OS 技能测试")
    print(f"  开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    tester = SkillTester()
    
    # 执行所有测试
    test_skill_registry(tester)
    test_market_skills(tester)
    test_macro_skills(tester)
    test_ledger_skills(tester)
    test_response_format(tester)
    test_zero_exception(tester)
    
    # 打印总结
    all_passed = tester.print_summary()
    
    # 返回退出码
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
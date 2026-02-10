# main.py

import os
import yaml
import logging
from datetime import datetime
from src.tools.market_data import MarketData
from src.utils.report_gen import ReportGenerator
from src.tools.portfolio_manager import PortfolioManager
from src.tools.news_mock import get_macro_news
from src.core.advisor import InvestmentAdvisor
from src.core.regime import RegimeIdentifier

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_settings():
    """加载 API 设置"""
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_investment_agent():
    logging.info("🚀 [Agent 投资辅助系统] 启动全流程：感知 + 决策...")

    # 1. 基础配置加载
    settings = load_settings()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 2. 获取用户持仓并动态更新行情监控列表
    portfolio_mgr = PortfolioManager()
    user_holdings = portfolio_mgr.portfolio_data.get('holdings', [])

    collector = MarketData()
    collector.update_targets(user_holdings) # 动态添加持仓标的
    
    # 3. 执行行情数据采集 (Phase 1)
    market_summary = collector.get_market_summary()
    indices_data = market_summary.get('indices', [])
    if not indices_data:
        logging.error("未能抓取到任何数据，任务终止。")
        return

    # 4. 生成数据摘要日报 (Phase 1 Report)
    MY_REPORT_COLUMNS = [
        ("名称", "name"),
        ("价格", "close"),
        ("涨跌", "change_pct"),
        ("RSI", "indicators.RSI"),
        ("MACD", "indicators.MACD"),
        ("20日均线", "indicators.MA20"),
    ]
    data_reporter = ReportGenerator(output_dir="reports")
    brief_path = data_reporter.generate_daily_report(indices_data, MY_REPORT_COLUMNS)
    logging.info(f"📊 事实简报已生成: {brief_path}")

    # 5. 计算实时持仓与盈亏 (Phase 2 Task 1/2)
    # 包含 Phase 2.5 新增的 strategy, term 等意图标签
    portfolio_status = portfolio_mgr.get_portfolio_status(indices_data)

    # 6. 获取宏观新闻 (Phase 2 Task 2)
    macro_news = get_macro_news()

    # 7. 获取当前市场体制信息 (Phase 2.5 Task 3)
    # 我们通常以上证指数 (sh000001) 作为大盘体制的判断基准
    regime_tool = RegimeIdentifier()
    # 假设 collector.last_dfs 已经保存了抓取过程中的 DataFrame
    benchmark_symbol = "sh000001"
    index_df = collector.last_dfs.get(benchmark_symbol)
    
    if index_df is not None:
        regime_info = regime_tool.identify(index_df)
        logging.info(f"时段体制识别完成: {regime_info[0]}")
    else:
        regime_info = ("Unknown", "未能获取大盘指数数据，无法识别体制")
        logging.warning("未能获取上证指数 DataFrame，体制识别失效")

    # 8. 调用硅基大脑进行深度分析 (Phase 2.5 Task 4)
    advisor = InvestmentAdvisor(
        api_key=settings['api_key'], 
        base_url=settings.get('base_url', "https://api.deepseek.com")
    )
    
    ai_analysis = advisor.analyze(
        market_data=indices_data,
        portfolio_data=portfolio_status,
        macro_news=macro_news,
        regime_info=regime_info # 传入体制信息
    )

    # 9. 保存 AI 决策报告 (Phase 2 Report)
    ai_report_path = f"reports/{today_str}_AI_Advisor.md"
    with open(ai_report_path, "w", encoding="utf-8") as f:
        f.write(ai_analysis)

    logging.info("=" * 50)
    logging.info(f"✅ 全流程任务完成！")
    logging.info(f"1️⃣ 事实报告: {brief_path}")
    logging.info(f"2️⃣ 决策报告: {ai_report_path}")
    logging.info("=" * 50)
    
    # 预览 AI 建议
    print("\n--- AI 投资建议预览 ---")
    # 打印前 600 个字符
    print(ai_analysis[:600] + "...\n(更多详见报告文件)")

if __name__ == "__main__":
    if not os.path.exists("reports"):
        os.makedirs("reports")
    run_investment_agent()
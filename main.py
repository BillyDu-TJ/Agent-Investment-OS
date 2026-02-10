# main.py

import os
import yaml
import logging
from datetime import datetime
from src.tools.market_data import MarketData
from src.utils.report_gen import ReportGenerator  # 找回 Phase 1 的报告生成器
from src.tools.portfolio_manager import PortfolioManager
from src.tools.news_mock import get_macro_news
from src.core.advisor import InvestmentAdvisor

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
    # 定义想要在表格中展示的列
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

    # 5. 计算实时持仓与盈亏 (Phase 2 Task 1)
    portfolio_status = portfolio_mgr.get_portfolio_status(indices_data)

    # 6. 获取宏观新闻 (Phase 2 Task 2)
    macro_news = get_macro_news()

    # 7. 调用硅基大脑进行深度分析 (Phase 2 Task 3)
    advisor = InvestmentAdvisor(
        api_key=settings['api_key'], 
        base_url=settings.get('base_url', "https://api.deepseek.com")
    )
    
    ai_analysis = advisor.analyze(
        market_data=indices_data,
        portfolio_data=portfolio_status,
        macro_news=macro_news
    )

    # 8. 保存 AI 决策报告 (Phase 2 Report)
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
    print(ai_analysis[:500] + "...\n(更多详见报告文件)")

if __name__ == "__main__":
    if not os.path.exists("reports"):
        os.makedirs("reports")
    run_investment_agent()
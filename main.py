# main.py

import os
import yaml
import logging
from datetime import datetime
from src.tools.market_data import MarketData
from src.tools.valuation import ValuationManager  
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
    logging.info("🚀 [Agent 投资辅助系统] 启动全流程：感知 + 估值 + 决策...")

    # 1. 基础配置加载
    settings = load_settings()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 2. 获取用户持仓并动态更新行情监控列表
    portfolio_mgr = PortfolioManager()
    user_holdings = portfolio_mgr.portfolio_data.get('holdings', [])

    collector = MarketData()
    collector.update_targets(user_holdings) # 动态添加持仓标的
    
    # 3. 执行行情数据采集 (Phase 1: Technicals)
    market_summary = collector.get_market_summary()
    indices_data = market_summary.get('indices', [])
    if not indices_data:
        logging.error("未能抓取到任何数据，任务终止。")
        return

    # ==========================================
    # [新增] Phase 1.5: Valuation Analysis (估值注入)
    # ==========================================
    logging.info("正在进行估值面扫描...")
    val_mgr = ValuationManager() # 初始化估值管理器(含大表缓存)
    
    for item in indices_data:
        symbol = item.get('symbol')
        # 获取该标的的估值数据
        val_data = val_mgr.get_valuation(symbol)
        
        # 将估值数据“缝合”进现有的行情字典中
        # 结果变成: {'name':..., 'close':..., 'valuation': {'pe': 16.5, ...}}
        item['valuation'] = val_data
        
        # 简单打印日志
        if val_data.get('pe'):
            logging.info(f" -> {item['name']}: PE={val_data['pe']}, PB={val_data.get('pb')}")
        else:
            logging.info(f" -> {item['name']}: 暂无估值数据")
    # ==========================================

    # 4. 生成数据摘要日报 (Phase 1 Report)
    # 你可以后续在 MY_REPORT_COLUMNS 里加上 valuation.pe 来生成更丰富的简报
    MY_REPORT_COLUMNS = [
        ("名称", "name"),
        ("价格", "close"),
        ("涨跌", "change_pct"),
        ("估值", "valuation.pe"),
        ("PB", "valuation.pb"),
        ("RSI", "indicators.RSI"),
        ("MACD", "indicators.MACD"),
    ]
    data_reporter = ReportGenerator(output_dir="reports")
    brief_path = data_reporter.generate_daily_report(indices_data, MY_REPORT_COLUMNS)
    logging.info(f"📊 事实简报已生成: {brief_path}")

    # 5. 计算实时持仓与盈亏 (Phase 2 Task 1/2)
    portfolio_status = portfolio_mgr.get_portfolio_status(indices_data)

    # 6. 获取宏观新闻 (Phase 2 Task 2)
    macro_news = get_macro_news()

    # 7. 获取当前市场体制信息 (Phase 2.5 Task 3)
    regime_tool = RegimeIdentifier()
    benchmark_symbol = "sh000001"
    index_df = collector.last_dfs.get(benchmark_symbol)
    
    if index_df is not None:
        regime_info = regime_tool.identify(index_df)
        logging.info(f"时段体制识别完成: {regime_info[0]}")
    else:
        regime_info = ("Unknown", "未能获取大盘指数数据，无法识别体制")
        logging.warning("未能获取上证指数 DataFrame，体制识别失效")

    # 8. 调用硅基大脑进行深度分析 (Phase 2.5 Task 4)
    # 注意：此时传入的 indices_data 已经包含了 valuation 字段
    advisor = InvestmentAdvisor(
        api_key=settings['api_key'], 
        base_url=settings.get('base_url', "https://api.deepseek.com")
    )
    
    ai_analysis = advisor.analyze(
        market_data=indices_data, # <--- 这里面现在有 PE/PB 了
        portfolio_data=portfolio_status,
        macro_news=macro_news,
        regime_info=regime_info 
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
    print(ai_analysis[:600] + "...\n(更多详见报告文件)")

if __name__ == "__main__":
    if not os.path.exists("reports"):
        os.makedirs("reports")
    run_investment_agent()
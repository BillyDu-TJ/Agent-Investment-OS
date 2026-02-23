# main.py

import os
import yaml
import logging
from datetime import datetime
from src.tools.market_data import MarketData
from src.tools.valuation import ValuationManager
from src.tools.news_hub import NewsHub          # <--- [修改] 引入真实新闻模块
from src.utils.report_gen import ReportGenerator
from src.tools.portfolio_manager import PortfolioManager
from src.core.advisor import InvestmentAdvisor
from src.core.regime import RegimeIdentifier

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_settings():
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_investment_agent():
    logging.info("🚀 [Agent 投资辅助系统] 启动全流程：感知 + 估值 + 决策...")

    settings = load_settings()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    portfolio_mgr = PortfolioManager()
    user_holdings = portfolio_mgr.portfolio_data.get('holdings', [])

    collector = MarketData()
    collector.update_targets(user_holdings)
    
    # 1. 行情与估值采集
    market_summary = collector.get_market_summary()
    indices_data = market_summary.get('indices', [])
    
    val_mgr = ValuationManager()
    for item in indices_data:
        item['valuation'] = val_mgr.get_valuation(item.get('symbol'))

    # 2. [修改] 获取真实宏观新闻
    news_hub = NewsHub()
    real_news = news_hub.get_recent_news() # 获取最新的 30 条真实新闻
    
    # 3. [新增] 生成独立的新闻快讯报告
    news_report_path = f"reports/{today_str}_News_Flash.md"
    with open(news_report_path, "w", encoding="utf-8") as f:
        f.write(f"# 📅 财经快讯 - {today_str}\n\n")
        if real_news:
            for i, content in enumerate(real_news, 1):
                f.write(f"### [{i}] 快讯内容\n{content}\n\n---\n")
        else:
            f.write("今日暂无重大实时快讯。")
    logging.info(f"📰 实时快讯报告已生成: {news_report_path}")

    # 4. 生成事实简报 (技术面)
    MY_REPORT_COLUMNS = [
        ("名称", "name"),
        ("价格", "close"),
        ("涨跌", "change_pct"),
        ("PE(估值)", "valuation.pe"),     
        ("PB(市净)", "valuation.pb"),     
        ("RSI", "indicators.RSI"),
        ("MACD", "indicators.MACD"),
        ("量比", "indicators.Vol_Ratio"),   
        ("布林带", "indicators.Bollinger")]
    data_reporter = ReportGenerator(output_dir="reports")
    brief_path = data_reporter.generate_daily_report(indices_data, MY_REPORT_COLUMNS)

    # 5. 体制与持仓分析
    portfolio_status = portfolio_mgr.get_portfolio_status(indices_data)
    regime_tool = RegimeIdentifier()
    index_df = collector.last_dfs.get("sh000001")
    regime_info = regime_tool.identify(index_df) if index_df is not None else ("Unknown", "未能识别体制")

    # 6. [修改] 调用大脑分析 (传入真实新闻列表)
    advisor = InvestmentAdvisor(api_key=settings['api_key'], base_url=settings.get('base_url'))
    ai_analysis = advisor.analyze(
        market_data=indices_data,
        portfolio_data=portfolio_status,
        macro_news="\n".join(real_news), # <--- [修改] 将真实新闻列表合并为字符串
        regime_info=regime_info
    )

    # 7. 注入新闻到最终报告中 (增强 AI 报告的阅读价值)
    ai_report_path = f"reports/{today_str}_AI_Advisor.md"
    with open(ai_report_path, "w", encoding="utf-8") as f:
        f.write(f"> ⚠️ 数据时效提示：当前估值参考日期为 {indices_data[-1].get('valuation',{}).get('date', 'Unknown')}\n\n")
        f.write(ai_analysis)
        f.write("\n\n---\n## 附录：今日参考快讯\n")
        f.write("\n".join([f"- {n}" for n in real_news[:10]])) # 附带前10条新闻

    logging.info("=" * 50)
    logging.info(f"✅ 全流程完成！事实简报: {brief_path} | 决策报告: {ai_report_path}")
    logging.info("=" * 50)

     # === [Task C 新增: 启动 CLI 交互式对话] ===
    print("\n" + "*" * 50)
    print("🤖 [私人投资顾问已上线]")
    print("您可以针对生成的报告自由追问 (例如：'为什么建议减仓软件ETF？' / '能帮我算算目前仓位的整体盈亏吗？')")
    print("*" * 50)
    
    while True:
        try:
            user_input = input("\n👤 您的追问 (输入 'q' 退出) > ").strip()
            
            if user_input.lower() in ['q', 'quit', 'exit']:
                print("👋 感谢使用，祝您投资顺利！再见。")
                break
            
            if not user_input:
                continue
                
            print("🧠 顾问正在基于底层数据思考...")
            # 调用 advisor 的上下文追问接口
            answer = advisor.chat(user_input)
            print(f"\n🤖 顾问回答:\n{answer}")
            
        except KeyboardInterrupt:
            # 捕获 Ctrl+C 强制退出
            print("\n👋 强制退出，再见。")
            break

if __name__ == "__main__":
    if not os.path.exists("reports"): os.makedirs("reports")
    run_investment_agent()
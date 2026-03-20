# main.py

import os
import yaml
import logging
import csv
from datetime import datetime
from openai import OpenAI
import re

from src.tools.market_data import MarketData
from src.tools.valuation import ValuationManager
from src.tools.news_hub import NewsHub
from src.tools.portfolio_manager import PortfolioManager
from src.tools.transaction import TransactionManager  # [Task 2] 交易引擎
from src.core.advisor import InvestmentAdvisor
from src.core.regime import RegimeIdentifier
from src.core.memory import ContextLoader            # [Task 1] 记忆引擎
from src.utils.report_gen import ReportGenerator
from src.utils.obsidian_sync import ObsidianSyncer   # [Task 3] 知识库同步
from src.core.risk_officer import RiskOfficer  # [Phase 5 新增]
from src.core.cio import CIO  # [Phase 5 新增]
from src.tools.macro_sentinels import MacroSentinel # [New]
import json # [New] 用于 debug 打印
from src.core.strategy_parser import PolicyTranslator
from src.tools.market_hunter import MarketHunter
from src.core.knowledge_base import ExpertKnowledgeBase
from src.tools.rebalancer import Rebalancer
from src.tools.performance_tracker import PerformanceTracker

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_settings():
    with open("config/settings.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_recent_trades_summary(csv_path, limit=10):
    """
    从 CSV 读取最近 N 笔真实交易记录，喂给 AI
    让 AI 知道账户的'真实历史动作'，弥补短期记忆的不足。
    """
    if not os.path.exists(csv_path):
        return "暂无历史交易记录。"
    
    trades = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)
    except Exception:
        return "读取交易记录失败。"

    if not trades:
        return "暂无历史交易记录。"

    # 取最近 limit 条，按时间倒序
    recent = trades[-limit:]
    summary = []
    for t in recent:
        # 格式: [2026-02-23] BUY sh513130 1000份 @ 0.688
        summary.append(f"[{t['Date']}] {t['Action']} {t['Symbol']} {t['Shares']}份 @ {t['Price']} (Pnl: {t['Realized_PnL']})")
    
    return "\n".join(summary)

def run_investment_agent():
    logging.info("🚀 [Agentic-Investment-OS] 系统全功能启动...")
    
    # 1. 初始化基础设施
    settings = load_settings()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 初始化各个管理器
    portfolio_mgr = PortfolioManager()
    trans_mgr = TransactionManager()     # 交易/记账
    context_loader = ContextLoader()     # 短期记忆
    obsidian_sync = ObsidianSyncer()     # 知识库同步
    
    # [Phase 6 关键] 启动时自检，识别手动清仓并记录
    if trans_mgr.sanitize_portfolio():
        logging.info("✅ 账本自愈完成，已同步手动清仓记录至 AI 记忆。")

    user_holdings = portfolio_mgr.portfolio_data.get('holdings', [])
    collector = MarketData()
    collector.update_targets(user_holdings)

    # 2. 感知层：获取多维数据
    logging.info("📡 正在建立全维市场感知...")
    sentinel = MacroSentinel()
    macro_data = sentinel.get_macro_data()
    gold_anchor = sentinel.get_gold_anchor() # 强制追踪黄金
    market_summary = collector.get_market_summary()
    macro_metrics = collector.get_macro_metrics()
    us_10y = macro_metrics.get('us_10y', 'N/A')
    indices_data = market_summary.get('indices', [])
    
    # 注入估值数据
    val_mgr = ValuationManager()
    for item in indices_data:
        symbol = item.get('symbol')
        # 获取 PE/PB
        item['valuation'] = val_mgr.get_valuation(symbol)
        # [新增] 获取净利润增速 (PEG 修正)
        item['growth_rate'] = val_mgr.get_growth_rate(symbol)

    # 获取真实新闻
    news_hub = NewsHub()
    real_news = news_hub.get_recent_news()

    # [Phase 6] 构造宏观上下文并插入新闻头部
    vix_info = f"VIX恐慌指数: {macro_data.get('vix', 'N/A')}"
    cnh_info = f"USD/CNH汇率: {macro_data.get('usd_cnh', 'N/A')}"
    gold_info = f"黄金锚点: {gold_anchor['price']} (涨跌: {gold_anchor['change_pct']}%)" if gold_anchor else "黄金数据不可用"
    
    macro_context_block = f"""
    【全球宏观硬指标 (哨兵监控)】
    1. {vix_info} (若>30则市场极度恐慌)
    2. {cnh_info} (若>7.3则人民币承压)
    3. {gold_info}
    4. 十年期美债收益率: {us_10y}% (若>4.0%则压制成长股估值)
    """
    real_news.insert(0, macro_context_block)
    
    # 获取账户状态 (含自动计算的持仓市值)
    portfolio_status = portfolio_mgr.get_portfolio_status(indices_data)
    
    # 获取市场体制
    regime_tool = RegimeIdentifier()
    index_df = collector.last_dfs.get("sh000001") # 默认以上证指数判定大盘体制
    regime_info = regime_tool.identify(index_df) if index_df is not None else ("Unknown", "未能识别体制")

    # =====================================================================
    #[Phase 7 新增] 策略解析、猎人选股与大师知识库注入
    # =====================================================================
    logging.info("🧠 正在启动策略引擎与大师知识库...")
    
    # 1. 加载 YAML 策略
    with open("config/strategy_profile.yaml", "r", encoding="utf-8") as f:
        strategy_config = yaml.safe_load(f)
    
    # 2. 初始化各大脑模块
    kb = ExpertKnowledgeBase()
    translator = PolicyTranslator(client=OpenAI(api_key=settings['api_key'], base_url=settings.get('base_url')))
    hunter = MarketHunter()

    # 3. 语义映射：将哲学转化为量化因子权重
    dynamic_sat_weights = translator.translate(strategy_config.get('investment_philosophy', '稳健成长'))
    sat_hunt_config = {"factors": dynamic_sat_weights.model_dump()} # 转换为字典供猎人使用
    
    # 4. 猎人出击：全市场扫描核心与卫星标的
    logging.info("🎯 猎人正在全市场搜寻符合您哲学的标的...")
    core_targets = hunter.hunt(strategy_config['dynamic_strategies']['core_dca'], top_n_industry=1, top_n_stocks=3)
    sat_targets = hunter.hunt(sat_hunt_config, top_n_industry=1, top_n_stocks=3)
    
    # 5. 大师思维检索：用当前的“宏观体制”去检索书籍/专家的“思维框架”
    query_context = f"市场处于 {regime_info[0]} 体制，美债收益率 {us_10y}%。在这种宏观周期下，专家或经典书籍中关于大类资产配置、仓位控制、风险防范的系统性分析逻辑是什么？"
    expert_wisdom = kb.query_rules(query_context, n_results=3)
    # =====================================================================

    # 3. 记忆与决策准备
    short_term_memory = context_loader.load_history(days=3)
    last_consensus = context_loader.load_consensus() # [Phase 6] 加载昨日共识
    trade_history_str = get_recent_trades_summary(trans_mgr.csv_path)

    # 合并记忆上下文
    # 合并记忆、专家思维与猎人选股池
    full_memory_context = f"""
    {short_term_memory}
    === 昨日 CIO 最终共识 ===
    {last_consensus}

    === 📚 投资大师与经典书籍的思维框架 (参考) ===
    (请提炼以下文献的分析逻辑和应对策略，结合当下的估值与动量数据，批判性地将其应用于今日决策，绝不可生搬硬套)
    {expert_wisdom}

    === 🎯 MarketHunter 机器筛选备选池 (仅供参考) ===
    【核心池候选 (低估红利)】: {json.dumps(core_targets, ensure_ascii=False)}
    【卫星池候选 (哲学映射)】: {json.dumps(sat_targets, ensure_ascii=False)}
    """

    # 4. 输出层：生成各类报告
    # (A) 新闻快讯
    news_report_path = f"reports/{today_str}_News_Flash.md"
    with open(news_report_path, "w", encoding="utf-8") as f:
        f.write(f"# 📅 财经快讯 - {today_str}\n\n")
        if real_news:
            for i, content in enumerate(real_news, 1):
                f.write(f"### [{i}] 快讯\n{content}\n\n---\n")
        else:
            f.write("今日暂无重大实时快讯。")
    
    # (B) 每日事实简报 (技术面+估值+量能)
    MY_REPORT_COLUMNS = [
        ("名称", "name"),
        ("价格", "close"),
        ("涨跌", "change_pct"),
        ("PE(估值)", "valuation.pe"),     
        ("PB(市净)", "valuation.pb"),     
        ("RSI", "indicators.RSI"),
        ("MACD", "indicators.MACD"),
        ("量比", "indicators.Vol_Ratio"),
        ("KDJ(K值)", "indicators.K"),       # [Phase 5 新增]
        ("ATR波动", "indicators.ATR"),      # [Phase 5 新增]    
        ("布林带", "indicators.Bollinger")   
    ]
    data_reporter = ReportGenerator(output_dir="reports")
    brief_path = data_reporter.generate_daily_report(indices_data, MY_REPORT_COLUMNS,
                                                     portfolio_status=portfolio_status)
    
    # 同步简报到 Obsidian
    obsidian_sync.archive_daily_report(brief_path)

    # 5. 决策层：硅基大脑分析
    advisor = InvestmentAdvisor(
        api_key=settings['api_key'], 
        base_url=settings.get('base_url'),
        proxy_config=settings.get('proxy')  # [Phase 4.5] 透传代理配置
    )
    
    # 将“真实交易历史”注入到 Portfolio 数据块中，让 AI 看到
    portfolio_context_with_history = f"""
    {portfolio_status}
    
    === 最近真实交易记录 (Reference) ===
    {trade_history_str}
    """

    # 计算出数学草案
    rebalancer = Rebalancer(portfolio_status, strategy_config, indices_data)
    draft_trade_list = rebalancer.generate_trade_list() 

    ai_analysis = advisor.analyze(
        market_data=indices_data,
        portfolio_data=portfolio_context_with_history, # 注入了交易历史
        macro_news="\n".join(real_news),
        regime_info=regime_info,
        historical_context=full_memory_context,       # <--- [Phase 7 修改] 注入包含大师知识、猎人选股和短期记忆的完全体上下文
        draft_trade_list=draft_trade_list
    )

    # 引入红军风控官进行审查
    risk_officer = RiskOfficer(
        api_key=settings['api_key'], 
        base_url=settings.get('base_url'),
        proxy_config=settings.get('proxy')
    )
    risk_report = risk_officer.evaluate(ai_analysis, indices_data)

    

    # CIO 进行最终决策
    cio_engine = CIO(
        api_key=settings['api_key'], 
        base_url=settings.get('base_url'),
        proxy_config=settings.get('proxy')
    )
    final_decision = cio_engine.arbitrate(
        ai_analysis,
        risk_report,
        indices_data,
        draft_trade_list
    )

    # [Phase 6] 保存今日共识，供明日参考
    context_loader.save_consensus(today_str, final_decision)

    # 生成最终 AI 报告
    ai_report_path = f"reports/{today_str}_AI_Advisor.md"
    valid_date = next((item.get('date') for item in indices_data if item.get('date')), today_str)
    with open(ai_report_path, "w", encoding="utf-8") as f:
        f.write(f"> ⚠️ 数据基准日期: {valid_date}\n")
        f.write(f"> 🧠 记忆模块: 已加载最近 3 天决策 + 最近 10 笔真实交易\n\n")
        
        f.write("## 🧠 CIO 最终决策\n")
        f.write(final_decision)

        f.write(f"\n\n---\n## 基金经理看法\n")
        f.write(ai_analysis)

        f.write("\n\n---\n## 🛑 首席风控官 (红军) 审查结论\n")
        f.write(risk_report)


        f.write(f"## 🔍 基金经理看法\n{ai_analysis}\n\n")
        f.write(ai_analysis)

        f.write("\n\n---\n## 🛑 首席风控官审查结论\n")
        f.write(risk_report)

        f.write("\n\n---\n## 附录：今日参考快讯\n")
        f.write("\n".join([f"- {n}" for n in real_news[:10]]))

    # [Task 3] 同步 AI 报告到 Obsidian
    obsidian_sync.archive_daily_report(ai_report_path)

    # =====================================================================
    # [Task 4] 记录今日总资产净值，并在终端展示近一周收益
    # =====================================================================
    tracker = PerformanceTracker()
    current_total_nav = portfolio_status.get('total_assets', 0.0)
    tracker.record_nav(current_total_nav)
    weekly_ret = tracker.get_weekly_return()
    logging.info(f"📈 OS 近一周累计收益评估: {weekly_ret}")

    # =====================================================================
    # [Task 2 & 3] 定量调仓引擎与终端确认 (Human-in-the-loop)
    # =====================================================================
    # 1. 此时 final_trades 已经通过 CIO 的 JSON 解析提取出来了
    # 如果 final_trades 为空（CIO 没操作），则无需执行；如果不为空，执行 final_trades

    final_trades = []
    json_match = re.search(r'```json\s*(.*?)\s*```', final_decision, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
        try:
            final_trades = json.loads(json_str)
        except json.JSONDecodeError as e:
            logging.error(f"❌ JSON 解析错误: {e}")

    if final_trades:
        print("\n" + "!" * 60)
        print("⚖️ [CIO 最终裁决执行清单] - 只有出现在此清单中的才会被执行")
        print("!" * 60)
        
        for t in final_trades:
            # 颜色标记
            color_action = "\033[91m[买入]\033[0m" if t['action'] == "BUY" else "\033[92m[卖出]\033[0m"
            print(f"{color_action} {t['symbol']} | 份额: {t['shares']} | 理由: {t['reason']}")
            
        print("-" * 60)
        
        # 拦截终端确认
        exec_mode = strategy_config.get('portfolio_structure', {}).get('execution_mode', 'confirm')
        if exec_mode == 'auto':
            print("🚀 系统处于 AUTO 模式，正在自动执行 CIO 裁决清单...")
            res_msg = trans_mgr.execute_batch(final_trades) # 必须使用 final_trades
            print(res_msg)
        else:
            choice = input("⚠️ 是否一键执行上述 AI 裁决清单？(y/n): ").strip().lower()
            if choice == 'y':
                res_msg = trans_mgr.execute_batch(final_trades) # 必须使用 final_trades
                print(res_msg)
                print("📝 记得前往真实的券商 APP 中完成对应的交易动作！")
            else:
                print("❌ 已放弃本次调仓操作。")
    else:
        print("\n✅ CIO 决策结论：当前无需进行任何调仓操作 (清单为空)。")

    logging.info("=" * 50)
    logging.info(f"✅ 核心流程完成。")
    logging.info(f"📄 简报: {brief_path}")
    logging.info(f"🧠 决策: {ai_report_path}")
    if obsidian_sync.is_active:
        logging.info(f"🔗 Obsidian 同步: 已推送到 {obsidian_sync.dashboard_dir}")
    logging.info("=" * 50)

    # 5. [Task 2 & Task 3] 交互式终端 (指令 + 对话)
    print("\n" + "*" * 60)
    print("🤖 [Agent 操作系统已就绪]")
    print("您可以：")
    print("1. 💬 直接提问 (例如：'结合今天的量能情况，点评一下恒生科技')")
    print("2. ⚡ 执行交易 (例如：'/buy 016452 1000 1.25' 或 '/deposit 5000')")
    print("*" * 60)
    
    while True:
        try:
            user_input = input("\n👤 指令/追问 (q退出) > ").strip()
            
            if user_input.lower() in ['q', 'quit', 'exit']:
                print("👋 系统关闭。Keep compounded.")
                break
            
            if not user_input:
                continue
            
            # === [Task 2] 交易指令拦截 ===
            if user_input.startswith("/"):
                print("⚡ 正在处理交易指令...")
                result = trans_mgr.execute_command(user_input)
                print(result)
                
                # 如果交易成功（返回包含 ✅），则生成 Obsidian 交易单
                if "✅" in result:
                    # 解析简单的动作和标的，用于文件名
                    try:
                        parts = user_input.split()
                        action = parts[0].replace("/", "").upper()
                        symbol = parts[1] if len(parts) > 1 else "UNKNOWN"
                        shares = float(parts[2]) if len(parts) > 2 else 0
                        price = float(parts[3]) if len(parts) > 3 else 0
                        
                        # [Task 3] 生成交易单并同步
                        obsidian_sync.create_trade_journal(
                            action=action, 
                            symbol=symbol, 
                            shares=shares, 
                            price=price, 
                            context=f"用户通过终端直接执行。\nAI 最新分析观点参考: {ai_report_path}"
                        )
                    except:
                        pass # 格式解析失败不影响交易结果打印
                continue

            # === [Task C] 顾问追问模式 ===
            print("🧠 顾问思考中...")
            answer = advisor.chat(user_input)
            print(f"\n🤖 顾问回答:\n{answer}")
            
        except KeyboardInterrupt:
            print("\n👋 强制退出。")
            break
        except Exception as e:
            logging.error(f"运行时异常: {e}")

if __name__ == "__main__":
    if not os.path.exists("reports"): os.makedirs("reports")
    if not os.path.exists("data"): os.makedirs("data")
    run_investment_agent()
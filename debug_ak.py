# tests/test_phase5_logic.py

import os
import yaml
import json
import logging
from openai import OpenAI
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ==========================================
# 1. 极限测试数据构造 (Mock Data)
# ==========================================
# 场景：纳指大跌(宏观恶化)，黄金飙升(避险升温)，但恒生科技表面上KDJ超买(诱多陷阱)
MOCK_MARKET_DATA =[
    {"name": "纳斯达克100", "symbol": "us.NDX", "type": "us_index", "close": 23500.0, "change_pct": -2.85, 
     "indicators": {"MA20": 24000.0, "RSI": 35.0, "MACD": "死叉", "Bollinger": "Lower", "K": 15.0, "ATR": 350.5}},
    {"name": "标普500", "symbol": "us.INX", "type": "us_index", "close": 6500.0, "change_pct": -1.90, 
     "indicators": {"MA20": 6650.0, "RSI": 40.0, "MACD": "死叉", "Bollinger": "Lower", "K": 22.0, "ATR": 85.0}},
    {"name": "恒生科技ETF", "symbol": "sh513130", "type": "etf", "close": 0.720, "change_pct": 1.50, 
     "indicators": {"MA20": 0.680, "RSI": 75.0, "MACD": "金叉", "Bollinger": "Upper", "K": 88.5, "ATR": 0.025}},
    {"name": "博时黄金C", "symbol": "002611", "type": "otc_fund", "close": 3.850, "change_pct": 2.10, 
     "indicators": {"MA20": 3.700, "RSI": 82.0, "MACD": "金叉", "Bollinger": "Upper", "K": 91.0, "ATR": 0.040}}
]

MOCK_PORTFOLIO = {"strategy": "稳健偏长线", "holdings": [{"name": "恒生科技ETF", "weight": "40%"}]}

# ==========================================
# 2. 蓝军：升级版 Advisor 原型
# ==========================================
class Phase5_Advisor:
    def __init__(self, api_key, base_url, proxy_config):
        client_args = {"api_key": api_key, "base_url": base_url}
        if proxy_config and proxy_config.get('llm_use_proxy', False):
            client_args["http_client"] = httpx.Client(proxy=proxy_config.get('http_url'))
        self.client = OpenAI(**client_args)

    def analyze(self, market_data):
        #[Phase 5 核心：宏观跨市场映射与新指标 Prompt]
        system_prompt = """
        你是资深基金经理(蓝军)。请基于技术面、估值与【全球宏观共振逻辑】进行分析。
        
        【Phase 5 强制逻辑挂载】：
        1. 跨市场映射：分析港股/科技股时，必须严格比对纳斯达克100(us.NDX)的涨跌。如果纳指暴跌，科技股的上涨大概率是诱多。
        2. 避险情绪侦测：如果全球指数下跌，而黄金(Gold)逆势大涨并触及布林带上轨，说明全球资金正在疯狂避险(Risk-Off)。
        3. 极端指标警报：如果 KDJ 的 K 值 > 80 (超买)，即使 MACD 金叉，也不建议追高；ATR 放大的标的意味着波动加剧，需控制仓位。
        
        请简要输出：1.大势定调(结合中美+黄金) 2.恒生科技的诊断建议。
        """
        logging.info("🧠 [蓝军] Advisor 正在思考...")
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(market_data, ensure_ascii=False)}
            ], temperature=0.3
        )
        return response.choices[0].message.content

# ==========================================
# 3. 红军：全新 Risk Officer 原型
# ==========================================
class Phase5_RiskOfficer:
    def __init__(self, api_key, base_url, proxy_config):
        client_args = {"api_key": api_key, "base_url": base_url}
        if proxy_config and proxy_config.get('llm_use_proxy', False):
            client_args["http_client"] = httpx.Client(proxy=proxy_config.get('http_url'))
        self.client = OpenAI(**client_args)

    def evaluate(self, advisor_report, market_data):
        system_prompt = """
        # Role: 首席风控官 (Red Team)
        你是一个极其悲观、极度厌恶风险的对冲基金风控官。你的天职是【反驳与挑刺】基金经理(Advisor)的乐观或中性建议。

        # Workflow:
        1. 审查 Advisor 的报告。
        2. 扫描数据中的致命弱点：例如 KDJ 超买(>80)、ATR 波动率剧增、均线偏离度过大、美股宏观负面溢出。
        3. 无论 Advisor 怎么说，你都要找出不买/减仓的理由。

        # Output Format:
        必须使用 Markdown 且严格包含以下三个标题：
        ### ⚠️ 风险点挖掘
        (指出 KDJ/ATR/布林带等技术面被忽略的隐患)
        ### 🌍 宏观干扰
        (强制联系纳指暴跌、黄金避险对目标标的的负面影响)
        ### 🛑 一票否决理由
        (给出 1-2 条强烈建议观望或减仓的毒舌理由)
        """
        logging.info("🦅 [红军] Risk Officer 正在审查报告并寻找漏洞...")
        response = self.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"【市场数据】\n{json.dumps(market_data, ensure_ascii=False)}\n\n【Advisor 初版报告】\n{advisor_report}"}
            ], temperature=0.4
        )
        return response.choices[0].message.content

# ==========================================
# 4. 报告排版分离原型 (UI Refactoring)
# ==========================================
def generate_split_tables(market_data):
    macro_list =[d for d in market_data if d['type'] in ['index', 'us_index']]
    micro_list =[d for d in market_data if d['type'] in ['etf', 'otc_fund', 'stock']]
    
    def render_row(d):
        k = d['indicators'].get('K', 50)
        k_str = f"🔥 {k}" if k > 80 else (f"❄️ {k}" if k < 20 else str(k))
        return f"| {d['name']} | {d['change_pct']}% | {d['indicators'].get('MACD')} | {k_str} | {d['indicators'].get('Bollinger')} |"

    print("\n" + "="*50)
    print("📊 【表1】全球宏观与宽基阵列")
    print("| 名称 | 涨跌幅 | MACD | KDJ(K值) | 布林带 |")
    print("|---|---|---|---|---|")
    for d in macro_list: print(render_row(d))
    
    print("\n📊 【表2】微观持仓与行业资产")
    print("| 名称 | 涨跌幅 | MACD | KDJ(K值) | 布林带 |")
    print("|---|---|---|---|---|")
    for d in micro_list: print(render_row(d))
    print("="*50 + "\n")

# ==========================================
# 5. 执行测试流程
# ==========================================
def run_test():
    # 读取配置
    try:
        with open("config/settings.yaml", "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ 无法读取配置文件: {e}")
        return

    # 1. 展示分离后的UI表单
    generate_split_tables(MOCK_MARKET_DATA)

    # 2. 蓝军出击
    advisor = Phase5_Advisor(settings['api_key'], settings.get('base_url'), settings.get('proxy'))
    adv_report = advisor.analyze(MOCK_MARKET_DATA)
    print("📘 【蓝军 (Advisor) 研报】\n" + adv_report + "\n")

    # 3. 红军审查
    officer = Phase5_RiskOfficer(settings['api_key'], settings.get('base_url'), settings.get('proxy'))
    risk_report = officer.evaluate(adv_report, MOCK_MARKET_DATA)
    print("📕 【红军 (Risk Officer) 审查结论】\n" + risk_report + "\n")

if __name__ == "__main__":
    run_test()
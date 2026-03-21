# src/core/risk_officer.py

from openai import OpenAI
import httpx
import logging
import json

class RiskOfficer:
    """
    首席风控官 (红军)：负责对 Advisor 的乐观报告进行无情反驳与风险挖掘。
    [Phase 5 新增]
    """

    def __init__(self, api_key, base_url="https://api.deepseek.com", proxy_config=None):
        self.model = "deepseek-chat"
        
        # 复用 Phase 4.5 的网络解耦逻辑
        client_args = {"api_key": api_key, "base_url": base_url}
        if proxy_config and proxy_config.get('llm_use_proxy', False):
            proxy_url = proxy_config.get('http_url')
            if proxy_url:
                logging.info(f"🛡️ [风控网络层] 已显式挂载指定代理: {proxy_url}")
                client_args["http_client"] = httpx.Client(proxy=proxy_url)
                
        self.client = OpenAI(**client_args)

    def evaluate(self, advisor_report: str, market_data: list) -> str:
        """
        审查 Advisor 的报告并输出反驳意见
        """
        market_data_str = json.dumps(market_data, ensure_ascii=False, indent=2)
        
        system_prompt = """
        # Role: 首席风控官 (Red Team)
        你是一个极其悲观、极度厌恶风险的华尔街对冲基金风控官。你的天职是充当“红军”，对基金经理 (Advisor) 提出的任何乐观或中性建议进行**极其刻薄、基于数据的量化反驳**。
        **【最高语气指令】**：
        你没有情绪，只有纪律。禁止任何客套话、前言或总结（如“Advisor的报告看似全面...”）。报告必须像法医鉴定书一样冷酷，直插敌人的逻辑致命伤。

        # Workflow & Attack Strategy (攻击策略)
        你需要仔细扫描 Advisor 的报告，寻找以下致命弱点进行精准狙击：
        1. **猎杀“技术面诱多”**：
           - Advisor 看到金叉就乐观？你必须检查是否处于 MA20 下方的“假金叉”（死猫跳）。
           - Advisor 觉得 RSI 正常？你必须用 KDJ 的 J值(>100) 或 K值(>80) 狠狠打脸，指出其随时可能崩盘。
           - Advisor 认为上涨健康？你必须检查 ATR/Price 比率，若异常放大，指出这是“拉高出货、筹码松动”。
        2. **摧毁“定投/低吸”借口**：
           - 如果 Advisor 以“核心定投池”为借口建议在暴跌时低吸，你必须审查：是否缩量？是否形成底背离？如果跌势未竭，痛斥其为“在下落的铡刀下捡硬币”。
        3. **引爆“宏观核弹”**：
           - 用美股暴跌、VIX 飙升或美债收益率（>4.0%）对所有 A 股/港股的科技成长股进行估值降维打击。

        # Quantitative Redlines (量化红线)
        - **KDJ 警报**：若 K > 80 且 J > 100，必须强制建议停止一切追高。
        - **背离警报**：若价格新高但 MACD 动能减弱，必须指出这是“诱多陷阱”。
        - **ATR 警报**：若 ATR/Price > 3%，必须指出这是“筹码松动”，建议分批撤离。
        - **宏观压制**：美债收益率 > 4.0% 时，对所有 PE > 30 的标的一票否决其乐观预期。

        # Output Format:
        必须使用 Markdown 且严格包含以下三个标题：
        ### ⚠️ 风险点挖掘
        *(要求：必须是 1. 2. 3. 的列表格式。每一条必须包含至少一个具体的技术指标数据（如 K值、ATR、MACD等）作为武器，逐个反驳 Advisor 对持仓标的的盲目乐观。)*
        ### 🌍 宏观干扰
        *(要求：必须将今日的宏观新闻（美股大跌、地缘冲突、美债）直接且粗暴地绑定到 Advisor 推荐持仓的负面影响上。解释宏观毒药是如何传导的。)*
        ### 🛑 一票否决理由
        (给出 1-2 条强烈建议观望或减仓的毒舌理由)
        """

        user_prompt = f"""
        【市场原始数据】
        {market_data_str}

        【Advisor 初版报告】
        {advisor_report}
        """

        try:
            logging.info("🦅 首席风控官正在审查报告并寻找致命漏洞...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4, # 保持一定的发散性以寻找刁钻角度
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"风控官连接失败: {e}")
            return "审查失败：风控官连接超时。"
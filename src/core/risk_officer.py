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

        # Dynamic Quantitative Redlines (动态量化红线 - 严禁绝对值教条)
        1. **【体制依赖的 KDJ 警报】**：绝对禁止看到 K>80 就无脑看空！你必须结合数据中该标的专属的【Regime】。
           - 若该标的处于 Bear/Panic/Correction，RSI>60 即为逃顶信号，狠狠狙击 Advisor 的贪婪。
           - 若处于 Aggressive Bull，K>80 是资金强劲的“高位钝化”特征。只有当价格“跌破MA20”或“MACD顶背离”时，才允许拉响高位诱多警报。
        2. **【相对波动率警报】**：摒弃绝对数值。仔细查看数据中的 ATR 描述。如果标的处于 Shock 震荡市，高波动意味着筹码松动；如果在 Aggressive Bull 的初期，放量高波动是突破的标志。
        3. **【顺势宏观压制】**：不再死守美债 4.0% 绝对值。若美债高企，且该资产的 Regime 已走弱（转为 Correction 或 Bear），则果断判定宏观毒药发作，一票否决；若该资产仍处于 Aggressive Bull（价格包容一切），则收起你的宏观说教，尊重市场趋势。

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
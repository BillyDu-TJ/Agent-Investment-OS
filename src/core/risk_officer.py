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
        你是一个极其悲观、极度厌恶风险的对冲基金风控官。你的天职是【反驳与挑刺】基金经理(Advisor)的乐观或中性建议。

        # Workflow:
        1. 审查 Advisor 的报告。
        2. 扫描数据中的致命弱点：例如 KDJ 超买(>80)、ATR 波动率剧增、均线偏离度过大、美股宏观负面溢出。
        3. 无论 Advisor 怎么说，你都要找出不买/减仓的理由。

        # Quantitative Redlines (量化红线)
        - **KDJ 警报**：若 K > 80 且 J > 100，必须强制建议停止一切追高。
        - **背离警报**：若价格新高但 MACD 动能减弱，必须指出这是“诱多陷阱”。
        - **ATR 警报**：若 ATR/Price > 3%，必须指出这是“筹码松动”，建议分批撤离。
        - **宏观压制**：美债收益率 > 4.0% 时，对所有 PE > 30 的标的一票否决其乐观预期。

        # Output Format:
        必须使用 Markdown 且严格包含以下三个标题：
        ### ⚠️ 风险点挖掘
        (指出 KDJ/ATR/布林带等技术面被忽略的隐患)
        ### 🌍 宏观干扰
        (强制联系纳指暴跌、黄金避险等对目标标的的负面影响)
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
# src/core/cio.py

from openai import OpenAI
import httpx
import logging
import json

class CIO:
    """
    首席投资官 (Chief Investment Officer)：
    负责仲裁 Advisor 和 RiskOfficer 的冲突，给出最终的仓位分配建议。
    """

    def __init__(self, api_key, base_url="https://api.deepseek.com", proxy_config=None):
        self.model = "deepseek-chat"
        client_args = {"api_key": api_key, "base_url": base_url}
        if proxy_config and proxy_config.get('llm_use_proxy', False):
            proxy_url = proxy_config.get('http_url')
            if proxy_url:
                client_args["http_client"] = httpx.Client(proxy=proxy_url)
        self.client = OpenAI(**client_args)

    def arbitrate(self, advisor_report, risk_report, market_data):
        system_prompt = """
        # Role: 首席投资官 (CIO)
        你是一个冷静、理性的对冲基金合伙人。你的任务是审查基金经理(Advisor)的投资建议和风控官(Risk Officer)的反驳意见。

        # 仲裁逻辑 (Arbitration Logic):
        1. **寻找共识**：如果两人都建议卖出，立即执行清仓。
        2. **处理冲突**：
           - 若 Advisor 极其乐观但 Risk Officer 提出了严重的【底背离/超买/波动率】警告，你必须采取“保守加仓”策略（即：加仓量减半，分批入场）。
           - 若 Risk Officer 提出一票否决，你必须重新评估该标的的【ATR 波动率】。如果 ATR 确实在放大，支持风控官。
        3. **仓位管理**：
           - 任何时候，如果 KDJ > 80，严禁单笔满仓。
           - 若市场体制 (Regime) 处于 Aggressive Bull，可以容忍风控官提到的部分超买，但必须设立硬性止损线。

        # 输出要求：
        使用 Markdown 格式，必须包含以下章节：
        ### ⚖️ 终审决策摘要
        (一句话总结：是激进、中性还是保守？)
        ### 📊 最终操作指令表
        | 标的 | 指令 | 执行比例/仓位 | 逻辑简述 | 止损/触发点 |
        | :--- | :--- | :--- | :--- | :--- |
        ### 🛡️ 强制执行红线
        (针对 Risk Officer 提出的致命点，给出一个具体的硬性退出条件)
        """

        user_prompt = f"""
        【基金经理分析建议】
        {advisor_report}

        【风控官审查报告】
        {risk_report}

        【市场参考数据】
        {json.dumps(market_data, ensure_ascii=False)}
        """

        try:
            logging.info("⚖️ CIO 正在进行投资委员会终审仲裁...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1, # 极低随机性，确保决策稳健
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"CIO 决策失败: {e}")
            return "仲裁失败：投资委员会无法达成一致。"
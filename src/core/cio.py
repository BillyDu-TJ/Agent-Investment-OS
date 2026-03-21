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

    def arbitrate(self, advisor_report, risk_report, market_data, draft_trade_list):
        system_prompt = """
        # Role: 首席投资官 (CIO)
        你是一个极其冷静、理智且大权在握的华尔街量化对冲基金合伙人。你的任务是审查基金经理 (Advisor) 的投资建议与风控官 (Risk Officer) 的反驳意见，并下达最终交易指令。
        **【最高语气与身份指令】**：
        你就是这里的最高决策者。**绝对禁止**任何形式的自我介绍、开场白或客套话（绝不允许出现“好的，首席投资官”、“我已审阅完毕”、“现在做出裁决”等机器废话）。

        # 仲裁逻辑 (Arbitration Logic):
        1. **寻找共识**：如果两人都建议卖出，立即执行清仓。
        2. **处理冲突**：
           - 若 Advisor 极其乐观但 Risk Officer 提出了严重的【底背离/超买/波动率】警告，你必须采取“保守加仓”策略（即：加仓量减半，分批入场）。
           - 若 Risk Officer 提出一票否决，你必须重新评估该标的的【ATR 波动率】。如果 ATR 确实在放大，支持风控官。
           - **【针对波段/卫星资产】**：只要 Risk Officer 提出了【跌破均线 / MACD死叉 / ATR剧增】的明确数据警告，你必须**无条件支持风控官**。打碎 Advisor 的任何侥幸心理，强制止损清仓。
           - **【针对定投/核心资产】**：若 Advisor 基于定投纪律建议“越跌越买/低吸”，而 Risk Officer 提示技术面极度危险。你必须审查【宏观数据】：若美债收益率>4.0%或发生极端黑天鹅，宏观一票否决，打破定投纪律，强制清仓；若仅为技术面大跌，你应**“和稀泥”**（支持 Advisor 保留底仓的纪律，但采纳风控官意见，禁止当日加仓）。
        3. **仓位管理**：
           - 任何时候，如果 KDJ > 80，严禁单笔满仓。
           - 若市场体制 (Regime) 处于 Aggressive Bull，可以容忍风控官提到的部分超买，但必须设立硬性止损线。
           - 必须计算 [目标仓位%] - [当前仓位%] = [操作比例]。
           - 必须基于该比例和总资产，精确折算出 [需交易股数]。
           - 若风控官红线被触碰，CIO 必须强制将 Advisor 的目标仓位调低 50%。


        # 输出要求：
        使用 Markdown 格式，必须包含以下章节：
        ### ⚖️ 终审决策摘要
        (一句话总结：是激进、中性还是保守？)
        ### 📊 最终操作指令表
        | 标的 | 指令 | 执行比例/仓位（精确到股数或金额） | 逻辑简述 | 止损/触发点 |
        | :--- | :--- | :--- | :--- | :--- |
        ### 🛡️ 强制执行红线
        *(要求：以 Bullet points 形式，列出 1-3 条你做出上述裁决的核心依据。特别标明在 Advisor 和 Risk Officer 发生分歧时，你为什么判定某一方获胜。必须引用具体的数据指标。)*
        ### 最终裁决结果
        在 Markdown 报告分析后，必须在最后提供一个独立的 JSON 代码块，作为你的最终裁决结果。如果无需操作，请输出空列表 []。
        格式：
        ```json
        [
            {"symbol": "sh513130", "action": "BUY", "shares": 1000, "reason": "理由"},
            {"symbol": "016452", "action": "SELL", "shares": 50, "reason": "理由"}
        ]
        ```
        """

        user_prompt = f"""
        【数学调仓草案 (Rebalancer)】
        {json.dumps(draft_trade_list, ensure_ascii=False)}

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
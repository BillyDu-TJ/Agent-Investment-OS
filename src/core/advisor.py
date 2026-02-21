# src/core/advisor.py

from openai import OpenAI
import logging
import json

class InvestmentAdvisor:
    """
    硅基大脑：负责整合 技术面(Technical) + 估值面(Fundamental) + 消息面(News) 进行多维决策。
    """

    def __init__(self, api_key, base_url="https://api.deepseek.com"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat" 

    def analyze(self, market_data, portfolio_data, macro_news, regime_info):
        """
        整合多维数据调用 LLM 进行分析
        market_data: 包含 K线技术指标 AND 估值数据(PE/PB)
        """

        regime_status = regime_info[0]  # Bull / Bear / Shock
        regime_desc = regime_info[1]

        # 将 market_data 转换为 JSON 字符串，方便 LLM 阅读结构化数据
        market_data_str = json.dumps(market_data, indent=2, ensure_ascii=False)

        # 构建 System Prompt (决策逻辑定义 - V3.0 估值增强版)
        system_prompt = f"""
        # Role
        你是一位精通“价值投资”与“趋势跟踪”双重体系的资深基金经理。你不仅看重技术面的买卖点，更看重资产的内生价值（估值安全边际）。

        # Context (当前市场体制)
        - 状态: **[{regime_status}]**
        - 描述: {regime_desc}

        # Decision Framework (决策框架)
        请基于以下三个维度进行综合研判（权重：估值40% + 技术40% + 宏观20%）：

        1. **Valuation (估值面)**：
           - 你会看到每个标的的 `valuation` 字段，包含 `pe` (市盈率) 和 `pb` (市净率)。
           - **请调动你的金融常识库**：判断该数值对于该行业（如券商、科技、白酒）是处于历史高位、中位还是低位？
           - *规则*：若 PE/PB 处于极低位，即使技术面走弱，也应考虑“左侧布局”或“定投积累”；若处于极高位，即使技术面金叉，也要警惕“估值杀”。
           - *注意*：若估值数据为 None，则降级为仅依据技术面和新闻决策。

        2. **Technical (技术面)**：
           - 关注 `signal_summary` (如均线得失、RSI超买超卖)。
           - 关注 `MACD` 金叉/死叉信号。
           - *规则*：在[Bear/熊市]中，技术压力位（均线压制）通常是减仓点；在[Bull/牛市]中，技术超买可适当容忍。

        3. **Intent (用户意图)**：
           - 检查 `portfolio_data` 中的 `strategy` (策略) 和 `term` (周期)。
           - **长线(Long/DCA)**：更看重估值便宜；**短线(Short/Swing)**：更看重技术趋势爆发。

        # Thinking Path (思维链)
        在输出前，请按步骤思考：
        Step 1: 这个标的现在贵吗？(看 PE/PB) -> 确定安全边际。
        Step 2: 现在的趋势是向上的吗？(看 MA/MACD) -> 确定入场时机。
        Step 3: 结合当前的市场体制(Regime)，我应该激进还是保守？

        # Output Format
        使用 Markdown 格式，输出一份严谨的投资报告：
        1. **【大势定调】**：基于 Regime 和宏观新闻的整体判断。
        2. **【个股/ETF 深度诊断】** (重点)：
           - 逐个分析持仓。
           - **必须明确写出**：当前 PE/PB 水平及其对应的历史位置评价（例如：“当前PE 16.5，位于券商板块历史低位区间...”）。
           - 结合技术面给出结论。
        3. **【操作指令摘要】**：表格或清单形式，给出最终建议（加仓/减仓/持有/观望）。
        """

        # 构建 User Prompt (注入实时数据)
        user_prompt = f"""
        请根据以下多维数据生成今日决策：

        === 1. 宏观面 (News) ===
        {macro_news}

        === 2. 市场与估值数据 (Market & Valuation) ===
        {market_data_str}

        === 3. 账户与策略 (Portfolio) ===
        {portfolio_data}
        """

        try:
            logging.info("正在调动硅基大脑进行 [技术+估值] 双维分析...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2, # 估值分析需要理性，降低随机性
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"硅基大脑连接失败: {e}")
            return "分析失败：大脑连接超时，请检查 API Key 或网络设置。"
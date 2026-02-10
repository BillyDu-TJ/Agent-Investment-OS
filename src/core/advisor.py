# src/core/advisor.py

from openai import OpenAI
import logging
import os

class InvestmentAdvisor:
    """
    硅基大脑：负责整合所有信息并给出决策建议。
    """

    def __init__(self, api_key, base_url="https://api.deepseek.com"):
        # 初始化 OpenAI 客户端 (适配 DeepSeek)
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat" # 或者使用 "gpt-3.5-turbo" / "gpt-4"

    def analyze(self, market_data, portfolio_data, macro_news, regime_info):
        """
        整合数据,结合市场体制(Regime)和用户意图(Intent)调用 LLM 进行分析
        """

        regime_status = regime_info[0]  # Bull / Bear / Shock
        regime_desc = regime_info[1]

        # 构建 System Prompt (决策逻辑定义)
        system_prompt = f"""
        # Role
        你是一位理性、专业、且具备深度心理洞察力的私人投资顾问。

        # Market Context
        当前市场体制为: **[{regime_status}]**
        体制描述: {regime_desc}

        # Strategic Rules
        1. **体制优先原则**：
           - 在 [Bear] 熊市中：即使技术面反弹，也要警惕“诱多”。对于[定投/长线]资产，建议减量定投或持币观望；对于[短线/波段]资产，严格执行止损。
           - 在 [Bull] 牛市中：容忍短期震荡。建议“让利润奔跑”，适当放宽止损位。
           - 在 [Shock] 震荡中：强调高抛低吸，不追涨杀跌。

        2. **意图一致性核查**：
           - 你必须检查用户的 [strategy] 和 [term]。
           - 如果是 [dca/定投]，其核心逻辑是“低位攒份额”，死叉不一定是卖点，反而可能是买点，除非体制显示系统性崩盘。
           - 如果是 [swing/波段]，其核心逻辑是“趋势”，一旦破位必须果断退出，无论用户主观多么看好。

        # Thinking Path (CoT)
        在输出建议前，请在心中执行以下逻辑链路：
        Step 1: 这里的市场体制对整体风险偏好有什么限制？
        Step 2: 用户的每项持仓，其技术信号是否违背了用户的初始意图（strategy）？
        Step 3: 如果技术信号、市场体制、用户意图三者发生冲突，你的权衡逻辑是什么？

        # Output Format
        使用 Markdown 格式，包含：
        - 【大势定调】：基于 Regime 的整体判断。
        - 【持仓诊断】：逐一分析资产。**必须包含“意图检查”小节**。
        - 【决策指令】：明确的操作建议（买入/卖出/持有/补仓/止损）。
        """

        # 构建 User Prompt (注入实时数据)
        user_prompt = f"""
        请根据以下数据进行分析：

        【宏观新闻】
        {macro_news}

        【市场指数数据】
        {market_data}

        【当前账户状态】
        {portfolio_data}
        """

        try:
            logging.info("正在调动硅基大脑进行深度博弈分析...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3, # 降低随机性，增加理性
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"硅基大脑连接失败: {e}")
            return "分析失败：大脑连接超时，请检查 API Key 或网络设置。"
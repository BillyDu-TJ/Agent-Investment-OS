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

    def analyze(self, market_data, portfolio_data, macro_news):
        """
        整合数据并调用 LLM 进行分析
        """
        # 构建 System Prompt (决策逻辑定义)
        system_prompt = """
        你是一位专业、冷静、风险厌恶型的私人投资顾问。
        你的任务是根据提供的[市场数据]、[用户持仓]和[宏观新闻]，为用户提供深度分析和操作建议。

        请遵循以下思考路径 (Chain of Thought):
        1. 宏观定调：分析新闻，判断当前环境是适合进攻（加仓）还是防御（减仓/持币）。
        2. 技术校验：观察市场指数的 RSI、MACD 和均线，判断趋势是否支持你的宏观判断。
        3. 账户诊断：检查用户持仓的盈亏、仓位占比。判断是否存在仓位过重或需要止损的标的。
        4. 最终博弈：如果宏观与技术面冲突（如宏观好但技术面破位），请说明你的权衡逻辑。

        输出要求：
        - 必须使用 Markdown 格式。
        - 必须包含“核心观点”、“详细分析”和“操作建议”三个章节。
        - 操作建议必须明确（买入、卖出、持有、调仓），并说明理由。
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
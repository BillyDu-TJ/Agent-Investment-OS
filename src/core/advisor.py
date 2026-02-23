# src/core/advisor.py

from openai import OpenAI
import logging
import json

class InvestmentAdvisor:
    """
    硅基大脑：负责整合 技术面(Technical) + 估值面(Fundamental) + 消息面(News) 进行多维决策。
    [Phase 4 升级]: 具备读取历史上下文的能力，保持决策的连贯性。
    """

    def __init__(self, api_key, base_url="https://api.deepseek.com"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat" 
        self.chat_history = [] 

    # === [Task 1 修改] 增加 historical_context 入参 ===
    def analyze(self, market_data, portfolio_data, macro_news, regime_info, historical_context="无历史记录。"):
        """
        整合多维数据调用 LLM 进行分析
        """

        regime_status = regime_info[0]  
        regime_desc = regime_info[1]

        market_data_str = json.dumps(market_data, indent=2, ensure_ascii=False)

        # 构建 System Prompt (决策逻辑定义)
        system_prompt = f"""
        # Role
        你是一位精通“价值投资”与“趋势跟踪”双重体系的资深基金经理。你不仅看重技术面的买卖点，更看重资产的内生价值（估值安全边际）。

        # Context (当前市场体制)
        - 状态: **[{regime_status}]**
        - 描述: {regime_desc}

        # Historical Memory (过去3天的决策连贯性锚点)
        以下是你过去几天的诊断和决策记录。请你在今天做决策时，务必参考这些记忆。
        如果过去几天建议“定投加仓”，且今天逻辑未变，请保持连贯；如果发生了趋势逆转，请说明为何改变主意。
        {historical_context}

        # Decision Framework (决策框架)
        请基于以下三个维度进行综合研判（权重：估值40% + 技术40% + 宏观20%）：

        1. **Valuation (估值面)**：
           - 你会看到每个标的的 `valuation` 字段，包含 `pe` (市盈率) 和 `pb` (市净率)。
           - **请调动你的金融常识库**：判断该数值对于该行业（如券商、科技、白酒）是处于历史高位、中位还是低位？
           - *规则*：若 PE/PB 处于极低位，即使技术面走弱，也应考虑“左侧布局”或“定投积累”；若处于极高位，即使技术面金叉，也要警惕“估值杀”。
           - *注意*：若估值数据为 None，则降级为仅依据技术面和新闻决策。

        2. **Technical (技术面与微观结构)**：
           - 关注 `signal_summary` (如均线得失、MACD金叉/死叉)。
           - **[进阶] 量价配合 (Vol_Ratio)**：重点关注“放量上涨”(资金坚决流入) 和 “缩量下跌”(抛压衰竭)。若突破均线但属于“极致缩量”，需警惕假突破。
           - **[进阶] 布林带 (Bollinger)**：这是一个极值观察工具。若价格“触及布林上轨”且处于震荡市/熊市，往往是短期卖点；若在主升浪中触及上轨，则代表动能极强，不应轻易下车。
           - *规则*：在[Bear/熊市]中，技术压力位（均线压制）通常是减仓点；在[Bull/牛市]中，技术超买可适当容忍。

        3. **Intent (用户意图)**：
           - 检查 `portfolio_data` 中的 `strategy` (策略) 和 `term` (周期)。
           - **长线(Long/DCA)**：更看重估值便宜；**短线(Short/Swing)**：更看重技术趋势爆发。

        # Thinking Path (思维链)
        在输出前，请按步骤思考：
        Step 1: 记忆比对 -> 今天的技术走势对比昨天是增强了还是恶化了？
        Step 2: 这个标的现在贵吗？(看 PE/PB) -> 确定安全边际。
        Step 3: 现在的趋势是向上的吗？(看 MA/MACD) -> 确定入场时机。
        Step 4: 结合当前的市场体制(Regime)，我应该激进还是保守？

        # Output Format
        使用 Markdown 格式，输出一份严谨的投资报告：
        1. **【大势定调】**：基于 Regime 和宏观新闻的整体判断。
        2. **【个股/ETF 深度诊断】** (重点)：
           - 逐个分析持仓。
           - **必须明确写出**：当前 PE/PB 水平及其对应的历史位置评价（例如：“当前PE 16.5，位于券商板块历史低位区间...”）。
           - 结合技术面及【历史记忆】给出结论。
        3. **【操作指令摘要】**：表格或清单形式，给出最终建议（加仓/减仓/持有/观望）。
        """

        user_prompt = f"""
        请根据以下多维数据生成今日决策：

        === 1. 宏观面 (News) ===
        {macro_news}

        === 2. 市场与估值数据 (Market & Valuation) ===
        {market_data_str}

        === 3. 账户与策略 (Portfolio) ===
        {portfolio_data}
        """

        self.chat_history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            logging.info("正在调动硅基大脑进行 [记忆+技术+估值] 全维分析...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=0.2, 
            )
            answer = response.choices[0].message.content
            
            self.chat_history.append({"role": "assistant", "content": answer})
            
            return answer
        except Exception as e:
            logging.error(f"硅基大脑连接失败: {e}")
            return "分析失败：大脑连接超时，请检查 API Key 或网络设置。"

    def chat(self, user_query: str) -> str:
        """
        基于当前记忆池，回应用户的追问
        """
        self.chat_history.append({"role": "user", "content": user_query})
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=0.4, 
            )
            answer = response.choices[0].message.content
            self.chat_history.append({"role": "assistant", "content": answer})
            return answer
        except Exception as e:
            self.chat_history.pop()
            return f"思考中断，请重试。错误信息: {e}"
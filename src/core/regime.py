# src/core/regime.py

import pandas as pd
import numpy as np
import logging

class RegimeIdentifier:
    """
    市场体制识别器 (v2.0 Professional)：
    引入 [波动率过滤器] + [均线斜率] + [量能确认] 的多维状态机。
    拒绝单一维度的 MA200 误判。
    """

    def identify(self, df: pd.DataFrame):
        """
        判断体制：
        - Passive Bull (结构性慢牛): 价格 > MA200 & MA200斜率向上 & 低波动
        - Aggressive Bull (进攻性快牛): 均线多头排列 & 放量 & 动量强
        - Bear (结构性熊市): 价格 < MA200 & MA200斜率向下
        - Panic (恐慌/高波): ATR 剧烈放大，脱离基本面
        - Shock (震荡/磨底): MA200 走平，价格反复穿越
        """
        if df is None or len(df) < 20:
            return "Unknown", "数据不足(需至少20个交易日)，无法判断体制"

        try:
            # 1. 提取核心指标
            latest = df.iloc[-1]
            prev_20 = df.iloc[-20] # 用来计算月度斜率
            
            close = float(latest['收盘'])
            ma20 = float(latest.get('MA20', 0))
            ma60 = float(latest.get('MA60', 0))
            ma200 = float(latest.get('MA200', 0))
            atr = float(latest.get('ATR', 0))
            
            # 容错：如果 MA200 还没算出来（新股），降级逻辑
            if ma200 == 0 or pd.isna(ma200):
                return "Shock", "上市时间过短，暂无长期均线参考，按震荡市处理。"

            # 2. 计算关键金融衍生因子
            
            # A. 长期趋势斜率 (MA200 Slope)
            # 过去20天 MA200 的变化率。> 0 代表长期成本在抬升（真牛），< 0 代表长期成本在下降（真熊/反弹）
            ma200_slope = (ma200 - float(prev_20.get('MA200', ma200))) / float(prev_20.get('MA200', ma200))
            
            # B. 波动率压力 (Volatility Stress)
            # 当日 ATR / 价格。如果 > 3% 通常代表极度恐慌或顶部剧烈分歧
            vol_stress = atr / close 

            # C. 均线排列 (Alignment)
            is_bull_align = (ma20 > ma60 > ma200)
            is_bear_align = (ma20 < ma60 < ma200)

            # 3. 状态机判定 (优先级：恐慌 > 熊 > 牛 > 震荡)

            # --- State 1: Panic (高波恐慌) ---
            if vol_stress > 0.025: # 2.5% 的日波动率阈值
                status = "Panic"
                desc = f"⚠️ 极度恐慌状态！日内波动率(ATR)高达 {vol_stress:.1%}。市场情绪失控，任何技术指标均可能失效。建议：空仓观望或仅进行极小仓位博弈。"
            
            # --- State 2: Structural Bear (结构性熊市) ---
            elif is_bear_align or (close < ma200 and ma200_slope < -0.005):
                status = "Bear"
                desc = "📉 结构性熊市。长期均线(MA200)持续向下倾斜，任何反弹大概率是诱多。建议：严控仓位，多看少动，等待右侧信号。"

            # --- State 3: Aggressive Bull (主升浪/快牛) ---
            elif is_bull_align and close > ma20 and ma200_slope > 0:
                status = "Aggressive Bull"
                desc = "🚀 主升浪进攻态势。均线完美多头排列，且长期趋势向上。市场处于赚钱效应最强的阶段。建议：积极持股，逢低加仓，直到跌破 MA20。"

            # --- State 4: Passive Bull (慢牛/回踩) ---
            elif close > ma200 and ma200_slope > 0:
                status = "Passive Bull"
                desc = "🐂 结构性慢牛。虽然短期可能回调，但长期均线(MA200)依然向上支撑。这是“千金难买牛回头”的阶段。建议：关注 MA60 或 MA200 附近的低吸机会。"

            # --- State 5: Shock (震荡/猴市) ---
            else:
                status = "Shock"
                desc = f"⚖️ 宽幅震荡市。MA200 斜率({ma200_slope:.4f})趋平，价格无明显方向。此时追涨杀跌极其容易亏损。建议：启用网格策略，高抛低吸，拒绝格局。"

            return status, desc

        except Exception as e:
            logging.error(f"体制识别计算出错: {e}")
            return "Error", "计算模块异常，请检查数据完整性。"
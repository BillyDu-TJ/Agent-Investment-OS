# src/core/regime.py

import pandas as pd

class RegimeIdentifier:
    """
    市场体制识别器：基于均线排列客观判断市场所处的阶段。
    """

    def identify(self, df: pd.DataFrame):
        """
        判断体制：Bull (牛), Bear (熊), Shock (震荡)
        要求：df 必须包含 [收盘, MA20, MA60, MA200]
        """
        if df is None or len(df) < 1:
            return "Unknown", "数据不足，无法判断"

        # 获取最新的一行数据
        latest = df.iloc[-1]
        close = latest['收盘']
        ma20 = latest.get('MA20')
        ma60 = latest.get('MA60')
        ma200 = latest.get('MA200')

        # 检查必要指标是否存在
        if pd.isna(ma20) or pd.isna(ma60) or pd.isna(ma200):
            return "Shock", "均线计算中，暂按震荡市处理"

        # 逻辑判断（仅客观描述事实）
        # Bull (牛市): 收盘价 > MA200 且 MA20 > MA60
        if close > ma200 and ma20 > ma60:
            status = "Bull"
            desc = "长期均线支撑强劲，中短期均线呈现多头排列。市场处于进攻周期。"
        
        # Bear (熊市): 收盘价 < MA200 且 MA20 < MA60
        elif close < ma200 and ma20 < ma60:
            status = "Bear"
            desc = "长期均线压制明显，短期均线空头排列。市场处于防御周期。"
        
        # Shock (震荡): 其他情况
        else:
            status = "Shock"
            desc = "均线交织或价格在长均线附近摆动，大趋势不明。市场处于博弈周期。"

        return status, desc
# src/core/regime.py

import pandas as pd
import numpy as np
import logging

class RegimeIdentifier:
    """
    市场体制识别器 (v4.1 机构实盘版)：
    - 波动率自适应归一化 (ATR Spike) + 恐慌冷却期(Hysteresis)
    - 价格趋势优先 (Price Action is King)
    - 动态宏观利率过滤 (取代硬编码)
    - 消除 Pandas NaN 陷阱与零除异常
    """

    def _safe_float(self, val, default=0.0):
        """安全转换浮点数，防范 Pandas 的 NaN 陷阱"""
        if pd.isna(val) or val is None:
            return default
        try:
            return float(val)
        except:
            return default

    def identify(self, df: pd.DataFrame, us_10y_yield: float = 0.0, vix: float = 0.0):
        if df is None or len(df) < 20:
            return "Unknown", "数据不足(需至少20个交易日)，无法判断体制。"

        try:
            latest = df.iloc[-1]
            
            # 1. 安全提取核心指标
            close = self._safe_float(latest.get('收盘'))
            ma20 = self._safe_float(latest.get('MA20'))
            ma60 = self._safe_float(latest.get('MA60'))
            ma200 = self._safe_float(latest.get('MA200'))
            atr = self._safe_float(latest.get('ATR'))

            # 2. 波动率自适应归一化与恐慌冷却期 (Volatility Spike & Hysteresis)
            vol_spike = 1.0
            recent_panic = False  # 恐慌滞后标志位（防止状态反复横跳）
            
            if 'ATR' in df.columns:
                atr_series = df['ATR'].dropna()
                if len(atr_series) >= 20:
                    atr_ma20 = self._safe_float(atr_series.rolling(20).mean().iloc[-1])
                    vol_spike = (atr / atr_ma20) if atr_ma20 > 0 else 1.0
                    
                    # 冷却期逻辑：过去3天内是否有过波动率异常放大（余震期）
                    if len(atr_series) >= 23:
                        recent_max_atr = atr_series.iloc[-3:].max()
                        if (recent_max_atr / atr_ma20) > 1.5:
                            recent_panic = True
                else:
                    atr_ma20 = atr
            else:
                atr_ma20 = atr

            # 3. 长期趋势斜率安全计算
            ma200_slope = 0.0
            if len(df) >= 20:
                prev_20 = df.iloc[-20]
                prev_ma200 = self._safe_float(prev_20.get('MA200'))
                # 确保 prev_ma200 存在且非 0，防止刚上市新股导致除零异常
                if ma200 > 0 and prev_ma200 > 0:
                    ma200_slope = (ma200 - prev_ma200) / prev_ma200

            # 4. 均线排列形态 (兼容次新股无 MA200 的情况)
            if ma200 > 0:
                is_bull_align = (close > ma20 and ma20 > ma60 and ma60 > ma200)
                is_bear_align = (close < ma20 and ma20 < ma60 and ma60 < ma200)
            else:
                # 降级验证
                is_bull_align = (close > ma20 and ma20 > ma60)
                is_bear_align = (close < ma20 and ma20 < ma60)

            # 5. 宏观条件解析 (动态化处理，剥离教条硬编码)
            macro_rate_pressure = False
            try:
                us_10y_val = float(str(us_10y_yield).replace('%', '')) if us_10y_yield not in['N/A', None] else 0.0
                
                # 动态利率判定：如果传入了历史美债列，看动量；否则使用较高极值作为备选
                if 'US_10Y' in df.columns and len(df) >= 60:
                    us10y_ma60 = self._safe_float(df['US_10Y'].rolling(60).mean().iloc[-1])
                    if us10y_ma60 > 0 and us_10y_val > us10y_ma60 * 1.1: # 利率短期快速飙升10%以上
                        macro_rate_pressure = True
                else:
                    if us_10y_val > 4.5: # 仅在无历史数据且达绝对极值时视为压力
                        macro_rate_pressure = True
            except:
                us_10y_val = 0.0

            vix_val = self._safe_float(vix)

            # =========================================================
            # 6. 状态机判定 (Price Action 优先法则)
            # =========================================================

            # --- State 1: Panic (恐慌/危机 + 冷却期保护) ---
            if vol_spike > 1.5 or recent_panic or vix_val > 28:
                reason = "VIX高企" if vix_val > 28 else "波动率异常放大(或处于余震冷却期)"
                return "Panic", f"⚠️ 极度恐慌状态！{reason}。资金正在踩踏，技术支撑大概率失效。建议：绝对防御，规避做多。"

            # --- State 2: Aggressive Bull (主升浪/快牛) ---
            # 微调：MA200 严重滞后，只要斜率不出现明显向下(>= -0.002)且呈现多头排列，即确认主升浪
            if is_bull_align and ma200_slope >= -0.002:
                desc = "🚀 主升浪进攻态势。均线呈完美多头排列，量价动能极强。"
                if macro_rate_pressure:
                    desc += f" (注: 虽宏观利率边际承压，但强劲的价格趋势包容了一切，顺势而为)。"
                return "Aggressive Bull", desc

            # --- State 3: Structural Bear (结构性熊市) ---
            if is_bear_align or (ma200 > 0 and close < ma200 and ma200_slope < -0.005):
                return "Bear", "📉 结构性熊市。价格被中期与长期均线死死压制，长期资本处于撤离状态。建议：严禁逆势抄底，逢高减仓。"

            # --- State 4: Macro Correction (中期调整) ---
            # 修复陷阱：不再因短线跌破MA20就误判，必须切切实实跌破季线(MA60)生命线
            if (ma200 > 0 and close > ma200) and close < ma60:
                desc = "⚠️ 中期回调/深度洗盘。长牛趋势(MA200)仍在，但已跌破中期机构生命线(MA60)。"
                if macro_rate_pressure:
                    desc += f" 叠加宏观利率飙升，正处于去杠杆期。"
                return "Correction", desc + " 建议：暂停追高，耐心等待缩量企稳。"

            # --- State 5: Passive Bull (慢牛/震荡向上) ---
            if close > ma60 and (ma200 == 0 or close > ma200):
                desc = "🐂 结构性慢牛。价格稳居中长期生命线之上，虽无暴涨动能，但重心在上移。"
                # 对慢牛回踩叠加宏观压力的情况，仅做文本提示，不改变底层体制
                if close < ma20 and macro_rate_pressure:
                    desc += f" (注: 跌破短线支撑且受高息扰动，控制单次买入仓位)。"
                return "Passive Bull", desc + " 建议：在核心资产回踩均线时进行定投布局。"

            # --- State 6: Shock (宽幅震荡) ---
            return "Shock", "⚖️ 宽幅震荡市。均线相互交织，无明确单边趋势。建议：高抛低吸网格操作，或保持观望。"

        except Exception as e:
            # 引入 exc_info=True，在日志里直接打印 Traceback，方便你排查 DataFrame 到底缺了什么数据
            logging.error(f"体制识别计算出错: {e}", exc_info=True)
            return "Error", "内部计算异常，已触发安全降级。"
# src/tools/market_data.py

import os
import requests
import pandas as pd
import akshare as ak
import logging
import numpy as np # 新增 numpy 用于计算 ATR
from datetime import datetime
from src.utils.network import no_proxy_context

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarketData:
    """
    负责从 AkShare/Tencent 获取市场数据，并清洗为 Agent 可读的格式。
    [Phase 4.5 升级]: 
    1. 移除全局代理暴力清理，采用直连策略。
    2. 新增美股指数支持 (Tencent 接口)。
    3. 新增 KDJ, ATR 指标。
    """

    def __init__(self):
        # 默认监控列表
        self.TARGETS = [
            {"name": "上证指数", "symbol": "sh000001", "type": "index"},
            {"name": "沪深300", "symbol": "sh000300", "type": "index"},
            {"name": "创业板指", "symbol": "sz399006", "type": "index"},
            # [Phase 4.5 新增] 美股三大指数
            {"name": "纳斯达克100", "symbol": "us.NDX", "type": "us_index"},
            {"name": "标普500", "symbol": "us.INX", "type": "us_index"},
            {"name": "道琼斯", "symbol": "us.DJI", "type": "us_index"},
        ]
        self.last_dfs = {} 

    def update_targets(self, new_holdings: list):
        """动态更新监控列表"""
        existing_symbols = {item['symbol'] for item in self.TARGETS}
        for item in new_holdings:
            name = item.get('name')
            symbol = item.get('symbol')
            h_type = item.get('type', 'holding')
            
            if symbol not in existing_symbols:
                self.TARGETS.append({
                    "name": name, 
                    "symbol": str(symbol),
                    "type": h_type
                })
                existing_symbols.add(symbol)
                logging.info(f"已动态添加持仓监控标的: {name} ({symbol})")

    def calculate_technical_indicators(self, df, has_volume=True):
        """
        计算核心技术指标: MA, RSI, MACD, Bollinger
        [Phase 4.5 新增]: KDJ, ATR
        """
        # 基础数据清洗
        df['收盘'] = pd.to_numeric(df['收盘'], errors='coerce')
        if '最高' in df.columns: df['最高'] = pd.to_numeric(df['最高'], errors='coerce')
        if '最低' in df.columns: df['最低'] = pd.to_numeric(df['最低'], errors='coerce')
        
        # 1. 均线 (Trend)
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()
        df['MA200'] = df['收盘'].rolling(window=200).mean()

        # 2. RSI (Momentum)
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 3. MACD
        exp12 = df['收盘'].ewm(span=12, adjust=False).mean()
        exp26 = df['收盘'].ewm(span=26, adjust=False).mean()
        df['MACD_DIF'] = exp12 - exp26
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])

        # 4. 布林带 (Bollinger)
        df['BB_STD'] = df['收盘'].rolling(window=20).std()
        df['BB_UP'] = df['MA20'] + 2 * df['BB_STD']
        df['BB_LOW'] = df['MA20'] - 2 * df['BB_STD']

        # 5. 量能
        if has_volume and '成交量' in df.columns:
            df['VOL_MA5'] = df['成交量'].rolling(window=5).mean()
        else:
            df['VOL_MA5'] = pd.NA

        # === [Phase 4.5 新增] KDJ 指标 ===
        if '最高' in df.columns and '最低' in df.columns:
            low_list = df['最低'].rolling(window=9, min_periods=9).min()
            high_list = df['最高'].rolling(window=9, min_periods=9).max()
            rsv = (df['收盘'] - low_list) / (high_list - low_list) * 100
            
            # Pandas 递归计算 K, D, J
            # 这里简化处理，直接用 ewm 模拟平滑
            df['K'] = rsv.ewm(com=2, adjust=False).mean() # com=2 等同于 alpha=1/3
            df['D'] = df['K'].ewm(com=2, adjust=False).mean()
            df['J'] = 3 * df['K'] - 2 * df['D']
        else:
            df['K'] = df['D'] = df['J'] = 50 # 缺省中性值

        # === [Phase 4.5 新增] ATR (波动率) ===
        if '最高' in df.columns and '最低' in df.columns:
            # TR = Max(High-Low, Abs(High-Close_prev), Abs(Low-Close_prev))
            df['H-L'] = df['最高'] - df['最低']
            df['H-PC'] = abs(df['最高'] - df['收盘'].shift(1))
            df['L-PC'] = abs(df['最低'] - df['收盘'].shift(1))
            df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
            df['ATR'] = df['TR'].rolling(window=14).mean()
        else:
            df['ATR'] = 0

        return df

    def get_data_from_tencent(self, symbol, name, t_type="stock"):
        """使用 AkShare 获取 A股/港股/指数, 提供复权数据"""
        try:
            # 兼容逻辑：如果是场外基金代码，不走这里
            if symbol.isdigit() and len(symbol) == 6 and not symbol.startswith(('sh', 'sz')):
                 return None 

            logging.info(f"正在获取国内标的 [{name}] ({symbol})...")
            with no_proxy_context():
                if t_type == "index":
                    # 指数无需复权，继续使用原接口
                    df = ak.stock_zh_index_daily_tx(symbol=symbol)
                else:
                    # 个股必须使用前复权 (qfq) 接口，杜绝价格幻觉
                    df = ak.stock_zh_a_hist_tx(symbol=symbol, start_date="20230101", adjust="qfq")
            
            if df is None or df.empty:
                return None

            # 重命名列
            column_mapping = {'date': '日期', 'open': '开盘', 'close': '收盘', 'high': '最高', 'low': '最低', 'amount': '成交量'}
            df.rename(columns=column_mapping, inplace=True)
            df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
            df = df[df['日期'] >= '2023-01-01']
            
            # 计算全套指标
            df = self.calculate_technical_indicators(df, has_volume=True)
            self.last_dfs[symbol] = df
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            change_pct = round((latest['收盘'] - prev['收盘']) / prev['收盘'] * 100, 2)

            # 生成信号摘要
            analysis_text = self._generate_signal_summary(latest, change_pct)

            return {
                "name": name,
                "symbol": symbol,
                "date": latest['日期'],
                "close": float(latest['收盘']),
                "change_pct": change_pct,
                "volume_e": round(float(latest['成交量']) / 100000000, 2),
                "indicators": self._pack_indicators(latest),
                "signal_summary": ", ".join(analysis_text)
            }
        except Exception as e:
            logging.error(f"获取国内标的 [{name}] 失败: {e}")
            return None

    def get_us_data_from_tencent(self, symbol, name):
        """
        [Phase 4.5 新增] 使用 requests 直连腾讯接口获取美股指数
        URL: http://qt.gtimg.cn/q=us.NDX
        """
        try:
            logging.info(f"正在获取美股标的 [{name}] ({symbol})...")
            url = f"http://qt.gtimg.cn/q={symbol}"
            
            # 直连，不使用代理 (proxies=None)
            resp = requests.get(url, timeout=5, proxies=None)
            if resp.status_code != 200:
                return None

            text = resp.content.decode('gbk', errors='ignore')
            # 解析: v_us_NDX="200~纳斯达克100~.NDX~24708.94~...~-303.68~-1.21~..."
            # 索引: 3=Current, 31=Change, 32=Pct
            
            if '="' not in text: return None
            content = text.split('="')[1].strip('";\n')
            parts = content.split('~')
            
            if len(parts) < 33: return None
            
            current_price = float(parts[3])
            change_val = float(parts[31])
            change_pct = float(parts[32])
            
            # 构造假的 DataFrame 以兼容 calculate_technical_indicators 
            # (注意：实时接口没有历史K线，这里我们只能拿当日数据做简单的均线估算，或者暂时只返回实时价格)
            # *为了系统稳定性，Phase 4.5 暂不支持美股的复杂历史指标 (MA/MACD)，只支持实时报价*
            
            indicators = {
                "MA20": "N/A", "RSI": "N/A", "MACD": "N/A", "K": "N/A", "ATR": "N/A"
            }
            
            # 简单的信号生成
            analysis_text = []
            if change_pct > 1.0: analysis_text.append("大涨")
            elif change_pct < -1.0: analysis_text.append("大跌")
            else: analysis_text.append("震荡")

            return {
                "name": name,
                "symbol": symbol,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "close": current_price,
                "change_pct": change_pct,
                "volume_e": 0, # 指数成交量通常巨大且单位不统一，暂忽略
                "indicators": indicators,
                "signal_summary": ", ".join(analysis_text)
            }

        except Exception as e:
            logging.error(f"获取美股标的 [{name}] 失败: {e}")
            return None

    def get_otc_fund_data(self, symbol, name):
        """[原有逻辑] 场外基金"""
        # ... (此处保持原有逻辑不变，为了节省篇幅，假设你已保留原代码) ...
        # 唯一需要修改的是在计算指标时调用新的 self.calculate_technical_indicators
        # 这里建议直接使用原文件中的代码，只需替换 calculate_technical_indicators 调用的地方
        # 为了完整性，我写一个简版占位，实际请保留你原有的完整逻辑
        try:
            df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
            if df is None or df.empty: return None
            df.rename(columns={'净值日期': '日期', '单位净值': '收盘'}, inplace=True)
            df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
            df['最高'] = df['最低'] = df['收盘'] # 基金无高低，填补以计算 KDJ
            df = self.calculate_technical_indicators(df, has_volume=False)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            change_pct = round((float(latest['收盘']) - float(prev['收盘'])) / float(prev['收盘']) * 100, 2)
            
            return {
                "name": name, 
                "symbol": symbol, 
                "date": latest['日期'], 
                "close": float(latest['收盘']),
                "change_pct": change_pct,
                "volume_e": 0.0,
                "indicators": self._pack_indicators(latest),
                "signal_summary": "净值更新"
            }
        except Exception:
            return None

    def _generate_signal_summary(self, row, pct):
        """辅助函数：生成信号文本"""
        txt = []
        # MA
        if row['收盘'] > row['MA20']: txt.append("站上MA20")
        else: txt.append("跌破MA20")
        # MACD
        if row['MACD_DIF'] > row['MACD_DEA']: txt.append("MACD金叉")
        # KDJ
        if row['K'] > 80: txt.append("KDJ超买")
        elif row['K'] < 20: txt.append("KDJ超卖")
        # ATR
        if row['ATR'] > row['收盘'] * 0.03: txt.append("高波动")
        return txt

    def _pack_indicators(self, row):
        """辅助函数：打包指标"""
        return {
            "MA20": round(float(row['MA20']), 2),
            "RSI": round(float(row['RSI']), 1),
            "MACD": "金叉" if row['MACD_DIF'] > row['MACD_DEA'] else "死叉",
            "Bollinger": "Upper" if row['收盘'] >= row['BB_UP'] else ("Lower" if row['收盘'] <= row['BB_LOW'] else "Mid"),
            "K": round(float(row['K']), 1),
            "ATR": round(float(row['ATR']), 2)
        }
    
    def get_macro_metrics(self):
        """[维度4新增] 获取宏观锚点数据 (美债10Y)"""
        macro_data = {"us_10y": "N/A", "cn_10y": "N/A"}
        try:
            with no_proxy_context():
                df = ak.bond_zh_us_rate()
                # 逻辑：查找最近一个非空的美债数据
                if not df.empty and '美国国债收益率10年' in df.columns:
                    us_val = df['美国国债收益率10年'].dropna().iloc[-1]
                    macro_data['us_10y'] = round(float(us_val), 2)
                
                # 顺便拿一下中债
                if not df.empty and '中国国债收益率10年' in df.columns:
                    cn_val = df['中国国债收益率10年'].dropna().iloc[-1]
                    macro_data['cn_10y'] = round(float(cn_val), 2)
                    
            logging.info(f"宏观数据获取成功: US10Y={macro_data['us_10y']}%")
        except Exception as e:
            logging.warning(f"宏观数据获取失败: {e}")
        
        return macro_data

    def get_market_summary(self):
        """路由分发中心"""
        results = []
        for target in self.TARGETS:
            t_type = target.get('type', 'stock')
            
            if t_type == 'otc_fund':
                data = self.get_otc_fund_data(target['symbol'], target['name'])
            elif t_type == 'us_index': # [新增]
                data = self.get_us_data_from_tencent(target['symbol'], target['name'])
            else:
                data = self.get_data_from_tencent(target['symbol'], target['name'], t_type)
                
            if data:
                data['type'] = t_type
                results.append(data)
        
        return {
            "summary_date": datetime.now().strftime("%Y-%m-%d"),
            "indices": results
        }
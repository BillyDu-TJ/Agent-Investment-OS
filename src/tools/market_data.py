# src/tools/market_data.py

import os
import sys
# 强制移除代理环境变量，必须在导入 akshare 之前执行
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if proxy_var in os.environ:
        del os.environ[proxy_var]

# 同时设置 requests 库不使用代理
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'


import akshare as ak
import pandas as pd
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MarketData:
    """
    负责从 AkShare 获取市场数据，并清洗为 Agent 可读的格式。
    """

    def __init__(self):
        # [配置区] 你可以在这里随意添加你想监控的标的
        # 格式: "中文名称": "代码"
        # 注意：东方财富接口的代码通常不需要加 sh/sz 前缀，直接用数字
        self.TARGETS = {
            "上证指数": "sh000001",
            "沪深300": "sh000300", 
            "创业板指": "sz399006",
            # "上证50": "000016", # 如果想看，取消注释即可
        }

    def calculate_technical_indicators(self, df):
        """
        计算核心技术指标：MA, RSI, MACD
        """
        # 1. 移动平均线 (Trend)
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA200'] = df['收盘'].rolling(window=200).mean()

        # 2. RSI 相对强弱指标 (Momentum) - 标准 Wilder's 算法
        delta = df['收盘'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 3. MACD (Trend Reversal)
        exp12 = df['收盘'].ewm(span=12, adjust=False).mean()
        exp26 = df['收盘'].ewm(span=26, adjust=False).mean()
        df['MACD_DIF'] = exp12 - exp26
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        df['MACD'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])
        
        return df

    def get_data_from_tencent(self, symbol, name):
        """
        使用腾讯接口获取数据
        """
        try:
            logging.info(f"正在获取 [{name}] ({symbol})...")
            
            # 调用腾讯接口
            df = ak.stock_zh_index_daily_tx(symbol=symbol)
            
            if df.empty:
                logging.warning(f"[{name}] 数据为空,请检查代码是否正确。")
                return None

            # 打印原始列名以便调试
            # logging.info(f"原始列名: {df.columns.tolist()}")
            
            # 重命名列为中文标准格式
            # 修复核心：腾讯接口返回的是 amount (成交额)，将其映射为 '成交量' 以匹配后续逻辑
            column_mapping = {
                'date': '日期',
                'open': '开盘',
                'close': '收盘',
                'high': '最高',
                'low': '最低',
                'amount': '成交量' 
            }
            df.rename(columns=column_mapping, inplace=True)
            
            # 确保日期格式正确
            df['日期'] = pd.to_datetime(df['日期']).dt.strftime('%Y-%m-%d')
            
            # 过滤最近2年的数据
            df = df[df['日期'] >= '2023-01-01']
            
            # 计算技术指标 - 修复：确保调用正确的函数名
            df = self.calculate_technical_indicators(df)
            
            # 获取最新数据
            latest = df.iloc[-1]
            prev = df.iloc[-2]

            # 计算涨跌幅
            change_pct = round((latest['收盘'] - prev['收盘']) / prev['收盘'] * 100, 2)

            # 生成自然语言分析 (给 Agent 看的)
            analysis_text = []
            
            # A. 均线分析
            if latest['收盘'] > latest['MA20']:
                analysis_text.append("站上20日线(强势)")
            else:
                analysis_text.append("跌破20日线(弱势)")
            
            # B. RSI 分析
            rsi_val = round(latest['RSI'], 1)
            if rsi_val > 80:
                analysis_text.append(f"RSI过热({rsi_val})")
            elif rsi_val < 20:
                analysis_text.append(f"RSI超卖({rsi_val})")
            else:
                analysis_text.append(f"RSI中性({rsi_val})")

            # C. MACD 分析
            if latest['MACD_DIF'] > latest['MACD_DEA']:
                analysis_text.append("MACD金叉状态")
            else:
                analysis_text.append("MACD死叉状态")

            return {
                "name": name,
                "symbol": symbol,
                "date": latest['日期'],
                "close": float(latest['收盘']),
                "change_pct": change_pct,
                "volume_e": round(float(latest['成交量']) / 100000000, 2), # 转为亿
                "indicators": {
                    "MA20": round(float(latest['MA20']), 2),
                    "RSI": rsi_val,
                    "MACD": "金叉" if latest['MACD_DIF'] > latest['MACD_DEA'] else "死叉"
                },
                "signal_summary": ", ".join(analysis_text)
            }

        except Exception as e:
            logging.error(f"获取 [{name}] 失败: {e}")
            # import traceback
            # traceback.print_exc()
            return None

    def get_market_summary(self):
        """
        循环抓取配置列表中的所有标的
        """
        results = []
        for name, code in self.TARGETS.items():
            data = self.get_data_from_tencent(code, name)
            if data:
                results.append(data)
        
        return {
            "summary_date": datetime.now().strftime("%Y-%m-%d"),
            "indices": results
        }

# --- 测试运行 ---
if __name__ == "__main__":
    provider = MarketData()
    data = provider.get_market_summary()
    
    import json
    print("\n" + "="*40)
    print("数据获取结果 (包含 RSI/MACD):")
    print("="*40)
    print(json.dumps(data, indent=4, ensure_ascii=False))
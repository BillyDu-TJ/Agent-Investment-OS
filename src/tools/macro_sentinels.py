# src/tools/macro_sentinels.py

import requests
import logging
from src.utils.network import no_proxy_context

class MacroSentinel:
    """
    宏观哨兵：负责监控 VIX (恐慌指数), USD/CNH (汇率) 和 Gold (黄金锚点)。
    独立于持仓列表运行。
    """
    
    def __init__(self):
        self.INDEX_LIST = [
            {"name": "上证指数", "symbol": "sh000001", "type": "index"},
            {"name": "沪深300", "symbol": "sh000300", "type": "index"},
            {"name": "创业板指", "symbol": "sz399006", "type": "index"},
            {"name": "纳斯达克100", "symbol": "us.NDX", "type": "us_index"},
            {"name": "标普500", "symbol": "us.INX", "type": "us_index"},
            {"name": "道琼斯", "symbol": "us.DJI", "type": "us_index"},
        ]
        self.headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def get_macro_data(self):
        """一次性获取所有宏观硬指标"""
        data = {
            "vix": "N/A",
            "usd_cnh": "N/A",
            "gold_price": "N/A"
        }

        # 1. 获取 VIX (腾讯接口)
        try:
            with no_proxy_context():
                resp = requests.get("http://qt.gtimg.cn/q=us.VIX", timeout=5)
            if resp.status_code == 200:
                text = resp.content.decode('gbk', errors='ignore')
                if '="' in text:
                    parts = text.split('="')[1].split('~')
                    if len(parts) > 30:
                        data['vix'] = float(parts[3])
        except Exception as e:
            logging.warning(f"[哨兵] VIX 获取失败: {e}")

        # 2. 获取 USD/CNH (新浪接口)
        try:
            with no_proxy_context():
                resp = requests.get("http://hq.sinajs.cn/list=fx_susdcnh", headers=self.headers, timeout=5)
            if resp.status_code == 200:
                text = resp.text
                if '="' in text:
                    parts = text.split('="')[1].strip('";\n').split(',')
                    if len(parts) > 8:
                        data['usd_cnh'] = float(parts[8])
        except Exception as e:
            logging.warning(f"[哨兵] USD/CNH 获取失败: {e}")

        return data

    def get_gold_anchor(self):
        """
        强制追踪黄金 (518880) 价格，即使未持仓。
        用于判断 Risk-Off 情绪。
        """
        try:
            with no_proxy_context():
                resp = requests.get("http://qt.gtimg.cn/q=sh518880", timeout=5)
            if resp.status_code == 200:
                text = resp.content.decode('gbk', errors='ignore')
                if '="' in text:
                    parts = text.split('="')[1].split('~')
                    # 价格(3), 涨跌幅(32)
                    return {
                        "name": "黄金ETF(宏观锚点)",
                        "price": float(parts[3]),
                        "change_pct": float(parts[32])
                    }
        except Exception:
            pass
        return None
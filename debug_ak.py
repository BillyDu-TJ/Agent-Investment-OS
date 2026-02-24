# tests/test_tencent_us.py

import requests
import logging
import pandas as pd
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def parse_tencent_us_data(symbol, response_text):
    """
    解析腾讯美股/指数的返回字符串 (修正版)
    """
    try:
        # 提取引号内容
        if '="' not in response_text: return None
        content = response_text.split('="')[1].strip('";\n')
        parts = content.split('~')
        
        # 针对你提供的日志数据进行精准映射
        # [1] 名称 (纳斯达克100)
        # [2] 代码 (.NDX) -> 这里之前代码试图转float导致报错
        # [3] 最新价 (24708.94)
        # [31] 涨跌额 (-303.68)
        # [32] 涨跌幅 (-1.21)
        
        # 简单防卫：确保数据长度足够
        if len(parts) < 33:
            return None

        data = {
            "symbol": symbol,
            "name": parts[1],
            "close": float(parts[3]),
            "change": float(parts[31]),
            "pct": float(parts[32]),
            # 腾讯的时间在 Index 30 (2026-02-23 17:15:59)
            "timestamp": parts[30]
        }
        return data
    except Exception as e:
        # 仅打印解析错误的简略信息，避免刷屏
        logging.warning(f"解析 {symbol} 异常: {e}")
        return None

def test_tencent_connection():
    logging.info("🚀 [Fix] 腾讯美股接口解析测试...")
    
    # 既然你只需要三大指数，我们重点测这几个
    targets = [
        ("us.NDX", "纳斯达克100"), 
        ("us.INX", "标普500"),
        ("us.DJI", "道琼斯"),     # 顺便加上道指
    ]
    
    codes = ",".join([t[0] for t in targets])
    url = f"http://qt.gtimg.cn/q={codes}"
    
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            logging.error(f"❌ 请求失败: {resp.status_code}")
            return

        # 尝试解码 (腾讯可能是 GBK 或 UTF-8)
        text = resp.content.decode('gbk', errors='ignore')
        
        results = []
        lines = text.strip().split('\n')
        for line in lines:
            if not line: continue
            for code, name in targets:
                # 模糊匹配 (us.NDX 可能会变成 v_us_NDX)
                clean_code = code.replace('.', '_')
                if clean_code in line:
                    parsed = parse_tencent_us_data(code, line)
                    if parsed:
                        results.append(parsed)
        
        if results:
            df = pd.DataFrame(results)
            print("\n" + "="*60)
            print("📊 腾讯全球指数实时行情 (Success)")
            print("="*60)
            # 调整列顺序
            print(df[['name', 'symbol', 'close', 'pct', 'change', 'timestamp']].to_string(index=False))
            print("\n✅ Step 1 验证完成：我们可以通过腾讯接口稳定获取美股指数。")
        else:
            logging.error("❌ 解析结果依然为空，请检查原始数据。")
            print(text)

    except Exception as e:
        logging.error(f"❌ 网络或系统异常: {e}")

if __name__ == "__main__":
    test_tencent_connection()
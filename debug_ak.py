# test_market_api.py

import os
import sys
import time

# 1. 环境清理：确保无代理干扰 (排除网络环境误判)
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if proxy_var in os.environ:
        del os.environ[proxy_var]
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import akshare as ak
import pandas as pd

def test_tencent_api():
    """测试当前报错的腾讯接口"""
    print("\n[1] 正在诊断原腾讯接口 (ak.stock_zh_index_daily_tx) ...")
    symbol = "sh000001"
    try:
        start_time = time.time()
        # 这就是 main.py 中报错的那个函数
        df = ak.stock_zh_index_daily_tx(symbol=symbol)
        
        if df is None or df.empty:
            print(f"❌ 腾讯接口返回空数据。")
        else:
            print(f"✅ 腾讯接口连接成功! (耗时 {time.time()-start_time:.2f}s)")
            print(f"   数据样例: {df.tail(1).to_dict(orient='records')}")
            
    except Exception as e:
        print(f"❌ 腾讯接口确认不可用。")
        print(f"   报错详情: {e}")

def test_eastmoney_index():
    """测试备选：东方财富-指数接口"""
    print("\n[2] 正在验证备选接口: 东方财富-指数 (ak.stock_zh_index_daily_em) ...")
    symbol = "sh000001" # 上证指数
    try:
        start_time = time.time()
        # 东财指数通常需要带 sh/sz 前缀
        df = ak.stock_zh_index_daily_em(symbol=symbol)
        
        if df is None or df.empty:
            print(f"❌ 东财指数接口返回空。")
        else:
            print(f"✅ 东财指数接口可用! (耗时 {time.time()-start_time:.2f}s)")
            print(f"   列名检查: {df.columns.tolist()}")
            print(f"   数据样例: \n{df.tail(2)}")
            
    except Exception as e:
        print(f"❌ 东财指数接口异常: {e}")

def test_eastmoney_stock():
    """测试备选：东方财富-个股/ETF接口"""
    print("\n[3] 正在验证备选接口: 东方财富-个股/ETF (ak.stock_zh_a_hist) ...")
    symbol = "513130" # 恒生科技ETF (注意：东财个股接口通常不需要 sh/sz 前缀)
    try:
        start_time = time.time()
        # 个股接口，使用前复权 (qfq)
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20240101", adjust="qfq")
        
        if df is None or df.empty:
            print(f"❌ 东财个股接口返回空。")
        else:
            print(f"✅ 东财个股接口可用! (耗时 {time.time()-start_time:.2f}s)")
            print(f"   列名检查: {df.columns.tolist()}")
            print(f"   数据样例: \n{df.tail(2)}")

    except Exception as e:
        print(f"❌ 东财个股接口异常: {e}")

if __name__ == "__main__":
    print("="*60)
    print("🚑 市场数据接口连通性诊断")
    print("="*60)
    
    test_tencent_api()
    test_eastmoney_index()
    test_eastmoney_stock()
    
    print("\n" + "="*60)
    print("诊断结束。请根据结果决定是否替换 market_data.py。")
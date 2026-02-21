import akshare as ak

# 软件服务指数代码
symbol = "931071"

print(f"--- 正在深入诊断指数 {symbol} 的所有字段 ---")
try:
    df = ak.stock_zh_index_value_csindex(symbol=symbol)
    if df is not None and not df.empty:
        # 获取最新的一行
        latest = df.iloc[-1]
        print("所有可用字段及当前值：")
        for col in df.columns:
            print(f"字段: {col:15} | 值: {latest[col]}")
            
        print("\n[分析提示]:")
        print("市盈率1: 通常是总股本PE")
        print("市盈率2: 可能是成分股加权或特定股本PE")
        print("股息率1/2: 对应的分红收益率")
    else:
        print("未能获取数据")
except Exception as e:
    print(f"诊断失败: {e}")
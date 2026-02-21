import akshare as ak

print("=============================================")
print("  Agent 估值模块 - 个股实时大表接口测试")
print("=============================================\n")

test_stock_code = "600519" # 贵州茅台
test_stock_name = "贵州茅台"

print(f"▶ 正在拉取 A股 实时行情大表 (大约需要几秒钟)...")
try:
    # 1. 调用 A股实时行情大表 (涵盖5000+只股票的今日数据)
    df_spot = ak.stock_zh_a_spot_em()
    
    if df_spot is not None and not df_spot.empty:
        print(f"✅ 成功拉取大表！共包含 {len(df_spot)} 只股票。")
        
        # 2. 在大表中匹配我们的测试股票
        # 大表中的代码通常是纯数字的字符串
        target_row = df_spot[df_spot['代码'] == test_stock_code]
        
        if not target_row.empty:
            print(f"\n✅ 成功在大表中找到 [{test_stock_name} ({test_stock_code})]！")
            
            # 3. 动态嗅探列名：防止东方财富改名字
            cols = target_row.columns.tolist()
            pe_cols = [c for c in cols if '市盈' in c or 'PE' in c.upper()]
            pb_cols = [c for c in cols if '市净' in c or 'PB' in c.upper()]
            
            print(f"   🔍 嗅探到的市盈率相关列: {pe_cols}")
            print(f"   🔍 嗅探到的市净率相关列: {pb_cols}")
            
            # 4. 尝试提取具体数值
            pe_col_name = '市盈率-动态' if '市盈率-动态' in cols else (pe_cols[0] if pe_cols else None)
            pb_col_name = '市净率' if '市净率' in cols else (pb_cols[0] if pb_cols else None)
            
            if pe_col_name and pb_col_name:
                pe_val = target_row[pe_col_name].values[0]
                pb_val = target_row[pb_col_name].values[0]
                print(f"\n🎯 最终提取结果 -> 市盈率({pe_col_name}): {pe_val}, 市净率({pb_col_name}): {pb_val}")
            else:
                print("❌ 找到了股票，但没有找到估值字段，请检查上方嗅探到的列名。")
        else:
            print(f"❌ 在大表中未找到代码为 {test_stock_code} 的股票。")
    else:
        print("❌ 大表数据返回为空。")
        
except Exception as e:
    print(f"❌ 接口拉取失败: {e}")

print("\n=============================================")
print("请将打印结果告诉我。只要拿到了 PE 和 PB，我们就可以拼上最后一块拼图了！")
# calc_gold.py
import os

# 清理代理环境变量
for proxy_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    if proxy_var in os.environ:
        del os.environ[proxy_var]
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import akshare as ak

def reverse_engineer_fund(fund_code: str, total_amount: float, profit: float):
    print(f"正在联网获取基金 {fund_code} 的最新净值...")
    try:
        # 获取最新净值
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        latest_nav = float(df.iloc[-1]['单位净值'])
        nav_date = df.iloc[-1]['净值日期']
        
        # 核心反推逻辑
        total_cost = total_amount - profit             # 计算总本金
        shares = total_amount / latest_nav             # 反推真实份额
        cost_per_share = total_cost / shares           # 反推持仓单价
        
        print("\n" + "="*40)
        print(f"✅ 反推成功！(基于 {nav_date} 净值: {latest_nav})")
        print("="*40)
        print("请将以下内容直接复制到您的 portfolio.yaml 中：\n")
        print(f"  - name: \"博时黄金C\"")
        print(f"    symbol: \"{fund_code}\"")
        print(f"    type: \"otc_fund\"")
        print(f"    cost: {round(cost_per_share, 4)}    # AI 反推的真实成本价")
        print(f"    shares: {round(shares, 2)}   # AI 反推的真实份额")
        print(f"    strategy: \"dca\"       # (按需修改)")
        print(f"    term: \"long\"          # (按需修改)")
        print(f"    reason: \"抗通胀与避险配置\"")
        print("="*40)
        
    except Exception as e:
        print(f"❌ 获取失败，请检查网络: {e}")

if __name__ == "__main__":
    # ⚠️ 请在这里填入您此刻在支付宝看到的数字！
    FUND_CODE = "002611"      # 博时黄金ETF联接C的代码
    TOTAL_AMOUNT = 5000.00    # 替换为您支付宝里的【总金额】
    PROFIT = 250.50           # 替换为您支付宝里的【持有收益】(如果是亏损请填负数，如 -100.0)
    
    reverse_engineer_fund(FUND_CODE, TOTAL_AMOUNT, PROFIT)
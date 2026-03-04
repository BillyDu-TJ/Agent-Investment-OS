# test_phase6_part2.py
import requests
import yaml
import os

print("="*50)
print("🚀 Phase 6: 宏观哨兵与 YAML 自愈 测试")
print("="*50)

# ==========================================
# 测试 1: 宏观指标数据源 (VIX & USD/CNH) 测试
# ==========================================
def test_macro_apis():
    print("\n--- 测试 1: 宏观指标获取 ---")
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0"
    }
    
    # 1. 测试腾讯获取 VIX 恐慌指数 (us.VIX)
    try:
        url_vix = "http://qt.gtimg.cn/q=us.VIX"
        resp = requests.get(url_vix, timeout=5)
        text = resp.content.decode('gbk')
        if '="' in text:
            parts = text.split('="')[1].split('~')
            print(f"✅ 腾讯接口 VIX 获取成功: {parts[3]} (涨跌幅: {parts[32]}%)")
        else:
            print("❌ 腾讯接口 VIX 获取失败: 返回格式异常")
    except Exception as e:
        print(f"❌ 腾讯接口 VIX 请求异常: {e}")

    # 2. 测试新浪获取 USD/CNH (离岸人民币)
    try:
        url_cnh = "http://hq.sinajs.cn/list=fx_susdcnh"
        resp = requests.get(url_cnh, headers=headers, timeout=5)
        text = resp.text
        if '="' in text:
            data_str = text.split('="')[1].strip('";\n')
            parts = data_str.split(',')
            # 新浪外汇数据：名称, 时间, 买入价, 卖出价, 昨收, ...
            if len(parts) > 8:
                current_price = parts[8] # 最新价
                print(f"✅ 新浪接口 USD/CNH 获取成功: {current_price} (更新时间: {parts[0]})")
            else:
                 print("❌ 新浪接口 USD/CNH 数据解析失败")
        else:
            print("❌ 新浪接口 USD/CNH 获取失败")
    except Exception as e:
        print(f"❌ 新浪接口 USD/CNH 请求异常: {e}")

# ==========================================
# 测试 2: YAML 自净化与记录拦截
# ==========================================
def test_yaml_sanitizer():
    print("\n--- 测试 2: 模拟 YAML 手动清零自愈机制 ---")
    mock_yaml_path = "test_mock_portfolio.yaml"
    
    # 写入模拟的脏数据 (用户手动把黄金设为 0)
    dirty_data = {
        "cash": 5000,
        "holdings":[
            {"name": "沪深300", "symbol": "510300", "shares": 1000},
            {"name": "黄金ETF", "symbol": "518880", "shares": 0.0} # <--- 脏数据
        ]
    }
    with open(mock_yaml_path, "w") as f:
        yaml.dump(dirty_data, f)
        
    print("加载前的 YAML:", [h['name'] for h in dirty_data['holdings']])
    
    # 模拟 PortfolioManager 加载并自愈
    with open(mock_yaml_path, "r") as f:
        loaded = yaml.safe_load(f)
        
    valid_holdings = []
    cleaned_symbols = []
    for h in loaded.get('holdings',[]):
        if float(h.get('shares', 1)) <= 0:
            cleaned_symbols.append(h['name'])
        else:
            valid_holdings.append(h)
            
    if cleaned_symbols:
        loaded['holdings'] = valid_holdings
        # 写回 YAML
        with open(mock_yaml_path, "w") as f:
            yaml.dump(loaded, f)
        print(f"✅ 成功自愈！已自动剔除手动 0 股的资产: {cleaned_symbols}")
        print("💡 同步触发机制：系统将在此刻向 CSV 写入 MANUAL_CLEAR 记录。")
    
    # 验证最终结果
    print("加载后的 YAML:", [h['name'] for h in loaded['holdings']])
    
    if os.path.exists(mock_yaml_path):
        os.remove(mock_yaml_path)

if __name__ == "__main__":
    test_macro_apis()
    test_yaml_sanitizer()
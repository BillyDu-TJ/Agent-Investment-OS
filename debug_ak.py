# test_phase7_hunter.py
from src.tools.market_hunter import MarketHunter
import yaml
import os

print("="*50)
print("🚀 Phase 7: MarketHunter 终极选股实弹演练")
print("="*50)

def test_integration():
    # 确保 data 目录存在
    os.makedirs("data", exist_ok=True)
    
    # 1. 准备/加载 YAML 策略
    yaml_path = "config/strategy_profile.yaml"
    if not os.path.exists(yaml_path):
        print(f"❌ 找不到 {yaml_path}，请确保已创建该文件并填入策略。")
        return

    with open(yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 2. 实例化猎人
    hunter = MarketHunter()

    # 3. 猎杀行动 (测试核心 DCA 策略)
    print("📈 正在执行【核心 DCA 策略】扫描 (偏好低估值、高股息)...")
    core_config = config['dynamic_strategies']['core_dca']
    core_results = hunter.hunt(core_config, top_n_industry=1, top_n_stocks=3)

    for ind, stocks in core_results.items():
        print(f"\n🏆 [核心池] 板块: {ind}")
        for s in stocks:
            print(f"  -> {s['名称']}({s['代码']}) | 价格: {s['最新价']} | PE: {s['PE']} | 得分: {s['Final_Score']:.3f}")

    # 4. 猎杀行动 (测试卫星动量策略)
    print("\n🚀 正在执行【卫星动量策略】扫描 (偏好高换手、强动量)...")
    satellite_config = config['dynamic_strategies']['satellite_momentum']
    sat_results = hunter.hunt(satellite_config, top_n_industry=1, top_n_stocks=3)

    for ind, stocks in sat_results.items():
        print(f"\n🎯 [卫星池] 板块: {ind}")
        for s in stocks:
            print(f"  -> {s['名称']}({s['代码']}) | 价格: {s['最新价']} | 换手率: {s['换手率']}% | 得分: {s['Final_Score']:.3f}")

if __name__ == "__main__":
    test_integration()
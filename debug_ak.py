# tests/test_rebalancer.py
import json
from src.tools.rebalancer import Rebalancer

def test_dynamic_dca_and_rebalance():
    # 模拟从 portfolio_manager 获取的状态
    mock_portfolio = {
        "total_assets": 100000.0,
        "cash": 10000.0,
        "holdings":[
            {
                "name": "恒生科技ETF",
                "symbol": "sh513130",
                "position_value": 45000.0, # 当前占45%，属于核心仓，我们目标是35% (超配需卖出)
                "user_intent": {"term": "long", "strategy": "value"}
            },
            {
                "name": "南方纳指A",
                "symbol": "016452",
                "position_value": 1000.0, # 刚开始建仓，只占 1%。策略是 DCA
                "user_intent": {"term": "long", "strategy": "dca"}
            },
            {
                "name": "卫星小票",
                "symbol": "sz300001",
                "position_value": 25000.0, # 卫星仓目标 30% (30000)，当前 25000，缺口 5000 (恰好 5% 边缘)
                "user_intent": {"term": "short", "strategy": "momentum"}
            }
        ]
    }

    # 模拟 strategy_profile.yaml 的配置
    mock_strategy = {
        "portfolio_structure": {
            "core_weight": 0.70,
            "satellite_weight": 0.30
        },
        "rebalance_rules": {
            "category_mapping": {"core": ["long"], "satellite": ["mid", "short"]},
            "tolerance_threshold": 0.05,
            "dca_build_period": 60,
            "dca_dynamic_adjust": True
        }
    }

    # 模拟市场数据 (关键是 RSI)
    mock_market =[
        {"symbol": "sh513130", "close": 0.75, "indicators": {"RSI": 60}},
        # 纳指暴跌，RSI极低，DCA应该加速买入 (1.5倍)
        {"symbol": "016452", "close": 2.00, "indicators": {"RSI": 25}}, 
        {"symbol": "sz300001", "close": 10.00, "indicators": {"RSI": 50}}
    ]

    rebalancer = Rebalancer(mock_portfolio, mock_strategy, mock_market)
    trades = rebalancer.generate_trade_list()

    print("\n📊 --- Rebalancer 计算结果 ---")
    print(f"账户总资产: 100000, 现金: 10000")
    print("理论分配目标: 核心仓(2只)目标70% -> 每只35000。卫星仓(1只)目标30% -> 30000\n")
    
    for t in trades:
        print(f"[{t['action']}] {t['name']}({t['symbol']})")
        print(f"   执行份额: {t['shares']} 份 | 消耗/回笼: ￥{t['amount']}")
        print(f"   触发理由: {t['reason']}\n")

if __name__ == "__main__":
    test_dynamic_dca_and_rebalance()
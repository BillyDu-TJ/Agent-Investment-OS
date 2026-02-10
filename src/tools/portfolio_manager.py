# src/tools/portfolio_manager.py

import yaml
import os
import logging

class PortfolioManager:
    """
    持仓管理器：负责读取配置并结合实时行情计算盈亏和仓位占比。
    """

    def __init__(self, config_path="config/portfolio.yaml"):
        self.config_path = config_path
        self.portfolio_data = self._load_config()

    def _load_config(self):
        """读取 YAML 配置文件"""
        if not os.path.exists(self.config_path):
            logging.error(f"未找到配置文件: {self.config_path}")
            return {"cash": 0, "holdings": []}
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logging.error(f"解析配置文件失败: {e}")
            return {"cash": 0, "holdings": []}

    def get_portfolio_status(self, market_summaries: list):
        """
        计算实时持仓状态
        :param market_summaries: Phase 1 中 get_market_summary() 返回的 indices 列表
        """
        cash = float(self.portfolio_data.get("cash", 0))
        holdings_config = self.portfolio_data.get("holdings", [])
        
        # 将市场数据转为字典以提高查询效率 {symbol: price}
        price_map = {item['symbol']: item['close'] for item in market_summaries}
        
        calculated_holdings = []
        total_holdings_value = 0.0

        for h in holdings_config:
            symbol = h['symbol']
            current_price = price_map.get(symbol)
            
            if current_price is None:
                logging.warning(f"持仓标的 {h['name']}({symbol}) 在实时行情中未找到，跳过计算。")
                continue

            # 核心计算逻辑
            cost = float(h['cost'])
            shares = float(h['shares'])
            current_value = current_price * shares
            profit_loss = (current_price - cost) * shares
            profit_loss_ratio = (current_price / cost - 1) * 100 if cost != 0 else 0
            
            total_holdings_value += current_value
            
            calculated_holdings.append({
                "name": h['name'],
                "symbol": symbol,
                "cost": cost,
                "shares": shares,
                "current_price": current_price,
                "current_value": round(current_value, 2),
                "profit_loss": round(profit_loss, 2),
                "profit_loss_ratio": round(profit_loss_ratio, 2)
            })

        # 计算资产总计
        total_assets = cash + total_holdings_value
        
        # 计算每只持仓的占比 (Position Ratio)
        for h in calculated_holdings:
            h['position_ratio'] = round((h['current_value'] / total_assets) * 100, 2)

        return {
            "total_assets": round(total_assets, 2),
            "total_holdings_value": round(total_holdings_value, 2),
            "cash": round(cash, 2),
            "cash_ratio": round((cash / total_assets) * 100, 2) if total_assets != 0 else 0,
            "holdings": calculated_holdings
        }

# --- 测试运行 ---
if __name__ == "__main__":
    # 模拟 Phase 1 返回的市场数据
    mock_market_data = [
        {"name": "沪深300", "symbol": "sh000300", "close": 3500.0},
        {"name": "创业板指", "symbol": "sz399006", "close": 1900.0}
    ]
    
    manager = PortfolioManager()
    status = manager.get_portfolio_status(mock_market_data)
    
    import json
    print("持仓实时状态分析:")
    print(json.dumps(status, indent=4, ensure_ascii=False))
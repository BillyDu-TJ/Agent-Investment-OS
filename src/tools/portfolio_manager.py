# src/tools/portfolio_manager.py

import yaml
import os
import logging

class PortfolioManager:
    """
    持仓管理器 (v2.5)：负责读取配置并打包“资产意图”上下文。
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
        计算实时持仓状态并透传策略意图
        :param market_summaries: MarketData 抓取的实时行情列表
        """
        cash = float(self.portfolio_data.get("cash", 0))
        holdings_config = self.portfolio_data.get("holdings", [])
        
        # 将市场数据转为字典 {symbol: price}
        price_map = {item['symbol']: item['close'] for item in market_summaries}
        
        calculated_holdings = []
        total_holdings_value = 0.0

        for h in holdings_config:
            symbol = h.get('symbol') or h.get('code') # 兼容 code 字段
            current_price = price_map.get(symbol)
            
            if current_price is None:
                logging.warning(f"持仓标的 {h['name']}({symbol}) 在实时行情中未找到，跳过计算。")
                continue

            # 1. 基础财务计算
            cost = float(h['cost'])
            shares = float(h['shares'])
            current_value = current_price * shares
            profit_loss_ratio = (current_price / cost - 1) * 100 if cost != 0 else 0
            
            total_holdings_value += current_value
            
            # 2. 策略意图打包 (Task 2 核心点：不做判断，只负责搬运数据)
            calculated_holdings.append({
                "name": h['name'],
                "symbol": symbol,
                "current_price": round(current_price, 3),
                "profit_loss_ratio": round(profit_loss_ratio, 2),
                "position_value": round(current_value, 2),
                # 透传用户意图
                "user_intent": {
                    "strategy": h.get("strategy", "unknown"),
                    "term": h.get("term", "unknown"),
                    "reason": h.get("reason", "n/a")
                }
            })

        total_assets = cash + total_holdings_value
        
        # 计算权重
        for h in calculated_holdings:
            h['weight_pct'] = round((h['position_value'] / total_assets) * 100, 2)

        return {
            "total_assets": round(total_assets, 2),
            "cash": round(cash, 2),
            "holdings": calculated_holdings
        }

# --- 验证逻辑 ---
if __name__ == "__main__":
    # 模拟输入
    mock_market = [{"symbol": "sh513130", "close": 0.78}]
    mgr = PortfolioManager()
    status = mgr.get_portfolio_status(mock_market)
    import json
    print(json.dumps(status, indent=4, ensure_ascii=False))


   
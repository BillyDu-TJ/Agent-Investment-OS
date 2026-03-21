# src/tools/transaction.py

import os
import yaml
import csv
from datetime import datetime
import logging

class TransactionManager:
    """
    Agent 操作系统的交易与记账中枢。
    负责解析 CLI 指令、执行交易数学计算、覆写 YAML 账本以及记录 CSV 交易日志。
    """

    def __init__(self, config_path="config/portfolio.yaml", log_dir="data"):
        self.config_path = config_path
        self.log_dir = log_dir
        self.csv_path = os.path.join(self.log_dir, "trade_history.csv")
        
        # 确保日志目录存在
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
            
        # 初始化 CSV 表头
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Action", "Symbol", "Price", "Shares", "Amount", "Realized_PnL"])

    def _load_portfolio(self):
        """安全读取 YAML"""
        if not os.path.exists(self.config_path):
            return {"cash": 0.0, "holdings": []}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"cash": 0.0, "holdings": []}

    def _save_portfolio(self, data):
        """将更新后的账本安全回写到 YAML"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    def _log_trade(self, action, symbol, price, shares, amount, pnl=0.0):
        """将交易记录追加到 CSV 日志中"""
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([today_str, action, symbol, price, shares, amount, pnl])

    def execute_command(self, command_str: str) -> str:
        """
        解析并执行类似:
        /buy sh513130 1000 0.688
        /sell 016452 500 1.500
        /deposit 5000
        """
        parts = command_str.strip().split()
        if not parts:
            return "❌ 无效的空指令。"

        action = parts[0].lower()
        
        try:
            # 1. 解析入金指令
            if action == "/deposit":
                if len(parts) != 2: return "❌ 格式错误。正确格式: /deposit [金额]"
                amount = float(parts[1])
                
                portfolio = self._load_portfolio()
                portfolio['cash'] = portfolio.get('cash', 0.0) + amount
                self._save_portfolio(portfolio)
                
                self._log_trade("DEPOSIT", "CASH", 0, 0, amount, 0.0)
                return f"✅ 成功入金: {amount:.2f} 元。当前可用现金: {portfolio['cash']:.2f} 元。"

            # 2. 解析买卖指令
            if action in ["/buy", "/sell"]:
                if len(parts) != 4: return f"❌ 格式错误。正确格式: {action} [代码] [份额] [价格]"
                
                symbol = str(parts[1])
                shares = float(parts[2])
                price = float(parts[3])
                total_value = shares * price
                
                portfolio = self._load_portfolio()
                cash = float(portfolio.get('cash', 0.0))
                holdings = portfolio.get('holdings', [])
                
                # 寻找目标资产
                target_holding = None
                for h in holdings:
                    if str(h.get('symbol')) == symbol:
                        target_holding = h
                        break
                
                if not target_holding:
                    return f"❌ 交易失败: 在 portfolio.yaml 中未找到代码为 '{symbol}' 的持仓。暂不支持自动建仓，请先在 YAML 中手动添加基础配置。"

                # 执行买入逻辑
                if action == "/buy":
                    if cash < total_value:
                        return f"❌ 买入失败: 可用现金 ({cash:.2f}) 不足，需要 ({total_value:.2f})。"
                    
                    old_cost = float(target_holding.get('cost', 0.0))
                    old_shares = float(target_holding.get('shares', 0.0))
                    
                    # 加权平均法计算新成本
                    new_shares = old_shares + shares
                    new_cost = (old_cost * old_shares + price * shares) / new_shares if new_shares > 0 else 0
                    
                    target_holding['shares'] = round(new_shares, 4)
                    target_holding['cost'] = round(new_cost, 4)
                    portfolio['cash'] = round(cash - total_value, 2)
                    
                    self._save_portfolio(portfolio)
                    self._log_trade("BUY", symbol, price, shares, total_value, 0.0)
                    
                    return f"✅ 买入成功: [{target_holding.get('name')}] {shares} 份 @ {price}。\n📊 扣除现金: {total_value:.2f}元。\n📉 最新摊薄成本: {new_cost:.4f}。"

                # 执行卖出逻辑
                elif action == "/sell":
                    old_cost = float(target_holding.get('cost', 0.0))
                    old_shares = float(target_holding.get('shares', 0.0))
                    
                    if old_shares < shares:
                        return f"❌ 卖出失败: 持有份额 ({old_shares}) 不足，无法卖出 ({shares})。"
                    
                    # 成本价不变，计算已实现盈亏
                    realized_pnl = (price - old_cost) * shares
                    
                    #[Phase 6 核心修复] 0 股剔除逻辑
                    remaining_shares = round(old_shares - shares, 4)
                    if remaining_shares <= 0:
                        portfolio['holdings'].remove(target_holding) # 彻底从账本中剔除
                        status_msg = "清仓"
                    else:
                        target_holding['shares'] = remaining_shares
                        status_msg = "卖出"
                    
                    portfolio['cash'] = round(cash + total_value, 2)
                    
                    self._save_portfolio(portfolio)
                    self._log_trade("SELL", symbol, price, shares, total_value, realized_pnl)
                    
                    pnl_str = f"盈利 {realized_pnl:.2f}元 🔴" if realized_pnl >= 0 else f"亏损 {abs(realized_pnl):.2f}元 🟢"
                    return f"✅ {status_msg}成功: [{target_holding.get('name')}] {shares} 份 @ {price}。\n💰 获得现金: {total_value:.2f}元。\n🏆 此次操作已实现盈亏: {pnl_str}。"

            return f"❌ 未知指令: {action}"

        except ValueError:
            return "❌ 参数类型错误。份额和价格必须为数字 (例如: /buy sh513130 1000 0.688)。"
        except Exception as e:
            return f"❌ 交易执行发生系统异常: {e}"
        
    def sanitize_portfolio(self):
        """
        [启动自愈] 检查 YAML 中是否有手动修改导致的 0 股残留。
        如果有，自动剔除并记录到 CSV，确保 AI 能够感知到这次手动清仓。
        """
        portfolio = self._load_portfolio()
        holdings = portfolio.get('holdings', [])
        
        valid_holdings = []
        cleaned_items = []
        
        for h in holdings:
            # 容错：处理 string 类型的 '0'
            try:
                shares = float(h.get('shares', 0))
            except:
                shares = 0
                
            if shares <= 0:
                cleaned_items.append(h)
            else:
                valid_holdings.append(h)
        
        if cleaned_items:
            # 执行剔除并保存
            portfolio['holdings'] = valid_holdings
            self._save_portfolio(portfolio)
            
            # 关键：向 CSV 写入操作记录，让 AI 知道
            for item in cleaned_items:
                symbol = item.get('symbol', 'UNKNOWN')
                name = item.get('name', 'UNKNOWN')
                logging.info(f"🧹 发现手动清仓资产: {name}({symbol})，正在执行账本自愈...")
                self._log_trade("MANUAL_CLEAR", symbol, 0, 0, 0, 0.0)
            
            return True # 返回 True 表示发生了清洗
        return False
    
    def execute_batch(self, trade_list: list) -> str:
        """
        [Task 3] 批量执行 Rebalancer 生成的交易清单
        """
        portfolio = self._load_portfolio()
        cash = float(portfolio.get('cash', 0.0))
        holdings = portfolio.get('holdings', [])
        
        messages =[]
        messages.append("📝 开始执行批量调仓指令...")
        
        for trade in trade_list:
            action = trade['action']
            symbol = trade['symbol']
            shares = float(trade['shares'])
            price = float(trade['price'])
            amount = float(trade.get('amount', shares * price))
            
            # 在现有的 holdings 中找到目标字典的引用 (直接修改该引用，其他字段就不会丢)
            target = next((h for h in holdings if str(h.get('symbol')) == str(symbol)), None)
            
            if not target:
                messages.append(f"⚠️ 跳过: 未在账本中找到 {symbol}。不支持自动新建仓。")
                continue
            
            old_shares = float(target.get('shares', 0.0))
            old_cost = float(target.get('cost', 0.0))
            
            if action == "BUY":
                if cash < amount:
                    messages.append(f"❌ 资金不足以买入 {symbol} (需 {amount:.2f}，剩余 {cash:.2f})")
                    continue
                
                # 加权成本计算
                new_shares = old_shares + shares
                new_cost = (old_cost * old_shares + amount) / new_shares if new_shares > 0 else 0
                
                # 仅更新关键数值字段，完美保留 strategy/term/reason/track_index 等原样字段！
                target['shares'] = round(new_shares, 4)
                target['cost'] = round(new_cost, 4)
                cash -= amount
                
                self._log_trade("BUY", symbol, price, shares, amount, 0.0)
                messages.append(f"✅ [买入] {target.get('name')} {shares}份。耗资: {amount:.2f}")
                
            elif action == "SELL":
                # 防爆仓校验
                if old_shares < shares:
                    shares = old_shares
                    amount = shares * price
                
                realized_pnl = (price - old_cost) * shares
                new_shares = round(old_shares - shares, 4)
                
                if new_shares <= 0.0001: # 容差清仓
                    holdings.remove(target)
                    messages.append(f"✅ [清仓] {target.get('name')} 已全部卖出。回笼: {amount:.2f}")
                else:
                    target['shares'] = new_shares
                    messages.append(f"✅ [卖出] {target.get('name')} {shares}份。回笼: {amount:.2f}")
                    
                cash += amount
                self._log_trade("SELL", symbol, price, shares, amount, realized_pnl)

        # 最终保存
        portfolio['cash'] = round(cash, 2)
        self._save_portfolio(portfolio)
        messages.append(f"💰 调仓完毕，当前可用现金余额: {portfolio['cash']:.2f}")
        
        return "\n".join(messages)

# --- 独立测试入口 ---
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 交易与记账系统独立测试")
    print("=" * 50)
    # 请确保您有 config/portfolio.yaml
    mgr = TransactionManager()
    
    # 模拟输入测试（您可以直接修改下面这段字符串来测买卖）
    test_cmd = "/buy sh513130 1000 0.688"  # 示例买入指令
    print(f"执行指令: {test_cmd}")
    print(mgr.execute_command(test_cmd))
    
    print("\n💡 您可以继续测试形如 '/buy sh513130 100 0.60' 的指令。")
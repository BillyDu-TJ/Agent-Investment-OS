# src/tools/rebalancer.py

import math
import logging

class Rebalancer:
    """
    智能定量调仓引擎 (V3.0)
    核心特性: 动态映射、容忍度带过滤、动态定投(Dynamic DCA)、可用资金安全锁。
    """

    def __init__(self, portfolio_status: dict, strategy_config: dict, market_data: list):
        self.portfolio = portfolio_status
        self.strategy = strategy_config
        
        # 将市场数据转为易查字典 {symbol: {close, RSI, ...}}
        self.market_map = {
            item['symbol']: {
                "close": item.get('close', 0.0),
                "rsi": item.get('indicators', {}).get('RSI', 50)
            }
            for item in market_data
        }

    def _get_category_weight(self, term: str) -> float:
        """根据 strategy_profile.yaml 动态解析该资产所属的池子权重"""
        mapping = self.strategy.get('rebalance_rules', {}).get('category_mapping', {})
        struct = self.strategy.get('portfolio_structure', {})
        
        if term in mapping.get('core', ['long']):
            return float(struct.get('core_weight', 0.70))
        elif term in mapping.get('satellite', ['mid', 'short']):
            return float(struct.get('satellite_weight', 0.30))
        return 0.0

    def generate_trade_list(self) -> list:
        total_assets = self.portfolio.get('total_assets', 0.0)
        available_cash = self.portfolio.get('cash', 0.0)
        holdings = self.portfolio.get('holdings', [])
        
        if total_assets <= 0:
            return[]

        rules = self.strategy.get('rebalance_rules', {})
        tolerance = float(rules.get('tolerance_threshold', 0.05))
        dca_period = int(rules.get('dca_build_period', 60))
        dca_dynamic = rules.get('dca_dynamic_adjust', True)

        # 1. 统计各个池子里的标的数量，以便平分权重 (假设同池均分，也可按用户设定扩展)
        pool_counts = {'core': 0, 'satellite': 0}
        mapping = rules.get('category_mapping', {'core': ['long'], 'satellite':['mid', 'short']})
        
        for h in holdings:
            term = h.get('user_intent', {}).get('term', 'unknown')
            if term in mapping.get('core', []): pool_counts['core'] += 1
            elif term in mapping.get('satellite', []): pool_counts['satellite'] += 1

        trade_list =[]
        expected_cash_change = 0.0  # 追踪理论资金变化

        # 2. 遍历所有持仓，计算交易指令
        for h in holdings:
            symbol = h['symbol']
            current_value = h['position_value']
            term = h.get('user_intent', {}).get('term', 'unknown')
            strategy = h.get('user_intent', {}).get('strategy', 'unknown')
            
            # 获取实时价格和指标
            mkt_info = self.market_map.get(symbol)
            if not mkt_info or mkt_info['close'] <= 0:
                continue
            current_price = mkt_info['close']
            current_rsi = mkt_info['rsi']

            # 计算该标的的目标市值
            pool_weight = self._get_category_weight(term)
            pool_name = 'core' if term in mapping.get('core',[]) else 'satellite'
            count_in_pool = pool_counts.get(pool_name, 1)
            
            # 单标的目标市值 = 总资产 * 池总权重 / 池内标的数量
            target_value = total_assets * (pool_weight / count_in_pool) if count_in_pool > 0 else 0
            gap_value = target_value - current_value  # >0 需买入, <0 需卖出

            action = None
            target_trade_value = 0.0
            reason_msg = ""

            # 获取该标的专属的 Regime (如果没拿到，默认当震荡市处理)
            current_regime = mkt_info.get('regime', 'Shock')

            # ==========================================
            # 核心算法 A: 动态定投逻辑 (Regime-Aware DCA)
            # ==========================================
            if strategy == 'dca' and gap_value > 0:
                base_daily_buy = target_value / dca_period
                multiplier = 1.0
                
                if dca_dynamic:
                    if current_regime in ['Bear', 'Panic', 'Correction']:
                        # 熊市/恐慌/宏观回调：防接飞刀。RSI再低也不能满目加仓。
                        if current_rsi < 35: multiplier = 0.5   # 阴跌不休，半仓定投(防深跌)
                        elif current_rsi > 50: multiplier = 0.0 # 稍有反弹就停止买入
                        else: multiplier = 0.8                  # 默认防守减速
                        reason_msg = f"动态定投: 体制[{current_regime}], 规避接飞刀, 乘数={multiplier}x"
                        
                    elif current_regime in ['Aggressive Bull', 'Passive Bull']:
                        # 牛市：千金难买牛回头。强势不恐高。
                        if current_rsi < 45: multiplier = 1.5   # 牛市回踩，加速买入
                        elif current_rsi > 80: multiplier = 1.0 # 极度超买，维持正常定投，不减速！
                        else: multiplier = 1.2                  # 默认顺势加速
                        reason_msg = f"动态定投: 体制[{current_regime}], 顺势定投, 乘数={multiplier}x"
                        
                    else:
                        # 震荡市 (Shock / Unknown)：回归高抛低吸
                        if current_rsi < 35: multiplier = 1.5
                        elif current_rsi > 65: multiplier = 0.5
                        reason_msg = f"动态定投: 体制[{current_regime}], 震荡高抛低吸, 乘数={multiplier}x"
                
                target_trade_value = base_daily_buy * multiplier
                # 兜底：不能超过实际缺口
                if target_trade_value > gap_value:
                    target_trade_value = gap_value
                    
                if target_trade_value > 0:
                    action = "BUY"
                    # 如果前面没设 reason_msg，补上默认的
                    if not reason_msg: reason_msg = f"动态定投: 基础乘数"

            # ==========================================
            # 核心算法 B: 存量资产重平衡 (非 DCA 或 卖出)
            # ==========================================
            else:
                deviation_pct = abs(gap_value) / total_assets
                # 如果偏离度大于容忍阈值，触发调仓
                if deviation_pct > tolerance:
                    action = "BUY" if gap_value > 0 else "SELL"
                    target_trade_value = abs(gap_value)
                    reason_msg = f"权重偏离度 {deviation_pct*100:.1f}% > 阈值 {tolerance*100:.1f}%"

            # ==========================================
            # 份额取整与生成订单
            # ==========================================
            if action and target_trade_value > 0:
                raw_shares = target_trade_value / current_price
                
                # A股和ETF：必须是 100 的整数倍向下取整
                if symbol.startswith(('sh', 'sz', 'us.')):
                    final_shares = math.floor(raw_shares / 100) * 100
                else:
                    # 场外基金 (otc_fund): 保留两位小数
                    final_shares = round(raw_shares, 2)

                if final_shares > 0:
                    trade_amount = round(final_shares * current_price, 2)
                    
                    # 如果是卖出，必须检查是否超过可用持仓
                    if action == "SELL":
                        current_shares = h.get('position_value', 0) / current_price # 估算或读取真实 shares
                        # 如果建议卖出量大于或接近持有量，修正为清仓
                        if final_shares >= current_shares * 0.99:
                            final_shares = current_shares
                            trade_amount = round(final_shares * current_price, 2)

                    trade_list.append({
                        "name": h['name'],
                        "symbol": symbol,
                        "action": action,
                        "shares": final_shares,
                        "price": current_price,
                        "amount": trade_amount,
                        "reason": reason_msg
                    })

        # 3. 可用资金兜底校验 (Safety Check)
        # 确保所有的 BUY 订单加起来不超过 (当前现金 + 预计的 SELL 获得现金)
        total_sell_cash = sum(t['amount'] for t in trade_list if t['action'] == 'SELL')
        max_buy_power = available_cash + total_sell_cash
        
        total_buy_needed = sum(t['amount'] for t in trade_list if t['action'] == 'BUY')
        
        if total_buy_needed > max_buy_power and max_buy_power > 0:
            # 资金不足，按比例削减所有 BUY 订单
            reduce_ratio = max_buy_power / total_buy_needed
            for t in trade_list:
                if t['action'] == 'BUY':
                    raw_shares = t['shares'] * reduce_ratio
                    # 重新取整
                    if t['symbol'].startswith(('sh', 'sz', 'us.')):
                        t['shares'] = math.floor(raw_shares / 100) * 100
                    else:
                        t['shares'] = round(raw_shares, 2)
                    t['amount'] = round(t['shares'] * t['price'], 2)
                    t['reason'] += " (因资金不足已按比例降级)"
        elif total_buy_needed > max_buy_power and max_buy_power <= 0:
            # 彻底没钱了，清空 BUY 订单
            trade_list = [t for t in trade_list if t['action'] != 'BUY']

        # 清理由于削减导致 shares == 0 的无效订单
        trade_list =[t for t in trade_list if t['shares'] > 0]

        return trade_list
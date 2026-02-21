import os
import yaml
import logging
import pandas as pd
import akshare as ak
from typing import Dict, Optional, Any

# 日志配置
logger = logging.getLogger(__name__)

class ValuationManager:
    """
    Agent 投资系统 - 估值获取模块 (完全解耦 V3.0)
    双擎驱动：
    1. 指数/ETF 引擎：利用 `track_index` 请求中证官网获取绝对 PE。
    2. 个股引擎：拉取 A股实时行情大表，提取动态 PE 和 PB。
    """

    def __init__(self, config_path: str = "config/portfolio.yaml"):
        self.config_path = config_path
        self.holdings_config = self._load_config()
        # 个股大表缓存：避免多次请求浪费时间
        self._stock_spot_data = None 

    def _load_config(self) -> Dict[str, Any]:
        """加载 portfolio.yaml，以 symbol 为主键"""
        if not os.path.exists(self.config_path):
            logger.warning(f"[Valuation] 配置文件缺失: {self.config_path}")
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            if not config or 'holdings' not in config:
                return {}
            # 只提取带有 symbol 字段的资产
            return {str(item.get('symbol')): item for item in config.get('holdings', []) if 'symbol' in item}
        except Exception as e:
            logger.error(f"[Valuation] 解析配置文件失败: {e}")
            return {}

    def _fetch_stock_spot_data(self):
        """惰性加载：拉取全市场个股实时行情大表 (仅执行一次)"""
        if self._stock_spot_data is None:
            logger.info("[Valuation] 首次查询个股，正在拉取全市场实时行情大表 (需耗时数秒)...")
            try:
                self._stock_spot_data = ak.stock_zh_a_spot_em()
                logger.info(f"[Valuation] 成功拉取个股大表，共 {len(self._stock_spot_data)} 只股票缓存完毕。")
            except Exception as e:
                logger.error(f"[Valuation] 拉取行情大表失败: {e}")
                self._stock_spot_data = pd.DataFrame() # 设为空表防止无限重试

    def _get_index_valuation(self, track_index: str) -> Dict:
        """引擎 1：获取指数估值 (中证官网)"""
        clean_code = ''.join(filter(str.isdigit, str(track_index)))
        res = {'pe': None, 'pb': None, 'dividend_yield': None, 'date': None, 'type': '指数'}
        try:
            df = ak.stock_zh_index_value_csindex(symbol=clean_code)
            if df is not None and not pd.to_datetime(df['日期']).empty:
                # 统一回归到最稳健的 市盈率1 (静态/动态口径)
                res['pe'] = float(df['市盈率1'].iloc[-1])
                res['dividend_yield'] = float(df['股息率1'].iloc[-1])
                res['date'] = str(df['日期'].iloc[-1]) # 记录数据日期，提醒 AI 时效性
        except Exception as e:
            logger.debug(f"[Valuation] 指数 {track_index} 估值获取失败: {e}")
        return res

    def _get_stock_valuation(self, symbol: str) -> Dict:
        """引擎 2：获取个股估值 (东财大表缓存)"""
        clean_code = ''.join(filter(str.isdigit, str(symbol)))
        res = {'pe': None, 'pb': None, 'dividend_yield': None, 'type': '个股'}
        
        # 确保大表已被加载
        self._fetch_stock_spot_data()
        
        if self._stock_spot_data is not None and not self._stock_spot_data.empty:
            try:
                target_row = self._stock_spot_data[self._stock_spot_data['代码'] == clean_code]
                if not target_row.empty:
                    res['pe'] = float(target_row['市盈率-动态'].values[0])
                    res['pb'] = float(target_row['市净率'].values[0])
            except Exception as e:
                logger.debug(f"[Valuation] 个股 {clean_code} 数据提取失败: {e}")
        return res

    def get_valuation(self, symbol: str) -> Dict:
        """
        Agent 调用的主入口
        """
        asset_info = self.holdings_config.get(symbol)
        
        if not asset_info:
            return {'pe': None, 'pb': None, 'status': '未知', 'msg': '该标的不在配置文件中'}

        # 根据是否配置了 track_index，自动路由到对应引擎
        track_index = asset_info.get('track_index')
        
        if track_index:
            logger.info(f"[Valuation] 标的 {symbol} 识别为 ETF，正追踪指数 {track_index}")
            data = self._get_index_valuation(track_index)
        else:
            logger.info(f"[Valuation] 标的 {symbol} 识别为个股，准备读取大表")
            data = self._get_stock_valuation(symbol)
            
        # 统一输出结构 (抛弃写死的判断，交由 LLM 裁决)
        data['msg'] = '获取成功' if data['pe'] is not None else '暂无估值数据(请依靠技术面决策)'
        data['status'] = '需大模型结合行业常识自行判定' 
        return data

if __name__ == "__main__":
    # 测试模块
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # 初始化估值管理器
    vm = ValuationManager()
    
    # 模拟 YAML 配置进行测试
    print("\n" + "="*50)
    print("🚀 开始全量解耦测试")
    print("="*50)
    
    for sym in vm.holdings_config.keys():
        print(f"\n---> 正在评估: {sym}")
        result = vm.get_valuation(sym)
        print(f"📊 结果: {result}")
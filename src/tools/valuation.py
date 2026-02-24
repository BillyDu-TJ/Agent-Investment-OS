# src/tools/valuation.py

import os
import yaml
import logging
import pandas as pd
import akshare as ak
from typing import Dict, Optional, Any
from src.utils.network import no_proxy_context  # [Phase 4.5] 引入隔离工具

# 日志配置
logger = logging.getLogger(__name__)

class ValuationManager:
    """
    Agent 投资系统 - 估值获取模块
    """

    def __init__(self, config_path: str = "config/portfolio.yaml"):
        self.config_path = config_path
        self.holdings_config = self._load_config()
        self._stock_spot_data = None 

    def _load_config(self) -> Dict[str, Any]:
        """加载 portfolio.yaml"""
        if not os.path.exists(self.config_path):
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            if not config or 'holdings' not in config:
                return {}
            return {str(item.get('symbol')): item for item in config.get('holdings', []) if 'symbol' in item}
        except Exception as e:
            logger.error(f"[Valuation] 解析配置文件失败: {e}")
            return {}

    def _fetch_stock_spot_data(self):
        """
        惰性加载：拉取全市场个股实时行情大表
        [Phase 4.5 修复]: 使用 no_proxy_context 强制绕过系统代理
        """
        if self._stock_spot_data is None:
            logger.info("[Valuation] 首次查询，正在拉取A股全市场估值大表 (需强制直连)...")
            try:
                # === 关键修改点 ===
                with no_proxy_context():
                    # 这里的数据量较大，东财接口容易超时，增加重试机制或单纯的直连
                    self._stock_spot_data = ak.stock_zh_a_spot_em()
                
                logger.info(f"[Valuation] 成功拉取大表，共 {len(self._stock_spot_data)} 条数据。")
            except Exception as e:
                # 捕获具体的网络错误信息
                logger.error(f"[Valuation] 拉取行情大表失败: {e}")
                self._stock_spot_data = pd.DataFrame() 

    def _get_index_valuation(self, track_index: str) -> Dict:
        """引擎 1：获取指数估值 (中证官网)"""
        clean_code = ''.join(filter(str.isdigit, str(track_index)))
        res = {'pe': None, 'pb': None, 'dividend_yield': None, 'date': None, 'type': '指数'}
        try:
            # 同样应用直连隔离，防止中证官网接口被代理拦截
            with no_proxy_context():
                df = ak.stock_zh_index_value_csindex(symbol=clean_code)
                
            if df is not None and not pd.to_datetime(df['日期']).empty:
                res['pe'] = float(df['市盈率1'].iloc[-1])
                res['dividend_yield'] = float(df['股息率1'].iloc[-1])
                res['date'] = str(df['日期'].iloc[-1]) 
        except Exception as e:
            logger.debug(f"[Valuation] 指数 {track_index} 估值获取失败: {e}")
        return res

    def _get_stock_valuation(self, symbol: str) -> Dict:
        """引擎 2：获取个股估值 (查大表)"""
        clean_code = ''.join(filter(str.isdigit, str(symbol)))
        res = {'pe': None, 'pb': None, 'type': '个股'}
        
        self._fetch_stock_spot_data()
        
        if self._stock_spot_data is not None and not self._stock_spot_data.empty:
            try:
                # 兼容不同列名 (东财接口有时列名会有微调)
                # 通常是 '代码', '市盈率-动态', '市净率'
                target_row = self._stock_spot_data[self._stock_spot_data['代码'] == clean_code]
                if not target_row.empty:
                    # 安全获取，处理 None 或非数字情况
                    pe_val = target_row['市盈率-动态'].values[0]
                    pb_val = target_row['市净率'].values[0]
                    
                    res['pe'] = float(pe_val) if pd.notna(pe_val) else None
                    res['pb'] = float(pb_val) if pd.notna(pb_val) else None
            except Exception as e:
                logger.debug(f"[Valuation] 个股 {clean_code} 数据提取失败: {e}")
        return res

    def get_valuation(self, symbol: str) -> Dict:
        """入口"""
        asset_info = self.holdings_config.get(symbol)
        
        # 1. 基础拦截
        if not asset_info:
            if str(symbol).startswith("us."):
                return {'pe': None, 'pb': None, 'status': '跳过', 'msg': '美股指数暂无实时估值'}
            return {'pe': None, 'pb': None, 'status': '未知', 'msg': '未配置'}

        # 2. 类型拦截
        asset_type = asset_info.get('type', 'stock')
        if asset_type in ['us_index', 'gold', 'bond', 'commodity', 'otc_fund']:
             return {'pe': None, 'pb': None, 'status': '跳过', 'msg': f'{asset_type} 无需估值'}

        # 3. 路由
        track_index = asset_info.get('track_index')
        if track_index:
            return self._get_index_valuation(track_index)
        else:
            return self._get_stock_valuation(symbol)
# src/tools/valuation.py

import os
import yaml
import logging
import pandas as pd
import akshare as ak
from typing import Dict, Optional, Any
from src.utils.network import proxy_context  

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
        """
        if self._stock_spot_data is None:
            logger.info("[Valuation] 首次查询，正在拉取A股全市场估值大表 (需强制直连)...")
            try:
                # === 关键修改点 ===
                with proxy_context():
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
            logger.info(f"[Valuation] 正在获取指数 {clean_code} 的估值数据...")
            # 同样应用直连隔离，防止中证官网接口被代理拦截
            with proxy_context():
                df = ak.stock_zh_index_value_csindex(symbol=clean_code)

            logger.debug(f"[Valuation] 原始数据列名: {df.columns.tolist()}")
            logger.debug(f"[Valuation] 最新数据行: {df.iloc[-1].to_dict()}")
                
            if df is not None and not pd.to_datetime(df['日期']).empty:
                # 显式检查列是否存在
                if '市盈率1' in df.columns:
                    pe_value = df['市盈率1'].iloc[-1]
                    logger.info(f"[Valuation] PE 值: {pe_value}")
                    res['pe'] = float(pe_value) if pd.notna(pe_value) else None
                else:
                    logger.error(f"[Valuation] 列 '市盈率1' 不存在！可用列: {df.columns.tolist()}")
                
            if '股息率1' in df.columns:
                res['dividend_yield'] = float(df['股息率1'].iloc[-1])
            if '日期' in df.columns:
                res['date'] = str(df['日期'].iloc[-1])
        except Exception as e:
            logger.debug(f"[Valuation] 指数 {track_index} 估值获取失败: {e}")
        return res

    def _get_stock_valuation(self, symbol: str) -> Dict:
        """引擎 2：获取个股估值 (查大表)"""
        """引擎 2：获取个股估值"""
        res = {'pe': None, 'pb': None, 'type': '个股'}
        try:
            df = self._fetch_stock_spot_data()
            if df is not None and not df.empty:
                # [修复] 显式检查列是否存在
                code = ''.join(filter(str.isdigit, str(symbol)))
                row = df[df['代码'] == code]
                if not row.empty:
                    if '市盈率-动态' in df.columns:
                        res['pe'] = float(row['市盈率-动态'].values[0])
                    if '市净率' in df.columns:
                        res['pb'] = float(row['市净率'].values[0])
        except Exception as e:
            logger.error(f"[Valuation] 个股 {symbol} 估值获取失败: {e}", exc_info=True)
        return res

    def get_growth_rate(self, symbol: str) -> str:
        """[维度4新增] 获取个股净利润增速 (用于识别价值陷阱)"""
        # 1. 过滤非个股
        if str(symbol).startswith(("us.", "sh000", "sz399")) or len(str(symbol)) < 6:
            return "N/A"
            
        clean_code = ''.join(filter(str.isdigit, str(symbol)))
        try:
            with proxy_context():
                # 使用新浪财务摘要接口 (速度快)
                df = ak.stock_financial_abstract(symbol=clean_code)
                
            if df is None or df.empty:
                return "N/A"
                
            # 2. 按行查找逻辑
            # 寻找 '指标' 列中包含 '净利润' 且包含 '同比' 的行
            # 注意：列名可能是 '指标' 或 '选项'
            mask = df.iloc[:, 1].astype(str).str.contains("净利润") & df.iloc[:, 1].astype(str).str.contains("同比")
            target_rows = df[mask]
            
            if not target_rows.empty:
                # 取第一行（通常是净利润同比增长率）
                # 取第3列（索引2），通常是最近的一个报告期数据
                # 列结构预览: [选项, 指标, 20250930, 20250630...]
                val = target_rows.iloc[0, 2]
                return f"{val}%"
                
        except Exception:
            pass # 仅仅是辅助数据，失败了不阻断流程
            
        return "N/A"

    def get_valuation(self, symbol: str) -> Dict:
        """入口"""
        asset_info = self.holdings_config.get(symbol)
        
        # 1. 基础拦截 (直接返回 N/A 避免 None)
        if not asset_info:
            if str(symbol).startswith("us."):
                return {'pe': 'N/A', 'pb': 'N/A', 'status': '跳过', 'msg': '美股指数暂无实时估值'}
            return {'pe': 'N/A', 'pb': 'N/A', 'status': '未知', 'msg': '未配置'}

        # 2. 类型拦截
        asset_type = asset_info.get('type', 'stock')
        if asset_type in ['us_index', 'gold', 'bond', 'commodity', 'otc_fund']:
             return {'pe': 'N/A', 'pb': 'N/A', 'status': '跳过', 'msg': f'{asset_type} 无需估值'}

        # 3. 路由
        track_index = asset_info.get('track_index')
        if track_index:
            res = self._get_index_valuation(track_index)
        else:
            # [修复] 显式判断是否为指数：sh/sz 开头且长度为6位（如 sh000001）
            if str(symbol).lower().startswith(("sh", "sz")) and len(str(symbol)) == 6:
                res = self._get_index_valuation(symbol)
            else:
                res = self._get_stock_valuation(symbol)
            
        # [Bugfix] 统一清洗底层的 None 值为 "N/A"
        if res.get('pe') is None: res['pe'] = "N/A"
        if res.get('pb') is None: res['pb'] = "N/A"
        
        return res
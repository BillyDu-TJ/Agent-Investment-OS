# src/tools/market_hunter.py

import os
import json
import time
import requests
import pandas as pd
import akshare as ak
import logging
from src.utils.network import no_proxy_context

class MarketHunter:
    """基于腾讯 Chunking 策略的全市场量化选股流水线"""

    def __init__(self, industry_map_path="data/industry_map.json"):
        self.industry_map_path = industry_map_path
        self.raw_data = None
        self.industry_map = self._load_industry_map()

    def _load_industry_map(self):
        """加载本地行业映射缓存，若无则返回空字典（触发降级机制）"""
        if os.path.exists(self.industry_map_path):
            try:
                with open(self.industry_map_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def _fetch_universe_chunking(self):
        """使用腾讯 Chunking 策略秒级获取 5000+ 股票横截面数据"""
        logging.info("📡 MarketHunter 正在执行全市场 Chunking 扫描...")
        try:
            with no_proxy_context():
                df_codes = ak.stock_info_a_code_name()
        except Exception as e:
            logging.error(f"代码表获取失败: {e}")
            return pd.DataFrame()

        valid_codes = df_codes[df_codes['code'].str.startswith(('6', '0', '3'))]['code'].tolist()
        
        tencent_codes =[]
        for c in valid_codes:
            tencent_codes.append(f"sh{c}" if c.startswith('6') else f"sz{c}")

        batch_size = 80
        total_batches = (len(tencent_codes) // batch_size) + 1
        all_stock_data =[]
        session = requests.Session()

        with no_proxy_context():
            for i in range(total_batches):
                batch = tencent_codes[i*batch_size : (i+1)*batch_size]
                if not batch: break
                
                url = f"http://qt.gtimg.cn/q={','.join(batch)}"
                try:
                    resp = session.get(url, timeout=5)
                    if resp.status_code == 200:
                        lines = resp.text.split(';\n')
                        for line in lines:
                            if '="' not in line: continue
                            parts = line.split('="')[1].strip('";').split('~')
                            if len(parts) > 46:
                                try:
                                    all_stock_data.append({
                                        "代码": parts[2],
                                        "名称": parts[1],
                                        "最新价": float(parts[3]) if parts[3] else 0.0,
                                        "涨跌幅": float(parts[32]) if parts[32] else 0.0,
                                        "换手率": float(parts[38]) if parts[38] else 0.0,
                                        "PE": float(parts[39]) if parts[39] else 9999.0, # 缺失填极大值
                                        "PB": float(parts[46]) if parts[46] else 9999.0,
                                        "总市值": float(parts[45]) if parts[45] else 0.0
                                    })
                                except: continue
                except:
                    pass # 单批次超时不影响大局
                    
        return pd.DataFrame(all_stock_data)

    def hunt(self, strategy_config, top_n_industry=3, top_n_stocks=3):
        """
        双层漏斗量化猎杀引擎
        :param strategy_config: 包含 factors 字典的配置
        """
        df = self._fetch_universe_chunking()
        if df.empty: return {}

        # 1. 净化数据：剔除 ST 股、停牌股(无价格/无换手)
        df = df[~df['名称'].str.contains('ST|退')]
        df = df[(df['最新价'] > 0) & (df['换手率'] > 0)]
        # 拒绝价值陷阱，剔除亏损(PE<=0)和资不抵债(PB<=0)的公司
        df = df[(df['PE'] > 0) & (df['PB'] > 0)]

        # 2. 映射行业 (降级机制)
        if self.industry_map:
            df['行业'] = df['代码'].map(self.industry_map).fillna("未知/综合")
        else:
            df['行业'] = "全市场精选池" # 降级为单层漏斗

        # 3. 核心数学：计算基础因子的全市场百分位排名 (0.0 ~ 1.0)
        df['rank_momentum'] = df['涨跌幅'].rank(pct=True)
        df['rank_volatility'] = df['换手率'].rank(pct=True)
        df['rank_pe'] = df['PE'].rank(pct=True)  # 数值越大，PE越高
        df['rank_pb'] = df['PB'].rank(pct=True)
        
        # 衍生因子
        df['rank_dividend'] = (df['总市值'].rank(pct=True) + (1/(df['PB']+0.01)).rank(pct=True)) / 2

        # 4. 根据 YAML 权重动态打分
        df['Final_Score'] = 0.0
        factors = strategy_config.get('factors', {})
        
        for factor_name, weight in factors.items():
            # 动量类
            if 'momentum' in factor_name or 'kdj' in factor_name:
                df['Final_Score'] += df['rank_momentum'] * weight
            # 波动/量能类
            elif 'volatility' in factor_name or 'volume' in factor_name:
                df['Final_Score'] += df['rank_volatility'] * weight
            # 估值类 (负权重表示越低越好)
            elif 'pe' in factor_name or 'value' in factor_name:
                if weight < 0:
                    df['Final_Score'] += (1 - df['rank_pe']) * abs(weight)
                else:
                    df['Final_Score'] += df['rank_pe'] * weight
            # 红利类
            elif 'dividend' in factor_name:
                df['Final_Score'] += df['rank_dividend'] * weight

        # 5. 漏斗决选
        results = {}
        # A. 如果映射了行业，执行轮动逻辑
        if len(df['行业'].unique()) > 1:
            industry_avg = df.groupby('行业')['Final_Score'].mean().sort_values(ascending=False)
            top_industries = industry_avg.head(top_n_industry).index.tolist()
            
            for ind in top_industries:
                ind_df = df[df['行业'] == ind].sort_values(by='Final_Score', ascending=False).head(top_n_stocks)
                results[ind] = ind_df[['代码', '名称', '最新价', 'Final_Score', 'PE', '换手率']].to_dict('records')
        # B. 降级模式：直接输出全市场 Top N
        else:
            best_df = df.sort_values(by='Final_Score', ascending=False).head(top_n_stocks * top_n_industry)
            results["全市场精选池"] = best_df[['代码', '名称', '最新价', 'Final_Score', 'PE', '换手率']].to_dict('records')
            
        return results
# src/tools/performance_tracker.py

import os
import csv
from datetime import datetime
import pandas as pd
import logging

class PerformanceTracker:
    """账户净值(NAV)追踪器"""
    
    def __init__(self, history_path="data/nav_history.csv"):
        self.history_path = history_path
        if not os.path.exists(self.history_path):
            with open(self.history_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Total_NAV", "Daily_Return_Pct"])

    def record_nav(self, current_nav: float):
        """记录今天的总资产"""
        today = datetime.now().strftime("%Y-%m-%d")
        df = pd.DataFrame()
        
        if os.path.exists(self.history_path):
            try:
                df = pd.read_csv(self.history_path)
            except Exception: pass
            
        # 防止同一天多次运行导致重复记录
        if not df.empty and df.iloc[-1]['Date'] == today:
            return 
            
        last_nav = df.iloc[-1]['Total_NAV'] if not df.empty else current_nav
        daily_return = ((current_nav - last_nav) / last_nav * 100) if last_nav > 0 else 0.0
        
        with open(self.history_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([today, round(current_nav, 2), round(daily_return, 2)])
            
        logging.info(f"📊 今日资产净值已记录: {current_nav:.2f} (日收益: {daily_return:.2f}%)")

    def get_weekly_return(self) -> str:
        """读取最近一周（约5个交易日）的累计收益"""
        if not os.path.exists(self.history_path): return "0.00%"
        try:
            df = pd.read_csv(self.history_path)
            if len(df) < 2: return "0.00%"
            
            # 取最近 6 条记录（对比前5天）
            recent = df.tail(6) 
            start_nav = recent.iloc[0]['Total_NAV']
            end_nav = recent.iloc[-1]['Total_NAV']
            
            wk_return = ((end_nav - start_nav) / start_nav) * 100
            emoji = "🔴" if wk_return >= 0 else "🟢"
            return f"{emoji} {wk_return:.2f}%"
        except Exception:
            return "N/A"
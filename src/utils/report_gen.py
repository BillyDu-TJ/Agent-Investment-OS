# src/utils/report_gen.py

import os
from datetime import datetime
from typing import List, Dict

class ReportGenerator:
    """
    负责将市场数据转换为 Obsidian 友好的 Markdown 日报。
    [Phase 5 升级]: 实现宏观/微观双表分离，强化指标的视觉预警。
    """

    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _get_value(self, data, key_path):
        parts = key_path.split('.')
        for p in parts:
            if isinstance(data, dict):
                data = data.get(p, "-")
            else:
                return "-"
        return data

    def _render_table(self, data_list: list, col_config: list, title: str) -> list:
        """辅助函数：渲染单个 Markdown 表格"""
        if not data_list:
            return []
            
        lines =[f"\n### {title}\n"]
        headers = [c[0] for c in col_config]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for item in data_list:
            row_cells =[]
            for _, key_path in col_config:
                val = self._get_value(item, key_path)
                
                # [Phase 6 视觉增强] 数据视觉化渲染 (状态灯映射)
                if key_path == "change_pct":
                    emoji = "🔴" if isinstance(val, (int, float)) and val >= 0 else "🟢"
                    val = f"{emoji} {val}%" if val != "-" else "-"
                elif key_path == "indicators.RSI":
                    try:
                        r_val = float(val)
                        if r_val >= 70: val = f"🔥 {r_val}"
                        elif r_val <= 30: val = f"❄️ {r_val}"
                        else: val = f"🟢 {r_val}"
                    except: pass
                elif key_path == "indicators.K":
                    try:
                        k_val = float(val)
                        if k_val >= 80: val = f"⚠️ {k_val}(超买)"
                        elif k_val <= 20: val = f"💎 {k_val}(超卖)"
                        else: val = f"✅ {k_val}"
                    except: pass
                elif key_path == "indicators.Bollinger":
                    if val == "Upper": val = "⚠️ 触顶"
                    elif val == "Lower": val = "💎 触底"
                    elif val == "Mid": val = "✅ 中轨"
                elif key_path == "regime":
                    regime_map = {
                        "Aggressive Bull": "🚀 快牛",
                        "Passive Bull": "🐂 慢牛",
                        "Correction": "⚠️ 回调",
                        "Bear": "📉 熊市",
                        "Panic": "😱 恐慌",
                        "Shock": "⚖️ 震荡"
                    }
                    val = regime_map.get(val, f"❓ {val}")

                row_cells.append(str(val))
            lines.append("| " + " | ".join(row_cells) + " |")
        
        return lines

    def generate_daily_report(self, market_data: list, col_config: list, portfolio_status: dict = None) -> str:
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.output_dir, f"{today_str}_Daily_Brief.md")

        lines =[
            "---",
            f"date: {today_str}",
            "tags:[投资日报, 自动生成]",
            "---\n",
            f"# 📈 市场感知日报 ({today_str})\n"
        ]

        #[Phase 6 核心] 财务总览 (Financial Overview)
        if portfolio_status:
            total_assets = portfolio_status.get('total_assets', 0)
            cash = portfolio_status.get('cash', 0)
            cash_pct = round((cash / total_assets) * 100, 2) if total_assets > 0 else 0
            
            # 计算持仓总盈亏 (金额估算 = 现值 - 成本总值，或者通过盈亏率反推)
            total_pnl = sum([h.get('position_value', 0) - (h.get('position_value', 0) / (1 + h.get('profit_loss_ratio', 0)/100)) for h in portfolio_status.get('holdings', [])])
            pnl_emoji = "🔴" if total_pnl >= 0 else "🟢"

            lines.extend([
                "## 💰 账户全局概览",
                f"- **总资产市值**: ¥{total_assets:,.2f}  |  **当前现金占比**: {cash_pct}% (¥{cash:,.2f})",
                f"- **当前持仓总浮盈/亏**: {pnl_emoji} ¥{total_pnl:,.2f}",
                "\n### 💼 持仓摘要",
                "| 标的 | 仓位占比 | 盈亏状况 |",
                "| :--- | :--- | :--- |"
            ])
            for h in portfolio_status.get('holdings',[]):
                h_pnl_emoji = "🔴" if h.get('profit_loss_ratio', 0) >= 0 else "🟢"
                lines.append(f"| {h.get('name')} | {h.get('weight_pct', 0)}% | {h_pnl_emoji} {h.get('profit_loss_ratio', 0)}% |")
            lines.append("\n---\n")

        # 数据分流
        macro_data = [d for d in market_data if d.get('type') in['index', 'us_index']]
        micro_data =[d for d in market_data if d.get('type') not in ['index', 'us_index']]

        # 渲染双表
        lines.extend(self._render_table(macro_data, col_config, "🌍 全球宏观与宽基阵列"))
        lines.extend(self._render_table(micro_data, col_config, "💼 微观持仓与行业资产"))

        # 信号总结部分
        lines.append("\n## 💡 自动化诊断")
        for item in market_data:
            lines.append(f"- **{item['name']}**: {item.get('signal_summary', '无')}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return file_path
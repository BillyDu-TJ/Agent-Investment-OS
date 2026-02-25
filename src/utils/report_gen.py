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
                
                # [Phase 5 增强] 数据视觉化渲染
                if key_path == "change_pct":
                    emoji = "🔴" if isinstance(val, (int, float)) and val >= 0 else "🟢"
                    val = f"{emoji} {val}%" if val != "-" else "-"
                elif key_path == "indicators.K":
                    try:
                        k_val = float(val)
                        if k_val > 80: val = f"🔥 {k_val}"
                        elif k_val < 20: val = f"❄️ {k_val}"
                    except: pass

                row_cells.append(str(val))
            lines.append("| " + " | ".join(row_cells) + " |")
        
        return lines

    def generate_daily_report(self, market_data: list, col_config: list) -> str:
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.output_dir, f"{today_str}_Daily_Brief.md")

        lines = [
            "---",
            f"date: {today_str}",
            "tags:[投资日报, 自动生成]",
            "---\n",
            f"# 📈 市场感知日报 ({today_str})\n"
        ]

        # [Phase 5 核心] 数据分流
        macro_data = [d for d in market_data if d.get('type') in ['index', 'us_index']]
        micro_data = [d for d in market_data if d.get('type') not in['index', 'us_index']]

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
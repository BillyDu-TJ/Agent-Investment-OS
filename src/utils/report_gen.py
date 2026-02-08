# src/utils/report_gen.py

import os
from datetime import datetime
from typing import List, Dict

class ReportGenerator:
    """
    负责将市场数据转换为 Obsidian 友好的 Markdown 日报。
    """

    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _get_value(self, data, key_path):
        """支撑嵌套访问，如 'indicators.RSI'"""
        parts = key_path.split('.')
        for p in parts:
            if isinstance(data, dict):
                data = data.get(p, "-")
            else:
                return "-"
        return data

    def _get_rsi_status(self, rsi: float) -> str:
        """根据 RSI 数值返回描述文案"""
        if rsi >= 70:
            return "🔥 RSI过热"
        elif rsi <= 30:
            return "❄️ RSI超卖"
        else:
            return "⚖️ RSI中性"

    def generate_daily_report(self, market_data: list, col_config: list) -> str:
        """
        col_config 格式: [("显示名", "数据Key"), ...]
        示例: [("名称", "name"), ("RSI", "indicators.RSI")]
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(self.output_dir, f"{today_str}_Daily_Brief.md")

        lines = [
            "---",
            f"date: {today_str}",
            "tags: [投资日报, 自动生成]",
            "---\n",
            f"# 📈 市场感知日报 ({today_str})\n"
        ]

        # 动态生成表格表头
        headers = [c[0] for c in col_config]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # 动态填充表格数据
        for item in market_data:
            row_cells = []
            for _, key_path in col_config:
                val = self._get_value(item, key_path)
                
                # 特殊格式处理（仅针对特定 Key 进行增强，不影响整体通用性）
                if key_path == "change_pct":
                    emoji = "🔴" if val >= 0 else "🟢"
                    val = f"{emoji} {val}%"
                
                row_cells.append(str(val))
            lines.append("| " + " | ".join(row_cells) + " |")

        # 信号总结部分
        lines.append("\n## 💡 自动化诊断")
        for item in market_data:
            lines.append(f"- **{item['name']}**: {item.get('signal_summary', '无')}")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return file_path
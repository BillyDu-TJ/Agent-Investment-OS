# src/core/memory.py

import os
import glob
import re
from datetime import datetime
import logging
import json

class ContextLoader:
    """
    Agent 的长期记忆检索引擎。
    负责扫描本地文件系统，提取过去 N 天的核心诊断与操作指令，浓缩为上下文。
    """

    def __init__(self, reports_dir="reports"):
        self.reports_dir = reports_dir

    def _extract_section(self, filepath: str, keyword: str, stop_prefix: str = "##") -> str:
        """
        从 Markdown 文件中按块提取包含特定关键字的章节。
        """
        if not os.path.exists(filepath):
            return ""
        
        extracted = []
        capturing = False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    # 碰到关键字，开始捕获
                    if keyword in line:
                        capturing = True
                        continue
                    
                    if capturing:
                        # 如果碰到下一个同级或高级标题，且不是当前标题，则停止捕获
                        if line.startswith(stop_prefix) and keyword not in line:
                            break
                        # 过滤空行，保留实质内容
                        if line.strip():
                            extracted.append(line.strip())
            
            return "\n".join(extracted)
        except Exception as e:
            logging.debug(f"提取记忆失败 {filepath}: {e}")
            return ""

    def load_history(self, days=3) -> str:
        """
        加载最近 N 天的记忆摘要
        """
        if not os.path.exists(self.reports_dir):
            return "无历史记录。"

        # 获取所有 AI 顾问报告，作为日期锚点
        files = glob.glob(os.path.join(self.reports_dir, "*_AI_Advisor.md"))
        
        # 提取历史日期
        date_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_AI_Advisor\.md")
        dates = []
        for f in files:
            basename = os.path.basename(f)
            match = date_pattern.search(basename)
            if match:
                dates.append(match.group(1))
        
        # 降序排列
        dates.sort(reverse=True)
        
        # 排除今天的记录（因为今天是我们要预测和分析的，不要把正在生成的混进去）
        today_str = datetime.now().strftime("%Y-%m-%d")
        dates = [d for d in dates if d != today_str]
        
        # 截取最近的 N 天
        target_dates = dates[:days]
        # 重新升序排列（T-3, T-2, T-1），符合时间发展逻辑
        target_dates.sort()

        if not target_dates:
            return "这是您的第一次运行，暂无历史记忆记录。"

        history_texts = []
        for d in target_dates:
            advisor_path = os.path.join(self.reports_dir, f"{d}_AI_Advisor.md")
            brief_path = os.path.join(self.reports_dir, f"{d}_Daily_Brief.md")
            
            # 提取客观诊断
            diagnosis = self._extract_section(brief_path, "💡 自动化诊断")
            if not diagnosis:
                diagnosis = "无自动化诊断记录。"
                
            # 提取主观决策
            decisions = self._extract_section(advisor_path, "【操作指令摘要】")
            if not decisions:
                decisions = "无操作指令记录。"

            # 组装为记忆块
            day_memory = f"📅 [历史记忆: {d}]\n> 市场技术诊断:\n{diagnosis}\n> AI操作指令:\n{decisions}\n"
            history_texts.append(day_memory)

        return "\n".join(history_texts)
    
    def save_consensus(self, date_str, content):
        """保存 CIO 的最终共识摘要 (JSON)"""
        memory_path = "data/long_term_memory.json"
        data = {}
        if os.path.exists(memory_path):
            try:
                with open(memory_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except: pass
        
        data['last_update'] = date_str
        data['consensus'] = content
        
        with open(memory_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_consensus(self):
        """读取上一日的共识"""
        memory_path = "data/long_term_memory.json"
        if os.path.exists(memory_path):
            try:
                with open(memory_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('consensus', '无历史共识。')
            except: pass
        return "无历史共识。"

# 测试代码
if __name__ == "__main__":
    loader = ContextLoader()
    print("提取的长期记忆如下：")
    print("-" * 50)
    print(loader.load_history(days=3))
    print("-" * 50)
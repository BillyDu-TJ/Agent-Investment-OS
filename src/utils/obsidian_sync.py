# src/utils/obsidian_sync.py

import os
import shutil
import yaml
import logging
from datetime import datetime

class ObsidianSyncer:
    """
    Obsidian 知识库同步中枢。
    负责将生成的报告与交易日志无缝推送到用户的个人知识库中。
    """

    def __init__(self, settings_path="config/settings.yaml"):
        self.vault_root = self._load_vault_path(settings_path)
        self.is_active = False
        
        # 验证 Obsidian 路径是否存在
        if self.vault_root and os.path.exists(self.vault_root):
            self.is_active = True
            # 根据用户的截图，严格匹配目标文件夹名
            self.dashboard_dir = os.path.join(self.vault_root, "60_Dashboard")
            self.trade_dir = os.path.join(self.vault_root, "50_Trade_Journal")
            
            # 如果目标文件夹在 Obsidian 中还未创建，系统会帮您自动创建
            os.makedirs(self.dashboard_dir, exist_ok=True)
            os.makedirs(self.trade_dir, exist_ok=True)
            logging.info(f"🔗 Obsidian 同步模块已激活: {self.vault_root}")
        else:
            logging.warning("⚠️ Obsidian 路径未配置或不存在，归档功能已静默降级为本地 reports/ 目录。")

    def _load_vault_path(self, path: str) -> str:
        """安全读取 settings.yaml 中的路径"""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    settings = yaml.safe_load(f)
                    return settings.get('obsidian_vault_root', '').strip()
        except Exception as e:
            logging.debug(f"读取 Obsidian 配置失败: {e}")
        return ""

    def archive_daily_report(self, local_filepath: str):
        """将生成的报告归档至 60_Dashboard"""
        if not self.is_active or not os.path.exists(local_filepath):
            return
            
        try:
            filename = os.path.basename(local_filepath)
            target_path = os.path.join(self.dashboard_dir, filename)
            # 使用 copy2 连同文件的元数据（修改时间等）一起复制
            shutil.copy2(local_filepath, target_path)
            logging.info(f"📁 已同步至 Obsidian 看板: {target_path}")
        except Exception as e:
            logging.error(f"同步报告至 Obsidian 失败: {e}")

    def create_trade_journal(self, action: str, symbol: str, shares: float, price: float, context: str = "CLI 终端直接下达的指令"):
        """
        生成交易快照并归档至 50_Trade_Journal
        (如果未激活 Obsidian，则降级生成在本地 reports/ 目录下)
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H:%M:%S")
        action_upper = action.upper().replace("/", "") # 去掉 / 符号
        
        filename = f"{today_str}_{action_upper}_{symbol}.md"
        target_dir = self.trade_dir if self.is_active else "reports"
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            
        target_path = os.path.join(target_dir, filename)
        amount = round(shares * price, 2)
        
        # 构建具有完美双链格式的 Markdown 内容
        content = f"""---
date: {today_str} {time_str}
tags: [交易日志, {action_upper}, {symbol}]
---

# 📝 交易执行单: {action_upper} {symbol}

## 📊 交易明细
- **执行时间**: {today_str} {time_str}
- **交易方向**: **{action_upper}**
- **操作标的**: [[{symbol}]]  <!-- 预留双链位置 -->
- **成交单价**: {price}
- **成交份额**: {shares}
- **涉及资金**: {amount} 元

## 🧠 操作上下文 (Context Snapshot)
> 此次交易发生时的系统状态或思考：
{context}
"""
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            if self.is_active:
                logging.info(f"📓 交易单已送达 Obsidian: {filename}")
            else:
                logging.info(f"📓 交易单已生成本地备份: {filename}")
        except Exception as e:
            logging.error(f"生成交易单失败: {e}")
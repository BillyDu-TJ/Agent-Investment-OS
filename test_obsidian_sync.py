# test_obsidian_sync.py
import os
from src.utils.obsidian_sync import ObsidianSyncer

def run_test():
    print("="*50)
    print("🚀 开始测试 Obsidian 同步模块")
    print("="*50)

    # 1. 初始化同步器 (会自动读取 settings.yaml)
    syncer = ObsidianSyncer()
    
    if not syncer.is_active:
        print("\n❌ 测试中止：Obsidian 路径未配置或不存在。")
        print("请检查 config/settings.yaml 中的 obsidian_vault_root 配置。")
        return

    # --- 测试场景 A: 模拟日报归档 ---
    print("\n[测试 1/2] 模拟日报归档...")
    
    # 先在本地造一个假报告
    dummy_report = "reports/TEST_Daily_Brief.md"
    if not os.path.exists("reports"):
        os.makedirs("reports")
    with open(dummy_report, "w", encoding="utf-8") as f:
        f.write("# 这是一个测试报告\n用于验证 Obsidian 同步功能是否正常。")
    
    # 执行归档
    syncer.archive_daily_report(dummy_report)
    print("   -> 调用归档函数完成。请检查您的 Obsidian/60_Dashboard 文件夹。")

    # --- 测试场景 B: 模拟交易单生成 ---
    print("\n[测试 2/2] 模拟生成交易单...")
    
    # 执行生成
    syncer.create_trade_journal(
        action="BUY", 
        symbol="TEST_999999", 
        shares=1000, 
        price=8.88, 
        context="这是测试脚本生成的模拟交易上下文。"
    )
    print("   -> 调用交易单生成函数完成。请检查您的 Obsidian/50_Trade_Journal 文件夹。")

    print("\n" + "="*50)
    print("✅ 测试结束！如果您的 Obsidian 里出现了新文件，说明 Task 3 完美通过！")
    print("="*50)

if __name__ == "__main__":
    run_test()
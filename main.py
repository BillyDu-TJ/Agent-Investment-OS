# main.py

import logging
from src.tools.market_data import MarketData
from src.utils.report_gen import ReportGenerator

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    执行感知层任务流
    """
    try:
        # 1. 获取数据
        collector = MarketData()
        data = collector.get_market_summary()
    
        # 提取标的列表
        indices_data = data.get('indices', [])
        
        if not indices_data:
            logging.error("未能抓取到任何市场数据，程序终止。")
            return
    
        # 2. [高扩展性配置] 定义你想在报告表格中展示的列
        # 格式: (显示在MD表格的名字, 数据字典里的路径)
        # 如果以后你在 MarketData 里加了新指标指标 'KDJ'，只需在这里加一行 ("KDJ", "indicators.KDJ")
        MY_REPORT_COLUMNS = [
            ("指数名称", "name"),
            ("收盘价", "close"),
            ("涨跌幅", "change_pct"),
            ("成交额(亿)", "volume_e"),
            ("RSI", "indicators.RSI"),
            ("MACD状态", "indicators.MACD"),
            ("MA20", "indicators.MA20"),
        ]
    
        # 3. 生成 Markdown 报告
        reporter = ReportGenerator(output_dir="reports")
        report_path = reporter.generate_daily_report(indices_data, MY_REPORT_COLUMNS)
        
        # 4. 打印你要求的特定 Log 内容
        logging.info("✅ 成功完成感知层任务！")
        logging.info(f"📊 监测标的数量: {len(indices_data)}")
            
        # 额外预览
        logging.info(f"📄 报告已保存至: {report_path}")
    
    except Exception as e:
        logging.error(f"Pipeline 执行过程中出现异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
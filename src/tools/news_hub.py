# src/tools/news_hub.py

import feedparser
import requests
import logging
import json
import socket
from typing import List

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
socket.setdefaulttimeout(5.0)

class NewsHub:
    """
    真实新闻中心：以东方财富 7x24 快讯为主，获取无截断的完整财经新闻。
    """

    def __init__(self):
        # 1. 东方财富 API (首选，速度快，内容全)
        self.eastmoney_api = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html"
        
        # 2. 新浪 RSS (备选，作为补充)
        self.rss_source = "https://finance.sina.com.cn/7x24/rss.shtml"

    def _get_news_from_eastmoney(self) -> List[str]:
        """[首选] 通过东方财富 API 获取快讯"""
        titles = []
        try:
            logging.info("正在尝试连接东方财富快讯接口...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(self.eastmoney_api, headers=headers, timeout=5)
            
            if response.status_code == 200:
                text = response.text
                # 清洗 JS 包装，提取纯 JSON
                if "var ajaxResult=" in text:
                    json_str = text.replace("var ajaxResult=", "").strip()
                    if json_str.endswith(";"):
                        json_str = json_str[:-1]
                    
                    data = json.loads(json_str)
                    lives = data.get('LivesList', [])
                    
                    for item in lives:
                        # 优先获取 'digest' (详细摘要)，如果没有则取 'title'
                        content = item.get('digest', '')
                        if not content:
                            content = item.get('title', '')
                        
                        # 【修正点】不做任何长度截断，保留原汁原味的内容
                        if content and len(content) > 10: # 过滤掉太短的无意义信息
                            titles.append(content.strip())
            else:
                logging.warning(f"东方财富接口返回状态码: {response.status_code}")

        except Exception as e:
            logging.error(f"东方财富 API 获取失败: {e}")
        
        return titles

    def _get_news_from_rss(self) -> List[str]:
        """[备选] 通过 RSS 获取"""
        titles = []
        try:
            logging.info(f"正在尝试连接新浪 RSS...")
            feed = feedparser.parse(self.rss_source)
            if feed.bozo:
                logging.debug(f"RSS 解析遇到非致命错误: {feed.bozo_exception}")
            
            for entry in feed.entries[:15]:
                titles.append(entry.title)
        except Exception as e:
            logging.warning(f"RSS 连接超时或失败: {e}")
        return titles

    def get_recent_news(self) -> List[str]:
        """
        统一接口：获取最近的财经动态。
        """
        # 1. 优先调用东方财富
        news_list = self._get_news_from_eastmoney()
        
        # 2. 如果东方财富挂了（返回空），再尝试 RSS
        if not news_list:
            logging.warning("东方财富数据为空，启动 RSS Fallback...")
            news_list = self._get_news_from_rss()
        
        # 3. 去重 (保留顺序)
        seen = set()
        unique_news = []
        for x in news_list:
            if x not in seen:
                unique_news.append(x)
                seen.add(x)
        
        # 返回前 15 条
        final_news = unique_news[:15]
        
        if not final_news:
            logging.warning("未能获取任何新闻数据，将返回空列表。")
            return []
            
        logging.info(f"成功获取 {len(final_news)} 条真实新闻快讯。")
        return final_news

# --- 验证运行 ---
if __name__ == "__main__":
    hub = NewsHub()
    news = hub.get_recent_news()
    print("\n" + "="*50)
    print("今日 7x24 核心快讯 (完整版预览)：")
    print("="*50)
    if news:
        # 打印前3条完整内容，证明没有被截断
        for i, content in enumerate(news[:3], 1):
            print(f"[{i}] {content}\n" + "-"*30)
        print(f"... (共 {len(news)} 条)")
    else:
        print("无数据")
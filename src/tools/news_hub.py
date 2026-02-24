# src/tools/news_hub.py

import feedparser
import requests
import logging
import json
import socket
from typing import List
import re
from src.utils.network import no_proxy_context

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
            with no_proxy_context():
                response = requests.get(self.eastmoney_api, headers=headers, timeout=10)
            
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

            with no_proxy_context():
                feed = feedparser.parse(self.rss_source)
                
            if feed.bozo:
                logging.debug(f"RSS 解析遇到非致命错误: {feed.bozo_exception}")
            
            for entry in feed.entries[:15]:
                titles.append(entry.title)
        except Exception as e:
            logging.warning(f"RSS 连接超时或失败: {e}")
        return titles
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算两条新闻的关键词重合度 (简单 Jaccard 相似度)"""
        set1 = set(list(str1)) # 简单字符级去重，实战中可按词切分
        set2 = set(list(str2))
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0
    
    def _get_tokens(self, text: str) -> set:
        """分词提取器：只保留中文字符和英文单词，用于更精准的匹配"""
        return set(re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}', text))

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

        # 定义关键词权重
        weight_map = {
            # 1. 货币政策与流动性 (最高权重：影响所有资产定价)
            '加息': 12, '降息': 12, '降准': 12, '利息': 10, '美联储': 10, '央行': 10, 
            '流动性': 8, 'LPR': 9, '逆回购': 7, 'MLF': 7,
            
            # 2. 宏观经济数据 (中高权重：市场风向标)
            'CPI': 9, 'PPI': 9, 'PMI': 8, 'GDP': 9, '非农': 10, '失业率': 8, 
            '通胀': 8, '通缩': 8, '社融': 9, 'M2': 8,
            
            # 3. 核心监管与政策 (中权重：行业导向)
            '政策': 7, '反垄断': 8, '监管': 7, '证监会': 8, '禁令': 9, '关税': 10, 
            '贸易': 7, '制裁': 10, '刺激': 8, '地产政策': 9,
            
            # 4. 企业盈利与估值 (中低权重：个股/行业驱动)
            '净利润': 7, '营收': 6, '财报': 7, '扭亏': 8, '分红': 6, '回购': 7, 
            '增持': 6, '减持': -5, '破产': 12, '重组': 8,
            
            # 5. 地缘与突发风险 (长线/避险情绪)
            '冲突': 10, '导弹': 12, '战争': 12, '紧急状态': 9, '选举': 7, '政变': 12,
            
            # 6. 核心行业关键词 (增加相关性)
            '芯片': 7, '半导体': 7, '人工智能': 7, '光伏': 6, '新能源': 6, '银行': 5
        }

        # 噪音词库：一旦出现，直接大幅扣分，排除生活类干扰
        noise_keywords = [
            '预警', '寒潮', '天气', '降温', '地震', '车祸', '起火', '科普', 
            '祥和', '假期', '市民', '宣传', '志愿者', '查处', '侵犯财产'
        ]

        scored_items = []
        for text in news_list:
            tokens = self._get_tokens(text) # 使用我们之前的分词提取器
            score = sum([weight_map.get(t, 0) for t in tokens])

            # 噪音过滤逻辑
            for noise in noise_keywords:
                if noise in text:
                    score -= 20 # 强力降权

            scored_items.append({"text": text, "tokens": tokens, "score": score})

        # 评分从高到低
        scored_items.sort(key=lambda x: x['score'], reverse=True)

        final_news = []
        used_tokens = set()

        for item in scored_items:
            if len(final_news) >= 30: break # 30条高质量信息足够Agent决策
            
            # 计算当前新闻与已选新闻池的“关键词重合度”
            # 如果这篇新闻里的核心词（高权重词）有 40% 以上已经在前面出现过了，就跳过
            intersection = item['tokens'].intersection(used_tokens)
            if len(item['tokens']) > 0:
                overlap_ratio = len(intersection) / len(item['tokens'])
                if overlap_ratio > 0.3: # 降低阈值，更严格去重
                    continue
            
            final_news.append(item['text'])
            used_tokens.update(item['tokens']) # 将新词加入已读池

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
        for i, content in enumerate(news[:10], 1):
            print(f"[{i}] {content}\n" + "-"*30)
        print(f"... (共 {len(news)} 条)")
    else:
        print("无数据")
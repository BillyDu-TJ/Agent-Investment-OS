# 📝 Project Roadmap (v2.0)

## ✅ Phase 1: Infrastructure (基础感知)
- [x] 搭建 Python 项目骨架与虚拟环境。
- [x] 实现 `market_data.py`：基于腾讯接口抓取行情、计算 MA/RSI/MACD。
- [x] 实现 `report_gen.py`：自动生成 Markdown 日报。
- [x] 解决网络代理与反爬虫问题。

## ✅ Phase 2: The Cognition (初步大脑)
- [x] 接入 DeepSeek/OpenAI API。
- [x] 实现 `portfolio_manager.py`：读取持仓并计算基础盈亏。
- [x] 实现 `advisor.py`：基于 Mock 新闻 + 持仓数据生成 AI 建议。
- [x] 实现 CoT (思维链) Prompt 架构。

## 🚧 Phase 2.5: Strategy Refinement (策略精细化) - [当前重点]
> 目标：让 AI 听懂“定投”和“止损”的区别，并能识别牛熊。
- [x] **Task 2.1:** 更新 `config/portfolio.yaml` 结构，增加 `strategy` (策略) 和 `term` (周期) 字段。
- [x] **Task 2.2:** 修改 `portfolio_manager.py`，使其读取并传递这些新标签。
- [x] **Task 2.3:** 在 `src/core/` 下新建 `regime.py`，实现简单的市场体制判断逻辑（如基于均线系统的 Bull/Bear/Chop）。
- [x] **Task 2.4:** **重构 System Prompt**，注入“资产意图”和“市场体制”逻辑，测试 AI 是否能对不同资产给出差异化建议。

## 📅 Phase 3: The Reality Interface (真实世界接入)
> 目标：移除 Mock 数据，接入真实信息流与专家知识。
- [x] **Task 3.1:** 实现 `src/tools/news_hub.py`，接入 RSS (如财联社/华尔街见闻) 获取真实宏观简讯。
- [x] **Task 3.2:** (可选) 实现简单的舆情探针（抓取雪球/微博热度）。
- [ ] **Task 3.3:** 建立 `data/expert_knowledge.md`，存储专家语录与逻辑。
- [ ] **Task 3.4:** 实现基础 RAG，在 Prompt 中动态插入相关的专家逻辑。

## 🔮 Phase 4: Evolution (交互与进化)
- [x] 实现 CLI 聊天模式，允许用户对日报内容进行追问。
- [ ] 自动化回测模块。
- [ ] 风险预警推送 (微信/钉钉)。
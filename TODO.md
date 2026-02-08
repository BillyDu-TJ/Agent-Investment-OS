# 📝 Project Roadmap

## Phase 1: Infrastructure (当前阶段)
- [x] 初始化项目目录结构
- [x] 配置 Python 环境与依赖 (`requirements.txt`)
- [x] **Task 1:** 实现 `tools/market_data.py`，封装 AkShare 接口，获取大盘核心数据。
- [ ] **Task 2:** 实现 `utils/file_handler.py`，测试生成 Markdown 文件并写入 Obsidian 目录。

## Phase 2: The Brain (LLM Integration)
- [ ] 申请 DeepSeek/OpenAI API Key 并配置 `config/settings.yaml`。
- [ ] **Task 3:** 构建 `agents/scout.py` (宏观 Agent)，测试简单的 Prompt 交互。
- [ ] **Task 4:** 实现“数据+分析”的串联，让 AI 读取 Task 1 的数据并生成评论。

## Phase 3: The Soul (Expert Knowledge)
- [ ] 整理专家逻辑数据（CSV/JSON 格式）。
- [ ] **Task 5:** 实现简单的 RAG (检索增强生成)，让 Agent 回答时参考专家逻辑。
- [ ] **Task 5 (New):** 实现 `src/tools/portfolio_mgr.py`，能够读取 `portfolio.yaml` 并计算当前持仓的最新市值与盈亏。
- [ ] **Task 6 (New):** 升级 CIO Agent 的 Prompt 模板，将“当前持仓”作为核心变量传入，开启个性化诊断模式。

## Phase 4: Automation & Deployment
- [ ] 编写 `main.py` 主流程脚本。
- [ ] 配置系统定时任务 (Cron/Task Scheduler)。
- [ ] 集成消息推送 (PushPlus/钉钉)。
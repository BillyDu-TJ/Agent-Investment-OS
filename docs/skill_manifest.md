# Skill Manifest - Agentic-Investment-OS

> ReAct AI 可调用的技能清单 (v1.0)

本文档是 AI 智能体的**唯一技能真相来源**。所有工具调用必须遵循此处定义的输入输出契约。

---

## 工具列表

| 工具名 | 类别 | 功能摘要 |
|--------|------|----------|
| `market_fetch_price` | Market | 获取实时价格 |
| `market_get_indicators` | Market | 获取技术指标 |
| `market_get_volume` | Market | 量能异动分析 |
| `macro_get_valuation` | Macro | 获取估值数据 |
| `macro_get_global_snapshot` | Macro | 全球宏观快照 |
| `ledger_get_portfolio` | Ledger | 获取持仓快照 |
| `ledger_execute_trade` | Ledger | 执行虚拟交易 |
| `ledger_get_trade_reasoning` | Ledger | 获取交易理由 |

---

## Market 技能

### `market_fetch_price(symbol: str) -> dict`

**功能**: 获取金融标的的实时价格。

**参数**:
- `symbol` (必填): 标的代码
  - A 股：`sh600519`, `sz000001`
  - 港股：`hk00700`
  - 美股指数：`us.NDX`, `us.SPX`
  - 场外基金：`016452`

**返回**:
```json
{
  "status": "success",
  "data": {"symbol": "sh513130", "price": 0.78, "change_pct": -1.2},
  "message": "OK"
}
```

**失败示例**:
```json
{"status": "error", "message": "网络请求失败：timeout"}
```

---

### `market_get_indicators(symbol: str, indicators: List[str] = None) -> dict`

**功能**: 获取技术指标数据。

**参数**:
- `symbol` (必填): 标的代码
- `indicators` (可选): 指标列表，默认返回全部
  - 可选值：`["MA", "RSI", "MACD", "BOLL", "KDJ", "ATR", "Vol_Ratio"]`

**返回**:
```json
{
  "status": "success",
  "data": {
    "symbol": "sh513130",
    "indicators": {
      "RSI": 45.2,
      "MACD": {"macd": -0.002, "signal": -0.001, "hist": -0.001}
    }
  }
}
```

---

### `market_get_volume(symbol: str) -> dict`

**功能**: 量能异动分析（5 日均量 vs 当日成交量）。

**返回**:
```json
{
  "status": "success",
  "data": {"symbol": "sh513130", "vol_ratio": 1.8, "signal": "放量"}
}
```

**signal 可选值**: `放量`, `缩量`, `正常`

---

## Macro 技能

### `macro_get_valuation(symbol: str, asset_type: str = "auto") -> dict`

**功能**: 获取估值数据 (PE/PB/股息率)。

**参数**:
- `symbol` (必填): 标的代码
- `asset_type` (可选): 资产类型
  - 可选值：`"stock"`, `"index"`, `"us_index"`, `"gold"`, `"bond"`, `"commodity"`, `"otc_fund"`, `"auto"`

**能力边界**:
- 权益类 (stock/index): 返回 PE/PB/股息率
- 非权益类 (us_index/gold/bond/commodity/otc_fund): 返回 `skipped` 状态

**返回 (成功)**:
```json
{
  "status": "success",
  "data": {"symbol": "sh513130", "pe": 12.5, "pb": 1.2, "dividend_yield": 2.1}
}
```

**返回 (跳过)**:
```json
{
  "status": "skipped",
  "message": "美股指数无需估值分析"
}
```

---

### `macro_get_global_snapshot() -> dict`

**功能**: 获取全球宏观关键指标快照。

**包含指标**:
- VIX 恐慌指数 (附带水平评估)
- USD/CNH 离岸人民币汇率
- US10Y 美债 10 年期收益率

**返回**:
```json
{
  "status": "success",
  "data": {
    "vix": {"value": 18.5, "level": "normal"},
    "usd_cnh": 7.25,
    "us10y": 4.2,
    "summary": "宏观环境正常，无极端风险信号"
  }
}
```

**vix.level 可选值**: `low`, `normal`, `high`, `extreme`

---

## Ledger 技能

### `ledger_get_portfolio() -> dict`

**功能**: 获取当前持仓快照 (**绝对真理来源**)。

**返回**:
```json
{
  "status": "success",
  "data": {
    "cash": 50000.0,
    "holdings": [
      {"symbol": "sh513130", "name": "中概互联", "shares": 10000, "cost": 0.75}
    ]
  }
}
```

---

### `ledger_execute_trade(action, symbol, shares, price, name, reason) -> dict`

**功能**: 执行虚拟交易记账。

**参数**:
- `action` (必填): `"buy"` 或 `"sell"`
- `symbol` (必填): 标的代码
- `shares` (必填): 交易份额 (正数)
- `price` (必填): 成交价格
- `name` (可选): 标的名称 (buy 时建议提供)
- `reason` (可选): 交易理由 (记录到 CSV 供复盘)

**返回 (成功)**:
```json
{
  "status": "success",
  "message": "BUY sh513130 x 1000 @ 0.78 成功",
  "trade_record": {"action": "buy", "symbol": "sh513130", "shares": 1000, "price": 0.78, "amount": 780},
  "updated_cash": 49220.0
}
```

**返回 (失败)**:
```json
{"status": "error", "message": "现金不足：可用 500, 需要 780"}
```

---

### `ledger_get_trade_reasoning(symbol: str, limit: int = 5) -> dict`

**功能**: 获取指定标的的历史交易理由。

**参数**:
- `symbol` (必填): 标的代码
- `limit` (可选): 返回最近 N 条 (默认 5)

**返回**:
```json
{
  "status": "success",
  "data": [
    {"date": "2026-03-20", "action": "buy", "shares": 1000, "price": 0.78, "reason": "估值低位，技术面金叉"}
  ],
  "message": "找到 3 条记录，返回最近 1 条"
}
```

---

## 使用建议 (ReAct AI)

1. **决策前**: 先调用 `ledger_get_portfolio()` 获取持仓，再调用 `market_*` 和 `macro_*` 获取行情。
2. **交易后**: 调用 `ledger_execute_trade()` 更新账本，并务必传入 `reason` 字段。
3. **复盘时**: 调用 `ledger_get_trade_reasoning(symbol)` 回顾历史决策逻辑。
4. **错误处理**: 所有工具返回 `status: "error"` 时，应读取 `message` 字段并调整策略。

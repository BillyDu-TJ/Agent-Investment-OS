import os
import glob
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

TableData = Dict[str, List[Any]]

import pandas as pd
import streamlit as st
import yaml
from openai import OpenAI
from chat_engine import build_model_candidates, get_default_chat_config, run_chat_stream

try:
    import plotly.express as px
except Exception:
    px = None


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
CONFIG_DIR = ROOT_DIR / "config"

NAV_PATH = DATA_DIR / "nav_history.csv"
STRATEGY_PATH = CONFIG_DIR / "strategy_profile.yaml"


st.set_page_config(
    page_title="投研系统监控驾驶舱",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
        font-size: 14px;
    }
    .stMetric label {
        font-size: 0.85rem;
    }
    .stMetricValue {
        font-size: 1.35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_csv(path: Path) -> Optional[pd.DataFrame]:
    try:
        if not path.exists():
            st.warning("暂无数据")
            return None
        data = pd.read_csv(path)
        if data is None or data.empty:
            st.warning("暂无数据")
            return None
        return data
    except Exception:
        st.warning("暂无数据")
        return None


def load_yaml(path: Path) -> Optional[dict]:
    try:
        if not path.exists():
            st.warning("暂无数据")
            return None
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if not data:
            st.warning("暂无数据")
            return None
        return data
    except Exception:
        st.warning("暂无数据")
        return None


def read_markdown(path: Path) -> Optional[str]:
    try:
        if not path.exists():
            st.warning("暂无数据")
            return None
        return path.read_text(encoding="utf-8")
    except Exception:
        st.warning("暂无数据")
        return None


MAX_ATTACHMENT_CHARS = 4000
MAX_TOOL_LOG_CHARS = 240


def build_attachment_payload(
    uploads: Optional[List[Any]],
) -> Tuple[List[Dict[str, Any]], str]:
    attachments: List[Dict[str, Any]] = []
    prompt_blocks: List[str] = []
    for uploaded in uploads or []:
        raw = uploaded.getvalue()
        size_kb = len(raw) / 1024
        file_type = uploaded.type or ""
        name = uploaded.name
        if file_type.startswith("image/"):
            attachments.append(
                {
                    "name": name,
                    "type": file_type,
                    "size_kb": size_kb,
                    "kind": "image",
                    "data": raw,
                }
            )
            prompt_blocks.append(f"[图片:{name}, {file_type}, {size_kb:.1f}KB]")
            continue

        preview = raw.decode("utf-8", errors="ignore").strip()
        if preview:
            preview = preview[:MAX_ATTACHMENT_CHARS]
            attachments.append(
                {
                    "name": name,
                    "type": file_type,
                    "size_kb": size_kb,
                    "kind": "text",
                    "preview": preview,
                }
            )
            prompt_blocks.append(f"[文件:{name}]\n{preview}")
        else:
            attachments.append(
                {
                    "name": name,
                    "type": file_type,
                    "size_kb": size_kb,
                    "kind": "file",
                }
            )
            prompt_blocks.append(f"[文件:{name}, {file_type}, {size_kb:.1f}KB] (未解析)")

    if not prompt_blocks:
        return attachments, ""
    return attachments, "\n\n【附件内容】\n" + "\n\n".join(prompt_blocks)


def render_attachments(attachments: List[Dict[str, Any]]) -> None:
    for item in attachments:
        kind = item.get("kind")
        if kind == "image" and item.get("data"):
            st.image(item["data"], caption=item.get("name"))
        elif kind == "text":
            with st.expander(f"附件：{item.get('name')}", expanded=False):
                st.code(item.get("preview", ""))
        else:
            st.caption(f"附件：{item.get('name')} ({item.get('size_kb', 0):.1f}KB)")


def shorten_tool_payload(payload: Any) -> str:
    if isinstance(payload, str):
        text = payload
    else:
        try:
            text = json.dumps(payload, ensure_ascii=False)
        except Exception:
            text = str(payload)
    text = text.replace("\n", " ")
    if len(text) > MAX_TOOL_LOG_CHARS:
        text = text[:MAX_TOOL_LOG_CHARS] + "..."
    return text


def build_report_index() -> Dict[str, Dict[str, Path]]:
    index: Dict[str, Dict[str, Path]] = {}
    if not REPORTS_DIR.exists():
        return index
    for file_path in REPORTS_DIR.glob("*.md"):
        match = re.match(r"(\d{4}-\d{2}-\d{2})_(.+)\.md$", file_path.name)
        if not match:
            continue
        date_str, report_type = match.groups()
        index.setdefault(date_str, {})[report_type] = file_path
    return index


def extract_section_lines(text: str, header_prefix: str) -> List[str]:
    lines = text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            start_index = idx + 1
            break
    if start_index is None:
        return []
    output: List[str] = []
    for idx in range(start_index, len(lines)):
        line = lines[idx].rstrip()
        if line.startswith("## ") and idx > start_index:
            break
        if line.strip():
            output.append(line)
    return output


def extract_section_block(text: str, header_prefix: str) -> str:
    lines = text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        if line.strip().startswith(header_prefix):
            start_index = idx + 1
            break
    if start_index is None:
        return ""
    output: List[str] = []
    for idx in range(start_index, len(lines)):
        line = lines[idx].rstrip()
        if line.strip().startswith("#") and idx > start_index:
            break
        if line.strip():
            output.append(line)
    return "\n".join(output).strip()


def parse_number(value: str) -> Optional[float]:
    cleaned = re.sub(r"[^0-9\.-]", "", value)
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_overview_metrics(text: str) -> Dict[str, Optional[float]]:
    metrics = {
        "total_asset": None,
        "cash_ratio": None,
        "cash_amount": None,
        "total_pnl": None,
    }
    if not text:
        return metrics
    for line in text.splitlines():
        if "总资产市值" in line:
            match = re.search(r"¥([\d,\.]+)", line)
            if match:
                metrics["total_asset"] = parse_number(match.group(1))
        if "当前现金占比" in line:
            match = re.search(r"([\d\.]+)%\s*\(¥([\d,\.]+)\)", line)
            if match:
                metrics["cash_ratio"] = parse_number(match.group(1))
                metrics["cash_amount"] = parse_number(match.group(2))
        if "当前持仓总浮盈/亏" in line:
            metrics["total_pnl"] = parse_number(line)
    return metrics


def parse_markdown_tables(text: str) -> List[TableData]:
    lines = text.splitlines()
    tables: List[TableData] = []
    idx = 0
    while idx < len(lines) - 1:
        line = lines[idx].strip()
        next_line = lines[idx + 1].strip()
        if "|" in line and "|" in next_line and re.search(r"-{3,}", next_line):
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            idx += 2
            rows: List[List[str]] = []
            while idx < len(lines):
                row_line = lines[idx].strip()
                if not row_line or "|" not in row_line:
                    break
                cells = [cell.strip() for cell in row_line.strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(cells)
                idx += 1
            if rows:
                tables.append({"headers": headers, "rows": rows})
            continue
        idx += 1
    return tables


def find_table_with_keywords(
    tables: List[TableData],
    keywords: List[str],
) -> Optional[TableData]:
    for table in tables:
        header_text = "".join(table["headers"])
        if all(keyword in header_text for keyword in keywords):
            return table
    return None


def pick_holdings_table(tables: List[TableData]) -> Optional[TableData]:
    priority_table = find_table_with_keywords(tables, ["总盈亏", "今日盈亏"])
    if priority_table:
        return priority_table
    fallback_table = find_table_with_keywords(tables, ["标的", "盈亏"])
    if fallback_table:
        return fallback_table
    return None


def table_to_dataframe(table: TableData) -> pd.DataFrame:
    return pd.DataFrame(table["rows"], columns=table["headers"])


def style_by_sign(df: pd.DataFrame) -> Union[pd.DataFrame, object]:
    def colorize(value: str) -> str:
        text = str(value)
        cleaned = re.sub(r"[^0-9\.-]", "", text)
        try:
            number = float(cleaned)
        except ValueError:
            return ""
        if number > 0:
            return "color: #d32f2f;"
        if number < 0:
            return "color: #2e7d32;"
        return ""

    columns = [
        column
        for column in df.columns
        if any(keyword in column for keyword in ["盈亏", "涨跌", "收益"])
    ]
    if not columns:
        return df
    return df.style.applymap(colorize, subset=columns)


def compute_period_returns(df: Optional[pd.DataFrame]) -> Dict[str, Dict[str, Optional[float]]]:
    periods = {"近一周": 7, "近1个月": 30, "近半年": 180}
    result: Dict[str, Dict[str, Optional[float]]] = {}
    for label in periods:
        result[label] = {"value": None, "fallback": False, "base_date": None}
    if df is None or df.empty:
        return result
    if "Date" not in df.columns or "Total_NAV" not in df.columns:
        return result
    data = df.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["Total_NAV"] = pd.to_numeric(data["Total_NAV"], errors="coerce")
    data = data.dropna(subset=["Date", "Total_NAV"]).sort_values("Date")
    if data.empty:
        return result
    latest_date = data["Date"].iloc[-1]
    latest_nav = data["Total_NAV"].iloc[-1]
    for label, days in periods.items():
        target_date = latest_date - pd.Timedelta(days=days)
        past = data[data["Date"] <= target_date]
        if past.empty:
            past_row = data.iloc[0]
            result[label]["fallback"] = True
        else:
            past_row = past.iloc[-1]
        past_nav = past_row["Total_NAV"]
        if pd.isna(past_nav) or past_nav == 0:
            result[label]["value"] = None
            continue
        result[label]["value"] = (latest_nav / past_nav - 1) * 100
        base_date = past_row["Date"]
        if pd.notna(base_date):
            result[label]["base_date"] = base_date.strftime("%Y-%m-%d")
    return result


def find_latest_report(report_type: str) -> Optional[Path]:
    pattern = str(REPORTS_DIR / f"*_{report_type}.md")
    files = glob.glob(pattern)
    if not files:
        return None
    dated_files: List[Tuple[datetime, str]] = []
    for file_path in files:
        name = Path(file_path).name
        match = re.match(rf"(\d{{4}}-\d{{2}}-\d{{2}})_{re.escape(report_type)}\.md$", name)
        if match:
            try:
                date_value = datetime.strptime(match.group(1), "%Y-%m-%d")
                dated_files.append((date_value, file_path))
            except ValueError:
                continue
    if dated_files:
        return Path(max(dated_files, key=lambda item: item[0])[1])
    return Path(max(files, key=lambda item: os.path.getmtime(item)))


def get_latest_nav(df: Optional[pd.DataFrame]) -> Optional[Tuple[float, Optional[float]]]:
    if df is None or df.empty:
        return None
    if "Total_NAV" not in df.columns:
        return None
    data = df.copy()
    if "Date" in data.columns:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        data = data.sort_values("Date")
    data["Total_NAV"] = pd.to_numeric(data["Total_NAV"], errors="coerce")
    data = data.dropna(subset=["Total_NAV"])
    if data.empty:
        return None
    latest_row = data.iloc[-1]
    previous_row = data.iloc[-2] if len(data) > 1 else None
    change_pct = None
    if "Daily_Return_Pct" in data.columns:
        value = pd.to_numeric(latest_row.get("Daily_Return_Pct"), errors="coerce")
        if pd.notna(value):
            change_pct = float(value)
    if change_pct is None and previous_row is not None:
        prev_nav = previous_row["Total_NAV"]
        if pd.notna(prev_nav) and prev_nav != 0:
            change_pct = (latest_row["Total_NAV"] - prev_nav) / prev_nav * 100
    return float(latest_row["Total_NAV"]), change_pct


def load_api_config() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL")
    if base_url is None and os.getenv("DEEPSEEK_API_KEY"):
        base_url = "https://api.deepseek.com"
    if model is None:
        if base_url and "deepseek" in base_url:
            model = "deepseek-chat"
        else:
            model = "gpt-4o-mini"
    return api_key, base_url, model


def run_risk_review(philosophy_text: str, risk_config: dict) -> str:
    api_key, base_url, model = load_api_config()
    if not api_key:
        return "【提示】未检测到 API 密钥，请先设置环境变量 OPENAI_API_KEY 或 DEEPSEEK_API_KEY。"
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    user_payload = (
        f"投资哲学：\n{philosophy_text}\n\n"
        f"风控阈值：\n{risk_config}\n\n"
        "请以极其严苛的华尔街风控官口吻，指出逻辑漏洞、风险敞口或风格漂移，"
        "输出 Markdown 格式的审阅意见。"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是极其严苛的华尔街风控官，只给出清晰、尖锐、专业的批判。",
            },
            {"role": "user", "content": user_payload},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content


nav_data = load_csv(NAV_PATH)
latest_nav = get_latest_nav(nav_data) if nav_data is not None else None
report_index = build_report_index()
report_dates = sorted(report_index.keys(), reverse=True)


with st.sidebar:
    st.markdown("## 状态总览")
    st.markdown("**系统版本**：V3.0 第一阶段")
    st.markdown(f"**当前日期**：{datetime.now().strftime('%Y-%m-%d')}")
    nav_choice = st.radio(
        "功能导航",
        ["账户与表现", "投研报告与决策", "策略中枢", "智能体对话"],
    )
    st.divider()
    st.markdown("### 最新净值")
    if nav_data is not None:
        if latest_nav is None:
            st.warning("暂无数据")
        else:
            nav_value, change_pct = latest_nav
            delta_text = f"{change_pct:+.2f}%" if change_pct is not None else None
            st.metric("最新净值", f"{nav_value:,.2f}", delta=delta_text)

    st.markdown("### 区间收益")
    period_returns = compute_period_returns(nav_data)
    for label in ["近一周", "近1个月", "近半年"]:
        info = period_returns.get(label, {})
        value = info.get("value")
        if value is None:
            st.metric(label, "暂无数据")
        else:
            st.metric(label, f"{value:+.2f}%")
        if info.get("fallback") and info.get("base_date"):
            st.caption(f"数据不足，按{info.get('base_date')}起算")


st.title("投研系统监控驾驶舱")

if nav_choice == "账户与表现":
    st.subheader("每日快览")
    latest_date = report_dates[0] if report_dates else None
    daily_brief_path = (
        report_index.get(latest_date, {}).get("Daily_Brief") if latest_date else None
    )
    daily_brief_text = read_markdown(daily_brief_path) if daily_brief_path else None

    if latest_date:
        st.caption(f"日报日期：{latest_date}")

    overview_col, holdings_col = st.columns([1.3, 1])
    with overview_col:
        st.markdown("### 账户全局概览")
        if daily_brief_text:
            metrics = parse_overview_metrics(daily_brief_text)
        else:
            metrics = {
                "total_asset": None,
                "cash_ratio": None,
                "cash_amount": None,
                "total_pnl": None,
            }

        asset_col, cash_col, pnl_col = st.columns(3)
        asset_value = (
            f"¥{metrics['total_asset']:,.2f}"
            if metrics.get("total_asset") is not None
            else "暂无数据"
        )
        asset_delta = None
        if latest_nav is not None:
            _, change_pct = latest_nav
            if change_pct is not None:
                asset_delta = f"{change_pct:+.2f}%"
        asset_col.metric("总资产", asset_value, delta=asset_delta)

        cash_value = (
            f"{metrics['cash_ratio']:.2f}%"
            if metrics.get("cash_ratio") is not None
            else "暂无数据"
        )
        cash_delta = (
            f"¥{metrics['cash_amount']:,.2f}"
            if metrics.get("cash_amount") is not None
            else None
        )
        cash_col.metric("现金占比", cash_value, delta=cash_delta)

        pnl_value = (
            f"¥{metrics['total_pnl']:,.2f}"
            if metrics.get("total_pnl") is not None
            else "暂无数据"
        )
        pnl_delta = (
            f"{metrics['total_pnl']:+.2f}"
            if metrics.get("total_pnl") is not None
            else None
        )
        pnl_col.metric("总浮盈/亏", pnl_value, delta=pnl_delta)

    with holdings_col:
        st.markdown("### 持仓盈亏明细")
        if daily_brief_text:
            holdings_block = extract_section_block(daily_brief_text, "### 💼 持仓摘要")
            tables = parse_markdown_tables(holdings_block) if holdings_block else []
            holdings_table = pick_holdings_table(tables)
            if holdings_table:
                holdings_df = table_to_dataframe(holdings_table)
                styled_table = style_by_sign(holdings_df)
                st.dataframe(styled_table, use_container_width=True, hide_index=True)
                missing_total = "总盈亏" not in holdings_df.columns
                missing_today = "今日盈亏" not in holdings_df.columns
                if missing_total or missing_today:
                    st.caption("日报未包含“总盈亏/今日盈亏”字段，将展示可用信息。")
            else:
                st.warning("暂无数据")
        else:
            st.warning("暂无数据")

    st.markdown("### 宏观与持仓快照")
    macro_col, micro_col = st.columns(2)
    with macro_col:
        with st.expander("全球宏观与宽基阵列", expanded=False):
            if daily_brief_text:
                macro_block = extract_section_block(daily_brief_text, "### 🌍 全球宏观与宽基阵列")
                macro_tables = parse_markdown_tables(macro_block) if macro_block else []
                if macro_tables:
                    macro_df = table_to_dataframe(macro_tables[0])
                    st.dataframe(style_by_sign(macro_df), use_container_width=True, hide_index=True)
                else:
                    st.warning("暂无数据")
            else:
                st.warning("暂无数据")
    with micro_col:
        with st.expander("微观持仓与行业资产", expanded=False):
            if daily_brief_text:
                micro_block = extract_section_block(daily_brief_text, "### 💼 微观持仓与行业资产")
                micro_tables = parse_markdown_tables(micro_block) if micro_block else []
                if micro_tables:
                    micro_df = table_to_dataframe(micro_tables[0])
                    st.dataframe(style_by_sign(micro_df), use_container_width=True, hide_index=True)
                else:
                    st.warning("暂无数据")
            else:
                st.warning("暂无数据")

    st.divider()
    st.subheader("净值增长曲线")
    if nav_data is None:
        st.warning("暂无数据")
    elif "Date" not in nav_data.columns or "Total_NAV" not in nav_data.columns:
        st.warning("暂无数据")
    else:
        plot_data = nav_data.copy()
        plot_data["Date"] = pd.to_datetime(plot_data["Date"], errors="coerce")
        plot_data["Total_NAV"] = pd.to_numeric(plot_data["Total_NAV"], errors="coerce")
        plot_data = plot_data.dropna(subset=["Date", "Total_NAV"])
        if plot_data.empty:
            st.warning("暂无数据")
        else:
            plot_data = plot_data.sort_values("Date")
            if px is None:
                st.warning("未检测到 Plotly，已回退到基础图表。")
                st.line_chart(plot_data.set_index("Date")["Total_NAV"])
            else:
                fig = px.line(
                    plot_data,
                    x="Date",
                    y="Total_NAV",
                    markers=True,
                    labels={"Date": "日期", "Total_NAV": "总净值"},
                )
                fig.update_layout(
                    template="plotly_dark",
                    hovermode="x unified",
                    font={
                        "family": "Microsoft YaHei, PingFang SC, Noto Sans CJK SC",
                        "size": 12,
                    },
                )
                fig.update_traces(line={"width": 2})
                st.plotly_chart(fig, use_container_width=True)

    st.subheader("每日收益（%）")
    if nav_data is None:
        st.warning("暂无数据")
    elif "Date" not in nav_data.columns or "Daily_Return_Pct" not in nav_data.columns:
        st.warning("暂无数据")
    else:
        return_data = nav_data.copy()
        return_data["Date"] = pd.to_datetime(return_data["Date"], errors="coerce")
        return_data["Daily_Return_Pct"] = pd.to_numeric(
            return_data["Daily_Return_Pct"], errors="coerce"
        )
        return_data = return_data.dropna(subset=["Date", "Daily_Return_Pct"])
        if return_data.empty:
            st.warning("暂无数据")
        else:
            return_data = return_data.sort_values("Date")
            if px is None:
                st.warning("未检测到 Plotly，已回退到基础图表。")
                st.bar_chart(return_data.set_index("Date")["Daily_Return_Pct"])
            else:
                return_data["方向"] = return_data["Daily_Return_Pct"].apply(
                    lambda value: "上涨" if value >= 0 else "下跌"
                )
                fig = px.bar(
                    return_data,
                    x="Date",
                    y="Daily_Return_Pct",
                    color="方向",
                    labels={"Date": "日期", "Daily_Return_Pct": "每日收益(%)"},
                    color_discrete_map={"上涨": "#d32f2f", "下跌": "#2e7d32"},
                )
                fig.update_layout(
                    template="plotly_dark",
                    hovermode="x unified",
                    font={
                        "family": "Microsoft YaHei, PingFang SC, Noto Sans CJK SC",
                        "size": 12,
                    },
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            st.caption("红涨绿跌")


elif nav_choice == "投研报告与决策":
    st.subheader("投研报告与决策")
    if not report_dates:
        st.warning("暂无数据")
    else:
        selected_date = st.selectbox("选择日期", report_dates, index=0)
        st.caption(f"当前日期：{selected_date}")
        report_tabs = st.tabs(["AI 顾问", "每日简报", "新闻快报"])
        report_types = ["AI_Advisor", "Daily_Brief", "News_Flash"]

        for report_tab, report_type in zip(report_tabs, report_types):
            with report_tab:
                report_path = report_index.get(selected_date, {}).get(report_type)
                if report_path is None:
                    st.warning("暂无数据")
                    continue
                st.caption(f"文件：{report_path.name}")
                content = read_markdown(report_path)
                if content:
                    st.markdown(content)

elif nav_choice == "策略中枢":
    st.subheader("策略读取")
    strategy_data = load_yaml(STRATEGY_PATH)
    if strategy_data is not None:
        philosophy_text = strategy_data.get("investment_philosophy", "")
        portfolio_structure = strategy_data.get("portfolio_structure", {})
        risk_governance = strategy_data.get("risk_governance", {})

        st.markdown("### 投资哲学")
        st.markdown(philosophy_text if philosophy_text else "暂无数据")

        st.markdown("### 仓位结构")
        if portfolio_structure:
            st.json(portfolio_structure)
        else:
            st.warning("暂无数据")

        st.markdown("### 风控阈值")
        if risk_governance:
            st.json(risk_governance)
        else:
            st.warning("暂无数据")

        st.divider()
        st.subheader("策略微调模拟")
        edited_philosophy = st.text_area(
            "投资哲学（仅临时编辑，不写回本地）",
            value=philosophy_text,
            height=200,
        )

        if "risk_review" not in st.session_state:
            st.session_state["risk_review"] = ""

        if st.button("让 AI 首席风控官评估当前策略"):
            if not edited_philosophy.strip() or not risk_governance:
                st.warning("暂无数据")
            else:
                with st.spinner("首席风控官正在审阅您的投资哲学..."):
                    try:
                        review_text = run_risk_review(edited_philosophy, risk_governance)
                        st.session_state["risk_review"] = review_text
                    except Exception:
                        st.error("请求失败，请稍后重试。")

        if st.session_state.get("risk_review"):
            st.markdown("### 风控官审阅意见")
            st.markdown(st.session_state["risk_review"])

else:
    st.subheader("智能体对话")
    st.caption("支持工具调用与本地账本读写，适合做真实策略咨询与执行。")

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&family=ZCOOL+XiaoWei&display=swap');
        .chat-hero {
            background: radial-gradient(circle at 15% 20%, #f1f6ff 0%, #f7f3ff 45%, #fffaf0 100%);
            border-radius: 16px;
            padding: 1.2rem 1.4rem;
            border: 1px solid rgba(0,0,0,0.06);
            margin-bottom: 1rem;
        }
        .chat-hero h2 {
            font-family: "ZCOOL XiaoWei", "Space Grotesk", "Microsoft YaHei", sans-serif;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin: 0;
        }
        .chat-hero p {
            font-family: "Space Grotesk", "Microsoft YaHei", sans-serif;
            margin: 0.35rem 0 0 0;
            color: #4f4f4f;
        }
        div[data-testid="stChatMessage"] {
            animation: fadeUp 0.35s ease-out both;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="chat-hero">
            <h2>Agentic Intelligence Console</h2>
            <p>LangGraph · Tool Calling · 本地交易与风控协作</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "chat_settings" not in st.session_state:
        defaults = get_default_chat_config()
        st.session_state["chat_settings"] = {
            "model_name": defaults["model_name"],
            "base_url": defaults["base_url"],
            "api_key": defaults["api_key"],
            "custom_model": "",
        }

    settings = st.session_state["chat_settings"]
    action_col, clear_col = st.columns([4, 1])
    with action_col:
        st.markdown("### 对话控制台")
    with clear_col:
        if st.button("清空对话"):
            st.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": "已就位，欢迎留言。",
                    "model_content": "已就位，欢迎留言。",
                }
            ]

    with st.expander("模型与连接设置", expanded=False):
        base_url = st.text_input(
            "API Base URL",
            value=settings.get("base_url", ""),
            placeholder="https://api.deepseek.com",
        )
        model_candidates = build_model_candidates(base_url, settings.get("model_name", ""))
        selected_model = st.selectbox(
            "模型",
            options=model_candidates,
            index=model_candidates.index(settings.get("model_name"))
            if settings.get("model_name") in model_candidates
            else 0,
        )
        custom_model = st.text_input(
            "自定义模型（可选）",
            value=settings.get("custom_model", ""),
            placeholder="例如：deepseek-chat / gpt-4o-mini",
        )
        api_key = st.text_input(
            "API Key",
            type="password",
            value=settings.get("api_key", ""),
            placeholder="未配置时将读取环境变量",
        )
        st.caption("后端 API 解析逻辑可在 web/chat_engine.py 的 resolve_api_config 中调整。")

        settings.update(
            {
                "model_name": selected_model,
                "base_url": base_url,
                "api_key": api_key,
                "custom_model": custom_model,
            }
        )

    uploads = st.file_uploader(
        "上传文件或图片（可多选）",
        type=["txt", "md", "csv", "json", "yaml", "yml", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="chat_uploads",
        help="文本文件将注入对话上下文，图片会显示预览但不会自动解析。",
    )

    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {
                "role": "assistant",
                "content": "已就位，欢迎留言。",
                "model_content": "已就位，欢迎留言。",
            }
        ]

    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            attachments = message.get("attachments", [])
            if attachments:
                render_attachments(attachments)

    user_input = st.chat_input("请输入指令 (如: 查一下恒生科技的技术指标并给个建议)")
    if user_input:
        attachments, attachment_prompt = build_attachment_payload(uploads)
        model_input = f"{user_input}{attachment_prompt}"

        user_message = {
            "role": "user",
            "content": user_input,
            "model_content": model_input,
            "attachments": attachments,
        }
        st.session_state["messages"].append(user_message)

        with st.chat_message("user"):
            st.markdown(user_input)
            if attachments:
                render_attachments(attachments)

        history_payload = [
            {
                "role": message.get("role"),
                "content": message.get("model_content", message.get("content", "")),
            }
            for message in st.session_state["messages"][:-1]
            if message.get("role") in {"user", "assistant", "system"}
        ]

        model_to_use = settings.get("custom_model", "").strip() or settings.get(
            "model_name", ""
        )

        with st.chat_message("assistant"):
            assistant_placeholder = st.empty()
            assistant_text = ""
            tool_status = None
            try:
                for event in run_chat_stream(
                    user_input=model_input,
                    chat_history=history_payload,
                    model_name=model_to_use,
                    base_url=settings.get("base_url"),
                    api_key=settings.get("api_key"),
                ):
                    if event.get("type") == "assistant":
                        assistant_text += event.get("content", "")
                        assistant_placeholder.markdown(assistant_text)
                    elif event.get("type") == "tool_call":
                        if tool_status is None:
                            tool_status = st.status("正在调用工具...", expanded=False)
                        for call in event.get("calls", []):
                            tool_name = call.get("name", "tool")
                            tool_args = shorten_tool_payload(call.get("args", {}))
                            tool_status.write(f"调用 {tool_name}")
                            tool_status.caption(f"参数：{tool_args}")
                    elif event.get("type") == "tool_result":
                        if tool_status is None:
                            tool_status = st.status("正在调用工具...", expanded=False)
                        tool_name = event.get("name", "tool")
                        result_preview = shorten_tool_payload(event.get("content", ""))
                        tool_status.write(f"结果 {tool_name}")
                        tool_status.caption(result_preview)
            except Exception:
                st.error("请求失败，请稍后重试。")

            if tool_status is not None:
                tool_status.update(label="工具调用完成", state="complete")

            if not assistant_text:
                assistant_text = "未收到模型回复，请稍后重试。"
                assistant_placeholder.markdown(assistant_text)

        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": assistant_text,
                "model_content": assistant_text,
            }
        )
        st.session_state["chat_uploads"] = []

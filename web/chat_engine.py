from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import sys

import yaml
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field, create_model

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from src.tools.skill_registry import SKILL_FUNCTIONS, SKILL_MANIFEST
STRATEGY_PATH = ROOT_DIR / "config" / "strategy_profile.yaml"


TYPE_MAP = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def load_investment_philosophy() -> str:
    if not STRATEGY_PATH.exists():
        return ""
    with STRATEGY_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return str(data.get("investment_philosophy", "")).strip()


def build_system_prompt() -> str:
    philosophy = load_investment_philosophy()
    tool_lines = []
    for name, meta in SKILL_MANIFEST.items():
        desc = meta.get("description", "")
        tool_lines.append(f"- {name}: {desc}")
    tool_list = "\n".join(tool_lines)
    return (
        "你是一个首席投研助理，必须严格遵循以下投资哲学：\n"
        f"{philosophy}\n\n"
        "你可以使用提供的工具查询实时行情、技术指标、账本状态和历史交易。"
        "工具会返回真实数据，禁止臆测或编造。\n\n"
        "可用工具列表：\n"
        f"{tool_list}\n\n"
        "当执行交易相关工具时，必须明确写出交易理由与风险提示。"
    )


def resolve_api_config(
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], str]:
    env_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    env_base = os.getenv("OPENAI_BASE_URL")
    env_model = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL")

    resolved_key = api_key or env_key
    resolved_base = base_url or env_base
    if resolved_base is None and os.getenv("DEEPSEEK_API_KEY"):
        resolved_base = "https://api.deepseek.com"

    resolved_model = model_name or env_model
    if resolved_model is None:
        if resolved_base and "deepseek" in resolved_base:
            resolved_model = "deepseek-chat"
        else:
            resolved_model = "gpt-4o-mini"

    return resolved_key, resolved_base, resolved_model


def get_default_chat_config() -> Dict[str, Any]:
    api_key, base_url, model_name = resolve_api_config()
    return {
        "api_key": api_key or "",
        "base_url": base_url or "",
        "model_name": model_name,
    }


def build_model_candidates(base_url: Optional[str], default_model: str) -> List[str]:
    options: List[str] = []
    if base_url and "deepseek" in base_url:
        options.extend(["deepseek-chat", "deepseek-reasoner"])
    else:
        options.extend(["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o"])
    if default_model and default_model not in options:
        options.insert(0, default_model)
    return options


def _map_param_type(param_meta: Dict[str, Any]) -> type:
    return TYPE_MAP.get(str(param_meta.get("type", "string")).lower(), str)


def _build_args_schema(skill_name: str, params: Dict[str, Any]) -> type[BaseModel]:
    fields: Dict[str, tuple] = {}
    for param_name, param_meta in params.items():
        field_type = _map_param_type(param_meta)
        description = str(param_meta.get("description", ""))
        fields[param_name] = (field_type, Field(..., description=description))
    if not fields:
        return create_model(f"{skill_name}_Args")
    return create_model(f"{skill_name}_Args", **fields)


def _wrap_skill_function(skill_name: str):
    fn = SKILL_FUNCTIONS[skill_name]

    def _tool_func(**kwargs: Any) -> Dict[str, Any]:
        payload = dict(kwargs)
        return fn(payload)

    _tool_func.__name__ = skill_name
    _tool_func.__doc__ = SKILL_MANIFEST.get(skill_name, {}).get("description", "")
    return _tool_func


@lru_cache(maxsize=1)
def build_tools() -> Tuple[StructuredTool, ...]:
    tools: List[StructuredTool] = []
    for skill_name in SKILL_FUNCTIONS:
        manifest = SKILL_MANIFEST.get(skill_name, {})
        description = str(manifest.get("description", skill_name))
        params = manifest.get("parameters", {})
        args_schema = _build_args_schema(skill_name, params)
        tool = StructuredTool.from_function(
            func=_wrap_skill_function(skill_name),
            name=skill_name,
            description=description,
            args_schema=args_schema,
        )
        tools.append(tool)
    return tuple(tools)


@lru_cache(maxsize=8)
def build_agent(model_name: str, base_url: Optional[str], api_key: str):
    model = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=0.2,
        streaming=True,
    )
    return create_react_agent(model, tools=list(build_tools()))


def _format_tool_payload(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        return str(payload)


def _normalize_history(chat_history: List[Dict[str, str]]) -> List[Any]:
    normalized = []
    for message in chat_history:
        role = message.get("role")
        content = message.get("content", "")
        if not content:
            continue
        if role == "user":
            normalized.append(HumanMessage(content=content))
        elif role == "assistant":
            normalized.append(AIMessage(content=content))
        elif role == "system":
            normalized.append(SystemMessage(content=content))
    return normalized


def run_chat_stream(
    user_input: str,
    chat_history: List[Dict[str, str]],
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    recursion_limit: int = 12,
) -> Iterable[Dict[str, Any]]:
    resolved_key, resolved_base, resolved_model = resolve_api_config(
        model_name=model_name,
        base_url=base_url,
        api_key=api_key,
    )
    if not resolved_key:
        yield {
            "type": "assistant",
            "content": "未检测到 API 密钥，请先设置环境变量或在前端输入 API Key。",
        }
        return

    agent = build_agent(resolved_model, resolved_base, resolved_key)
    messages = [SystemMessage(content=build_system_prompt())]
    messages.extend(_normalize_history(chat_history))
    messages.append(HumanMessage(content=user_input))

    assistant_so_far = ""
    last_len = 0
    safe_limit = max(1, min(int(recursion_limit or 12), 50))
    for step in agent.stream(
        {"messages": messages},
        config={"recursion_limit": safe_limit},
        stream_mode="values",
    ):
        step_messages = step.get("messages", [])
        if len(step_messages) <= last_len:
            continue
        new_messages = step_messages[last_len:]
        last_len = len(step_messages)
        for message in new_messages:
            if isinstance(message, AIMessage):
                if message.tool_calls:
                    yield {"type": "tool_call", "calls": message.tool_calls}
                if message.content:
                    assistant_so_far = message.content
                    yield {"type": "assistant", "content": assistant_so_far}
            elif isinstance(message, ToolMessage):
                yield {
                    "type": "tool_result",
                    "name": message.name,
                    "content": _format_tool_payload(message.content),
                }

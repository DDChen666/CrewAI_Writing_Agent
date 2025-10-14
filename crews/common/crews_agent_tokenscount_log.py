"""Global agent token usage logging utilities."""
from __future__ import annotations

import json
import threading
import types
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

import litellm  # type: ignore
from crewai import Agent  # type: ignore
from crewai.llm import LLM  # type: ignore


_CURRENT_CALL_CONTEXT: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "crews_agent_call_context",
    default=None,
)
_LOG_WRITE_LOCK = threading.Lock()
_PATCH_LOCK = threading.Lock()
_LITELLM_COMPLETION_ORIGINAL = None
_LLM_CALL_ORIGINAL = None
_AGENT_EXECUTE_ORIGINAL = None
_PATCHED = False

_TOKEN_LOG_DIR = Path(__file__).resolve().parents[2] / "token_logs"
_ACTIVE_AGENT_CONTEXT: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "crews_active_agent_context",
    default=None,
)


def ensure_agent_token_logger() -> None:
    """Ensure the agent token logger is patched exactly once."""

    global _PATCHED
    if _PATCHED:
        return

    with _PATCH_LOCK:
        if _PATCHED:
            return
        _patch_llm_call()
        _patch_litellm_completion()
        _patch_agent_execute_task()
        _PATCHED = True


def _patch_llm_call() -> None:
    global _LLM_CALL_ORIGINAL
    if _LLM_CALL_ORIGINAL is not None:
        return

    _LLM_CALL_ORIGINAL = LLM.call

    def call_wrapper(  # type: ignore[override]
        self: LLM,
        messages: str | list[dict[str, str]],
        tools: list[dict] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any | None = None,
        from_agent: Any | None = None,
    ) -> str | Any:
        active_agent_context = _ACTIVE_AGENT_CONTEXT.get() or {}
        agent_obj = from_agent or active_agent_context.get("agent")
        context: Dict[str, Any] = {
            "model": getattr(self, "model", None),
            "timestamp": datetime.now(timezone.utc),
            "thread_id": threading.get_ident(),
            "agent": _describe_agent(agent_obj),
            "agent_tools": _extract_tool_names(
                getattr(from_agent, "tools", None)
                or active_agent_context.get("tools")
            ),
            "call_tools": _extract_tool_schema_names(tools),
        }
        token = _CURRENT_CALL_CONTEXT.set(context)
        try:
            return _LLM_CALL_ORIGINAL(
                self,
                messages,
                tools=tools,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
            )
        finally:
            _CURRENT_CALL_CONTEXT.reset(token)

    LLM.call = call_wrapper  # type: ignore[assignment]


def _patch_litellm_completion() -> None:
    global _LITELLM_COMPLETION_ORIGINAL
    if _LITELLM_COMPLETION_ORIGINAL is not None:
        return

    _LITELLM_COMPLETION_ORIGINAL = litellm.completion

    def completion_wrapper(*args, **kwargs):
        context = _CURRENT_CALL_CONTEXT.get()
        response = _LITELLM_COMPLETION_ORIGINAL(*args, **kwargs)

        if not context:
            return response

        if _is_streaming_response(response):
            return _wrap_streaming_response(response, context, kwargs)

        _log_completion_response(response, context, kwargs)
        return response

    litellm.completion = completion_wrapper  # type: ignore[assignment]


def _patch_agent_execute_task() -> None:
    global _AGENT_EXECUTE_ORIGINAL
    if _AGENT_EXECUTE_ORIGINAL is not None:
        return

    _AGENT_EXECUTE_ORIGINAL = Agent.execute_task

    def execute_task_wrapper(  # type: ignore[override]
        self: Agent,
        task,
        context: str | None = None,
        tools: list[Any] | None = None,
    ) -> str:
        agent_context = {
            "agent": self,
            "tools": tools or self.tools or [],
        }
        token = _ACTIVE_AGENT_CONTEXT.set(agent_context)
        try:
            return _AGENT_EXECUTE_ORIGINAL(
                self,
                task,
                context=context,
                tools=tools,
            )
        finally:
            _ACTIVE_AGENT_CONTEXT.reset(token)

    Agent.execute_task = execute_task_wrapper  # type: ignore[assignment]


def _wrap_streaming_response(
    response: Iterator[Any],
    context: Dict[str, Any],
    call_kwargs: Dict[str, Any],
) -> Iterator[Any]:
    def _generator() -> Iterator[Any]:
        last_chunk: Any = None
        usage_snapshot: Optional[Dict[str, Optional[int]]] = None
        tool_calls: set[str] = set()

        try:
            for chunk in response:
                last_chunk = chunk
                chunk_usage = _extract_usage_dict(chunk)
                if chunk_usage:
                    usage_snapshot = chunk_usage
                tool_calls.update(_extract_tool_calls(chunk))
                yield chunk
        finally:
            data = usage_snapshot or _extract_usage_dict(last_chunk) or {}
            _log_record(
                context=context,
                call_kwargs=call_kwargs,
                usage=data,
                tool_calls=list(tool_calls),
            )

    return _generator()


def _log_completion_response(
    response: Any,
    context: Dict[str, Any],
    call_kwargs: Dict[str, Any],
) -> None:
    usage = _extract_usage_dict(response) or {}
    tool_calls = _extract_tool_calls(response)
    _log_record(
        context=context,
        call_kwargs=call_kwargs,
        usage=usage,
        tool_calls=tool_calls,
    )


def _log_record(
    *,
    context: Dict[str, Any],
    call_kwargs: Dict[str, Any],
    usage: Dict[str, Optional[int]],
    tool_calls: Iterable[str],
) -> None:
    if not context:
        return

    timestamp = context.get("timestamp")
    if isinstance(timestamp, datetime):
        timestamp_iso = timestamp.isoformat().replace("+00:00", "Z")
    else:
        timestamp_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "timestamp": timestamp_iso,
        "model": context.get("model") or call_kwargs.get("model"),
        "agent": context.get("agent"),
        "tools": list(tool_calls) if tool_calls else context.get("agent_tools", []),
        "available_tools": context.get("call_tools", []),
        "prompt_tokens": _safe_int(usage.get("prompt_tokens")),
        "cached_prompt_tokens": _safe_int(usage.get("cached_prompt_tokens")),
        "completion_tokens": _safe_int(usage.get("completion_tokens")),
        "total_tokens": _derive_total_tokens(usage),
        "thread_id": context.get("thread_id"),
    }

    _write_log(record)


def _extract_tool_schema_names(tools: Optional[Iterable[dict]]) -> list[str]:
    names: list[str] = []
    if not tools:
        return names
    for tool in tools:
        if isinstance(tool, dict):
            name = tool.get("function", {}).get("name") or tool.get("name")
            if name:
                names.append(str(name))
    return names


def _extract_tool_names(tools: Optional[Iterable[Any]]) -> list[str]:
    names: list[str] = []
    if not tools:
        return names
    for tool in tools:
        name = getattr(tool, "name", None)
        if not name and isinstance(tool, dict):
            name = tool.get("name")
        if not name:
            name = tool.__class__.__name__
        names.append(str(name))
    return names


def _describe_agent(agent: Any) -> Optional[str]:
    if agent is None:
        return None
    for attr in ("role", "name", "title"):
        value = getattr(agent, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    return agent.__class__.__name__


def _is_streaming_response(response: Any) -> bool:
    return hasattr(response, "__next__") or isinstance(response, types.GeneratorType)


def _extract_usage_dict(obj: Any) -> Dict[str, Optional[int]]:
    usage = None
    if isinstance(obj, dict):
        usage = obj.get("usage")
    elif hasattr(obj, "usage"):
        usage = getattr(obj, "usage")

    if usage is None:
        return {}

    if isinstance(usage, dict):
        data = usage
    else:
        data = {attr: getattr(usage, attr, None) for attr in dir(usage) if not attr.startswith("_")}

    return {
        "prompt_tokens": data.get("prompt_tokens"),
        "cached_prompt_tokens": data.get("cached_prompt_tokens") or data.get("cached_tokens"),
        "completion_tokens": data.get("completion_tokens") or data.get("response_tokens"),
        "total_tokens": data.get("total_tokens"),
    }


def _extract_tool_calls(response: Any) -> list[str]:
    choices = None
    if isinstance(response, dict):
        choices = response.get("choices")
    elif hasattr(response, "choices"):
        choices = getattr(response, "choices")

    if not choices:
        return []

    first_choice = None
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
    elif hasattr(choices, "__iter__"):
        iterator = iter(choices)
        try:
            first_choice = next(iterator)
        except StopIteration:
            first_choice = None

    if first_choice is None:
        return []

    message = None
    if isinstance(first_choice, dict):
        message = first_choice.get("message")
    elif hasattr(first_choice, "message"):
        message = getattr(first_choice, "message")

    if message is None:
        return []

    tool_calls = None
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls")
    elif hasattr(message, "tool_calls"):
        tool_calls = getattr(message, "tool_calls")

    if not tool_calls:
        return []

    tool_names: list[str] = []
    for call in tool_calls:
        name = None
        if isinstance(call, dict):
            name = call.get("function", {}).get("name") or call.get("name")
        else:
            function = getattr(call, "function", None)
            if function is not None and hasattr(function, "name"):
                name = getattr(function, "name")
            elif hasattr(call, "name"):
                name = getattr(call, "name")
        if name:
            tool_names.append(str(name))

    return tool_names


def _derive_total_tokens(usage: Dict[str, Optional[int]]) -> Optional[int]:
    total = usage.get("total_tokens")
    if total is not None:
        return _safe_int(total)
    prompt = _safe_int(usage.get("prompt_tokens"))
    completion = _safe_int(usage.get("completion_tokens"))
    if prompt is not None and completion is not None:
        return prompt + completion
    return None


def _safe_int(value: Any) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_log(record: Dict[str, Any]) -> None:
    _TOKEN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"agent_token_usage_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    log_path = _TOKEN_LOG_DIR / filename

    with _LOG_WRITE_LOCK:
        with log_path.open("a", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
            fh.write("\n")

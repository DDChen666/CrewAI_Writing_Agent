"""Shared helpers for command-line entry points."""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - platform guard
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python <3.9
    ZoneInfo = None  # type: ignore[assignment]

PROMPT_KEY = "prompt"


@dataclass
class PromptTemplate:
    """Container returned when resolving prompt templates."""

    prompt: str
    scalars: Dict[str, Optional[str]]


def _extract_top_level_scalars(lines: List[str]) -> Dict[str, Optional[str]]:
    scalars: Dict[str, Optional[str]] = {}
    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")):
            continue
        if ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        scalars[key] = value or None
    return scalars


def _split_sections(content: str) -> List[List[str]]:
    sections: List[List[str]] = []
    current: List[str] = []
    for line in content.splitlines():
        if line.strip() == "---":
            if current:
                sections.append(current)
                current = []
            continue
        current.append(line)
    if current:
        sections.append(current)
    if not sections:
        sections.append([])
    return sections


def _extract_prompt(lines: List[str]) -> str:
    prompt_lines: List[str] = []
    capture = False
    indent: Optional[int] = None

    for line in lines:
        stripped = line.strip()
        if not capture:
            if stripped.startswith(f"{PROMPT_KEY}:"):
                suffix = stripped[len(PROMPT_KEY) + 1 :].strip()
                if suffix and not suffix.startswith(("|", ">")):
                    return suffix
                capture = True
                indent = None
            continue

        if indent is None:
            if not line:
                prompt_lines.append("")
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent == 0:
                break

        if indent is not None and line.startswith(" " * indent):
            prompt_lines.append(line[indent:])
        elif not line.strip() and indent is not None:
            prompt_lines.append("")
        else:
            break

    if not prompt_lines:
        raise RuntimeError("Prompt not found in template section")

    return "\n".join(prompt_lines).rstrip("\n")


def load_prompt_template(
    path: Path,
    *,
    expected_agent: Optional[str] = None,
    expected_task: Optional[str] = None,
) -> PromptTemplate:
    """Load a prompt template from disk and select the matching section."""

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem guard
        raise RuntimeError(f"Unable to read prompt file: {path}") from exc

    sections = _split_sections(content)
    fallback_prompt: Optional[PromptTemplate] = None
    for section in sections:
        scalars = _extract_top_level_scalars(section)
        agent_identifier = scalars.get("agent")
        task_identifier = scalars.get("task")

        agent_matches = expected_agent is None or agent_identifier == expected_agent
        task_matches = expected_task is None or (task_identifier or "") == str(expected_task)

        if not agent_matches or not task_matches:
            if fallback_prompt is None and scalars:
                try:
                    prompt = _extract_prompt(section)
                except RuntimeError:
                    continue
                fallback_prompt = PromptTemplate(prompt=prompt, scalars=scalars)
            continue

        prompt = _extract_prompt(section)
        return PromptTemplate(prompt=prompt, scalars=scalars)

    if expected_agent is not None or expected_task is not None:
        raise RuntimeError(
            f"Prompt file {path} does not contain a section for agent '{expected_agent}' with task '{expected_task}'"
        )

    if fallback_prompt is not None:
        return fallback_prompt

    raise RuntimeError(f"Prompt not found in {path}")


def resolve_prompt(
    prompt_argument: str,
    default_prompts: Dict[str, Dict[str, Any]],
) -> PromptTemplate:
    """Resolve either a literal prompt or a configured template."""

    prompt_entry = default_prompts.get(prompt_argument)
    if prompt_entry is None:
        return PromptTemplate(prompt=prompt_argument, scalars={})

    prompt_path = Path(prompt_entry["path"])
    if not prompt_path.exists():
        raise FileNotFoundError(f"Default prompt file not found: {prompt_path}")

    template = load_prompt_template(
        prompt_path,
        expected_agent=prompt_entry.get("agent"),
        expected_task=prompt_entry.get("task"),
    )

    extras = {k: v for k, v in prompt_entry.items() if k not in {"path", "agent", "task"}}
    if extras:
        merged_scalars = dict(template.scalars)
        merged_scalars.update({key: str(value) for key, value in extras.items()})
        return PromptTemplate(prompt=template.prompt, scalars=merged_scalars)
    return template


def load_config(path: Path) -> Dict[str, Any]:
    """Load an optional JSON configuration file."""

    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:  # pragma: no cover - configuration guard
        raise RuntimeError(f"Invalid JSON configuration in {path}") from exc


def ensure_output_path(root: Path, stem: str) -> Path:
    """Create a timestamped output file path."""

    os.makedirs(root, exist_ok=True)
    tz = ZoneInfo("Asia/Taipei") if ZoneInfo is not None else dt.timezone(dt.timedelta(hours=8))
    now = dt.datetime.now(tz)
    directory = root / now.strftime("%Y%m%d")
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{now.strftime('%Y%m%d%H%M')}_{stem}.json"
    return directory / filename


def write_output(path: Path, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def coerce_json_payload(result: Any) -> Optional[Any]:
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, (dict, list)):
        return result
    return None


def persist_result_if_json(result: Any, output_root: Path, stem: str) -> Optional[Path]:
    payload = coerce_json_payload(result)
    if payload is None:
        return None
    if isinstance(payload, dict) and payload.get("status") == "error":
        return None
    try:
        path = ensure_output_path(output_root, stem)
        write_output(path, payload)
    except OSError:
        return None
    return path


def serialize_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(), ensure_ascii=False, indent=2)
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError:
        return str(result)

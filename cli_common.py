"""Shared helpers for command-line entry points."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


@dataclass
class DirectiveBlock:
    """Instructions and structured parameters extracted for a prompt section."""

    instructions: str
    parameters: Dict[str, Any]


@dataclass
class PromptDirectives:
    """Parsed representation of a prompt broken into regional directive blocks."""

    main_text: str
    blocks: Dict[str, DirectiveBlock]
    raw_prompt: str


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


_SECTION_HEADER_PATTERN = re.compile(r"^\s*\[([A-Za-z0-9][A-Za-z0-9_\- ]*)\]\s*(.*)$")
_KEY_VALUE_PATTERN = re.compile(r"^\s*([A-Za-z0-9_\-\.]+)\s*(?:=|:)\s*(.+?)\s*$")


def _normalise_section_name(name: str) -> str:
    normalised = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return normalised.strip("_") or "global"


def _parse_sections_from_prompt(prompt: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"global": []}
    current = "global"
    for raw_line in prompt.splitlines():
        match = _SECTION_HEADER_PATTERN.match(raw_line)
        if match:
            section_name = _normalise_section_name(match.group(1))
            remainder = match.group(2).strip()
            current = section_name
            sections.setdefault(current, [])
            if remainder:
                sections[current].append(remainder)
            continue
        sections.setdefault(current, []).append(raw_line)
    return sections


def _split_instructions_and_parameters(text: str) -> Tuple[str, Dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return "", {}

    # Attempt to decode JSON directives first
    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError:
        decoded = None

    if isinstance(decoded, dict):
        return "", decoded

    parameters: Dict[str, Any] = {}
    instruction_lines: List[str] = []
    for raw_line in stripped.splitlines():
        match = _KEY_VALUE_PATTERN.match(raw_line)
        if match:
            key = match.group(1).strip().lower()
            value = match.group(2).strip()
            parameters[key] = value
        else:
            instruction_lines.append(raw_line)

    instructions = "\n".join(instruction_lines).strip()
    return instructions, parameters


def parse_prompt_directives(prompt: str) -> PromptDirectives:
    """
    Break a free-form prompt into directive sections using `[section]` headers.

    Example:
        Overall instructions here

        [data_triage]
        target_files = reddit_ai.json
        Limit results to high engagement threads.

    Returns a structure containing a main request plus per-section directives.
    """

    sections = _parse_sections_from_prompt(prompt)
    blocks: Dict[str, DirectiveBlock] = {}
    main_text = ""

    for name, lines in sections.items():
        joined = "\n".join(lines).strip()
        instructions, parameters = _split_instructions_and_parameters(joined)
        block = DirectiveBlock(instructions=instructions, parameters=parameters)
        blocks[name] = block
        if name == "global":
            main_text = instructions or joined

    return PromptDirectives(
        main_text=main_text.strip(),
        blocks=blocks,
        raw_prompt=prompt,
    )


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

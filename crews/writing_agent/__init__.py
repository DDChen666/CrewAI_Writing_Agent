"""Writing Agent package."""

from .crew import WritingAgentCrew
from .agents import (
    build_editor_in_chief_agent,
    build_editorial_guardian_agent,
    build_hook_architect_agent,
    build_master_writer_agent,
    build_writing_agent,
    build_writing_team,
)
from .tasks import (
    build_hook_task,
    build_quality_task,
    build_strategy_task,
    build_writing_task,
)
from .tools import (
    facebook_writer_tool,
    thread_writer_tool,
    x_writer_tool,
)

__all__ = [
    "WritingAgentCrew",
    "build_editor_in_chief_agent",
    "build_editorial_guardian_agent",
    "build_hook_architect_agent",
    "build_master_writer_agent",
    "build_writing_agent",
    "build_writing_team",
    "build_strategy_task",
    "build_hook_task",
    "build_quality_task",
    "build_writing_task",
    "facebook_writer_tool",
    "x_writer_tool",
    "thread_writer_tool",
]

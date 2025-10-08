"""Task definitions for the Writing Agent crew."""
from __future__ import annotations

from crewai import Task

from .schemas import HookConcept, StrategicBlueprint, WritingAgentOutput


def build_strategy_task(agent) -> Task:
    """Digest briefs and produce a DR-aligned strategic blueprint."""

    return Task(
        description=(
            "研讀 '{{pipeline_context}}' 中的 prioritized_topic_briefs 與 scored_and_filtered_opportunities，"  # noqa: E501
            "挑選最符合 '{{user_request}}' 指示的單一 brief。建立一份 Strategic Blueprint："  # noqa: E501
            "闡述目標受眾的痛點、品牌承諾、核心故事骨幹，以及你會啟用的 STEPPS 與進階心理觸發器（資訊差、FOMO、預期心理、社會認同等）。"  # noqa: E501
            "引用 dataset_id 可追溯的證據，必要時呼叫 content_explorer_tool 取得貼文或留言原文。"  # noqa: E501
            "同時列出潛在的編輯風險與緩解策略，確保後續寫作有依可循。"
        ),
        expected_output=(
            "輸出 StrategicBlueprint JSON，包含已選 brief 標題、受眾洞察、品牌承諾、故事節點、"  # noqa: E501
            "框架應用與風險備註。"
        ),
        agent=agent,
        async_execution=False,
        output_json_schema=StrategicBlueprint.model_json_schema(),
    )


def build_hook_task(agent, strategy_task: Task) -> Task:
    """Create cross-platform hooks and trigger stacks based on the blueprint."""

    return Task(
        description=(
            "根據策略藍圖（context 中的 StrategicBlueprint）與 '{{user_request}}'，"  # noqa: E501
            "設計多平台可用的 Hook 與敘事節奏。除非指令明確要求精簡，預設至少提供兩個 Hook。每個 Hook 需清楚說明吸睛句、承諾的價值、"  # noqa: E501
            "對應的心理觸發器堆疊，以及引用的資料洞察。視需求呼叫 facebook_writer、x_writer、thread_writer 工具取得語氣指引。"  # noqa: E501
            "保持精煉，避免無意義的長篇鋪陳。"
        ),
        expected_output=(
            "輸出 HookConcept JSON 陣列，每個元素包含 hook 文案、觸發器組合、支撐承諾的資料觀察與適用平台。"
        ),
        agent=agent,
        context=[strategy_task],
        async_execution=False,
        output_json_schema={
            "type": "array",
            "items": HookConcept.model_json_schema(),
        },
    )


def build_writing_task(agent, strategy_task: Task, hook_task: Task) -> Task:
    """Produce channel-ready drafts using the upstream assets."""

    return Task(
        description=(
            "閱讀 context 內的 StrategicBlueprint 與 HookConcept 清單。遵照 '{{user_request}}' 指示的主要平台，"  # noqa: E501
            "必要時加開其他高影響力平台。撰寫符合 WritingAgentOutput schema 的成品："  # noqa: E501
            "1) 每個 rewrite 需延續策略藍圖的故事弧；2) 明確引用 dataset_id + post_id 或 permalink；"  # noqa: E501
            "3) supporting_points 要點出數據或洞察來源；4) editorial_notes 紀錄假設、待審風險、建議 KPI。"  # noqa: E501
            "輸出時一併附上 strategic_blueprint 與 hook_concepts 以便追溯。"
        ),
        expected_output=(
            "回傳符合 WritingAgentOutput 的 JSON，至少 1 個 rewrite 變體，並整合 strategic_blueprint 與 hook_concepts。"
        ),
        agent=agent,
        context=[strategy_task, hook_task],
        async_execution=False,
        output_json_schema=WritingAgentOutput.model_json_schema(),
    )


def build_quality_task(agent, strategy_task: Task, hook_task: Task, writing_task: Task) -> Task:
    """Perform a final QA pass and append the quality review to the output."""

    return Task(
        description=(
            "審閱 context 中的 WritingAgentOutput，對照 StrategicBlueprint 與 HookConcept 確認："  # noqa: E501
            "心理觸發器是否落實、引用是否可追溯、品牌語氣是否一致。必要時可微調文案強化說服力，"  # noqa: E501
            "但請保留原作者意圖並記錄變更理由。最後輸出更新後的 WritingAgentOutput，並填寫 quality_review："  # noqa: E501
            "列出已完成的合規檢查、給人類編輯的改善建議與整體信心評分。"
        ),
        expected_output=(
            "輸出最終版 WritingAgentOutput JSON（含 quality_review）。若有調整請在 editorial_notes 裡說明。"
        ),
        agent=agent,
        context=[strategy_task, hook_task, writing_task],
        async_execution=False,
        output_json_schema=WritingAgentOutput.model_json_schema(),
    )


__all__ = [
    "build_strategy_task",
    "build_hook_task",
    "build_writing_task",
    "build_quality_task",
]

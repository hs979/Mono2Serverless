"""
CrewAI event-bus based tool timing monitor.

Why:
  Wrapping tool instances (_run monkey-patch) can break CrewAI's internal tool IO flow.
  CrewAI already emits ToolUsageStarted/Finished/Error events, which are provider-agnostic
  and safe to listen to.
"""

from __future__ import annotations

from typing import Any

from .performance_monitor import get_monitor

_installed: bool = False


def _safe_getattr(obj: Any, name: str, default: str = "") -> str:
    try:
        val = getattr(obj, name, None)
        return str(val) if val is not None else default
    except Exception:
        return default


def install_crewai_tool_event_monitor() -> bool:
    """
    Install event listeners to record tool call timing.

    Returns:
        bool: True if installed now, False if already installed or CrewAI not available.
    """
    global _installed
    if _installed:
        return False

    try:
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.types.tool_usage_events import (
            ToolUsageErrorEvent,
            ToolUsageFinishedEvent,
            ToolUsageStartedEvent,
        )
    except Exception:
        return False

    @crewai_event_bus.on(ToolUsageStartedEvent)
    def _on_tool_started(source: Any, event: Any) -> None:
        # We don't record here because started event doesn't include timestamps.
        return None

    @crewai_event_bus.on(ToolUsageFinishedEvent)
    def _on_tool_finished(source: Any, event: Any) -> None:
        monitor = get_monitor()
        if not monitor:
            return

        tool_name = _safe_getattr(event, "tool_name", "unknown")
        agent_role = _safe_getattr(event, "agent_role", "unknown")

        started_at = getattr(event, "started_at", None)
        finished_at = getattr(event, "finished_at", None)
        if not started_at or not finished_at:
            return

        start_ts = started_at.timestamp()
        end_ts = finished_at.timestamp()

        monitor.record_tool_call(
            tool_name=tool_name,
            agent_name=agent_role,
            start_time=start_ts,
            end_time=end_ts,
            success=True,
        )

    @crewai_event_bus.on(ToolUsageErrorEvent)
    def _on_tool_error(source: Any, event: Any) -> None:
        # Error events don't always carry timestamps; record a zero/unknown duration safely.
        monitor = get_monitor()
        if not monitor:
            return

        tool_name = _safe_getattr(event, "tool_name", "unknown")
        agent_role = _safe_getattr(event, "agent_role", "unknown")

        # Best effort timestamps if present
        started_at = getattr(event, "started_at", None)
        finished_at = getattr(event, "finished_at", None)
        if started_at and finished_at:
            start_ts = started_at.timestamp()
            end_ts = finished_at.timestamp()
        else:
            start_ts = end_ts = 0.0

        monitor.record_tool_call(
            tool_name=tool_name,
            agent_name=agent_role,
            start_time=start_ts,
            end_time=end_ts,
            success=False,
        )

    _installed = True
    return True


"""
CrewAI event-bus based LLM timing monitor.

Why this exists:
  Monkey-patching litellm.completion is not always reliable because CrewAI can route
  through native SDKs depending on provider/model. However, CrewAI always emits
  LLMCallStarted/Completed/Failed events from its LLM wrapper.

This module listens to those events and records per-call timing into PerformanceMonitor.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from .performance_monitor import get_monitor


@dataclass
class _StartStack:
    # allow nested / repeated calls per (agent, task, model)
    # store tuples to survive missing fields in failure events (e.g., model may be absent)
    starts: List[Tuple[float, str, str, str]] = field(default_factory=list)


_installed: bool = False
_start_times: Dict[Tuple[str, str], _StartStack] = {}


def _safe_getattr(obj: Any, name: str, default: str = "") -> str:
    try:
        val = getattr(obj, name, None)
        return str(val) if val is not None else default
    except Exception:
        return default


def _make_key(event: Any) -> Tuple[str, str, str]:
    """
    Key ONLY by agent_id + task_id.
    Reason: failure events (LLMCallFailedEvent) do not always include model, so using
    model in the key can prevent pairing start/end correctly.
    """
    agent_id = _safe_getattr(event, "agent_id", "unknown-agent")
    task_id = _safe_getattr(event, "task_id", "unknown-task")
    model = _safe_getattr(event, "model", "unknown-model")
    return (agent_id, task_id, model)


def _make_key_without_model(event: Any) -> Tuple[str, str]:
    agent_id = _safe_getattr(event, "agent_id", "unknown-agent")
    task_id = _safe_getattr(event, "task_id", "unknown-task")
    return (agent_id, task_id)


def install_crewai_llm_event_monitor() -> bool:
    """
    Install event listeners to record LLM call timing.

    Returns:
        bool: True if installed now, False if already installed or CrewAI not available.
    """
    global _installed
    if _installed:
        return False

    try:
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.types.llm_events import (
            LLMCallCompletedEvent,
            LLMCallFailedEvent,
            LLMCallStartedEvent,
        )
    except Exception:
        return False

    @crewai_event_bus.on(LLMCallStartedEvent)
    def _on_llm_started(source: Any, event: Any) -> None:
        key = _make_key_without_model(event)
        stack = _start_times.get(key)
        if stack is None:
            stack = _start_times[key] = _StartStack()
        start_time = time.time()
        model = _safe_getattr(event, "model", "unknown-model")
        agent_role = _safe_getattr(event, "agent_role", "unknown")
        task_name = _safe_getattr(event, "task_name", "unknown")
        stack.starts.append((start_time, model, agent_role, task_name))

    @crewai_event_bus.on(LLMCallCompletedEvent)
    def _on_llm_completed(source: Any, event: Any) -> None:
        key = _make_key_without_model(event)
        stack = _start_times.get(key)
        if not stack or not stack.starts:
            return

        start_time, model_from_start, agent_role_from_start, task_name_from_start = stack.starts.pop(0)
        end_time = time.time()
        duration = end_time - start_time

        monitor = get_monitor()
        if not monitor:
            return

        agent_role = _safe_getattr(event, "agent_role", agent_role_from_start or "unknown")
        task_name = _safe_getattr(event, "task_name", task_name_from_start or "unknown")
        model = _safe_getattr(event, "model", model_from_start or "unknown-model")

        monitor.record_llm_call(
            model=model,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=True,
            context=f"source=crewai_event_bus, agent={agent_role}, task={task_name}",
        )

    @crewai_event_bus.on(LLMCallFailedEvent)
    def _on_llm_failed(source: Any, event: Any) -> None:
        key = _make_key_without_model(event)
        stack = _start_times.get(key)
        if not stack or not stack.starts:
            return

        start_time, model_from_start, agent_role_from_start, task_name_from_start = stack.starts.pop(0)
        end_time = time.time()
        duration = end_time - start_time

        monitor = get_monitor()
        if not monitor:
            return

        agent_role = _safe_getattr(event, "agent_role", agent_role_from_start or "unknown")
        task_name = _safe_getattr(event, "task_name", task_name_from_start or "unknown")
        # failed event may not contain model, so prefer the start snapshot
        model = _safe_getattr(event, "model", model_from_start or "unknown-model")
        error = _safe_getattr(event, "error", "unknown error")

        monitor.record_llm_call(
            model=model,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=False,
            error=error,
            context=f"source=crewai_event_bus, agent={agent_role}, task={task_name}",
        )

    _installed = True
    return True


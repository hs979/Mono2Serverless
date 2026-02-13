#!/usr/bin/env python3
"""
Quick CrewAI kickoff timing smoke test (no full MAG workflow).

Goal:
  Verify that a real CrewAI kickoff triggers LLM calls that are recorded into
  storage/performance_logs via our early LiteLLM patch + PerformanceMonitor.

What it does:
  - Loads .env
  - Ensures project root is importable (so `import src...` works)
  - Normalizes model name for LiteLLM (OpenAI-compatible endpoints -> "openai/<model>")
  - Imports src.main (installs early LiteLLM patch)
  - Initializes PerformanceMonitor
  - Runs a minimal CrewAI kickoff: 1 agent, 1 task
  - Saves report and prints llm_calls summary
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _normalize_model_for_litellm() -> None:
    """
    LiteLLM requires a provider. If we're using an OpenAI-compatible base URL
    (e.g. DeepSeek via OPENAI_API_BASE), prefix the model with 'openai/'.
    """
    api_base = (os.getenv("OPENAI_API_BASE") or "").strip()
    model = (os.getenv("OPENAI_MODEL_NAME") or "").strip()
    if api_base and model and "/" not in model:
        prefixed = f"openai/{model}"
        os.environ["OPENAI_MODEL_NAME"] = prefixed
        # Some libs may read OPENAI_MODEL instead.
        os.environ.setdefault("OPENAI_MODEL", prefixed)


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root_dir))

    load_dotenv(root_dir / ".env")
    _normalize_model_for_litellm()

    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set in environment/.env")
        return 2

    # IMPORTANT: importing src.main installs the early LiteLLM patch before CrewAI imports.
    import src.main  # noqa: F401

    from src.utils import init_monitor

    log_dir = root_dir / "storage" / "performance_logs"
    monitor = init_monitor(log_dir)

    # Install provider-agnostic LLM timing via CrewAI event bus
    from src.utils import install_crewai_llm_event_monitor
    install_crewai_llm_event_monitor()

    # Now run a minimal CrewAI kickoff.
    from crewai import Agent, Task, Crew

    agent = Agent(
        role="Timing Smoke Test Agent",
        goal="Return a very short response.",
        backstory="You are a minimal agent used only to verify LLM timing instrumentation.",
        verbose=False,
        allow_delegation=False,
        max_iter=1,
    )

    task = Task(
        description="Reply with exactly: pong",
        expected_output="pong",
        agent=agent,
        verbose=False,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=False,
    )

    print("[quick_crewai_timing_test] Starting minimal CrewAI kickoff ...")
    try:
        result = crew.kickoff()
        print("[quick_crewai_timing_test] kickoff result (truncated):", str(result)[:200])
    except Exception as e:
        # Even failures should still be recorded by the patch (success=False)
        print("[quick_crewai_timing_test] kickoff failed:", e)

    report = monitor.save_report()
    llm_calls = report.get("llm_calls", [])

    print(f"[quick_crewai_timing_test] llm_calls recorded: {len(llm_calls)}")
    if llm_calls:
        print("[quick_crewai_timing_test] last llm_call record:")
        print(llm_calls[-1])
        return 0

    print("[quick_crewai_timing_test] No llm_calls recorded. CrewAI may not be using LiteLLM completion/acompletion path.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


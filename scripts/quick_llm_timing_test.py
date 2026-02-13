#!/usr/bin/env python3
"""
Quick LLM timing smoke test (no full MAG workflow).

Goal:
  Verify we can record per-LLM-call timing (send -> response) into performance logs.

What it does:
  - Loads .env
  - Imports src.main to enable the early LiteLLM patch (but does NOT run the crew workflow)
  - Initializes PerformanceMonitor
  - Makes ONE minimal LiteLLM call
  - Saves the performance report and prints the last llm_calls record
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    root_dir = Path(__file__).resolve().parents[1]
    # Ensure project root is importable so `import src...` works reliably.
    sys.path.insert(0, str(root_dir))
    load_dotenv(root_dir / ".env")

    # IMPORTANT: import src.main to install the early LiteLLM patch
    # (src.main only runs run_crew() when executed as __main__).
    import src.main  # noqa: F401

    from src.utils import init_monitor

    log_dir = root_dir / "storage" / "performance_logs"
    monitor = init_monitor(log_dir)

    import litellm

    model = os.getenv("OPENAI_MODEL_NAME", "unknown").strip()
    api_base = os.getenv("OPENAI_API_BASE")
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set in environment/.env")
        return 2

    # LiteLLM requires a provider. For OpenAI-compatible endpoints (e.g. DeepSeek via OPENAI_API_BASE),
    # the simplest is to prefix the model with "openai/".
    # Example: OPENAI_MODEL_NAME=deepseek-chat -> model="openai/deepseek-chat"
    if api_base and model and "/" not in model:
        model = f"openai/{model}"

    # Minimal request to keep it fast/cheap
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "temperature": 0,
        "max_tokens": 8,
    }
    if api_base:
        # LiteLLM uses api_base for OpenAI-compatible endpoints (e.g., DeepSeek).
        kwargs["api_base"] = api_base
    if api_key:
        kwargs["api_key"] = api_key

    print(f"[quick_llm_timing_test] Calling model={model} ...")
    try:
        _resp = litellm.completion(**kwargs)
    except Exception as e:
        # Even failures should still be recorded by the patch (success=False)
        print(f"[quick_llm_timing_test] LLM call failed: {e}")

    report = monitor.save_report()

    llm_calls = report.get("llm_calls", [])
    print(f"[quick_llm_timing_test] llm_calls recorded: {len(llm_calls)}")
    if llm_calls:
        print("[quick_llm_timing_test] last llm_call record:")
        print(llm_calls[-1])
        return 0

    print("[quick_llm_timing_test] No llm_calls recorded. Patch may not be intercepting the real call path.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


from pathlib import Path
import json
import os
import time
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]

# Load environment variables from .env file (尽早加载，避免 provider 在 import 阶段读取到旧环境)
load_dotenv(ROOT_DIR / ".env")

def _get_env(key: str) -> str:
    val = os.getenv(key)
    return (val or "").strip()


def validate_llm_env() -> None:
    """
    在真正调用 LLM 之前做一次快速自检，避免出现难读的 provider 栈追踪。

    你当前工程同时支持：
    - Gemini（Google Generative Language API）
    - OpenAI 兼容接口（如 DeepSeek）
    但两者的 API Key 格式/环境变量完全不同，配置错了会出现 400 API_KEY_INVALID。
    """
    model = _get_env("OPENAI_MODEL_NAME")

    # CrewAI 会根据模型名/配置选择 provider。
    # 当模型名包含 gemini 时，最终会走 googleapis.com 的 generativelanguage 接口，
    # 需要 GOOGLE_API_KEY（通常以 "AIza" 开头），而不是 "sk-"。
    if model and "gemini" in model.lower():
        google_key = _get_env("GOOGLE_API_KEY")
        if not google_key:
            raise ValueError(
                "检测到你配置的模型是 Gemini，但未设置 GOOGLE_API_KEY。\n"
                "请在 .env 中设置有效的 Google AI Studio (Gemini API) Key，例如：\n"
                "  GOOGLE_API_KEY=AIza...（不要带引号）\n"
                "然后重新运行：python src/main.py"
            )
        if google_key.lower().startswith("sk-"):
            raise ValueError(
                "检测到你配置的模型是 Gemini，但 GOOGLE_API_KEY 看起来像 OpenAI/DeepSeek 的 key（以 sk- 开头）。\n"
                "Gemini 的 Google API Key 通常以 'AIza' 开头，需要从 Google AI Studio 获取。\n"
                "请把 .env 的 GOOGLE_API_KEY 换成真实可用的 Gemini API Key 后重试。"
            )

    # OpenAI 兼容接口（例如 DeepSeek）常见配置自检
    if model and "deepseek" in model.lower():
        if not _get_env("OPENAI_API_KEY"):
            raise ValueError(
                "检测到你配置的模型可能是 DeepSeek/OpenAI 兼容接口，但 OPENAI_API_KEY 为空。\n"
                "请在 .env 中设置 OPENAI_API_KEY（并确保 OPENAI_API_BASE 指向对应服务）。"
            )


# 早失败：在导入/初始化 crew 之前就把配置问题报清楚
validate_llm_env()

def early_patch_litellm():
    """
    必须在导入 CrewAI 之前执行：
    CrewAI 可能在 import 阶段把 `litellm.completion` 绑定到局部符号，
    如果在导入之后再 patch `litellm.completion`，拦截会失效，导致 llm_calls=0。
    """
    try:
        import litellm

        # 避免重复 patch
        if getattr(litellm, "_monitor_early_patch_enabled", False):
            return True

        original_completion = getattr(litellm, "completion", None)
        original_acompletion = getattr(litellm, "acompletion", None)

        temp_calls = []

        def get_monitor_safely():
            # 只 import performance_monitor，避免引入 src.utils.__init__（会触发 crewai.tools 等依赖）
            try:
                from src.utils.performance_monitor import get_monitor as _get_monitor
                return _get_monitor()
            except Exception:
                return None

        def extract_tokens(result):
            if result is None:
                return None, None, None

            if isinstance(result, dict):
                usage = result.get("usage") or {}
                if isinstance(usage, dict):
                    return usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")
                return None, None, None

            usage = getattr(result, "usage", None)
            if usage is None:
                return None, None, None

            if isinstance(usage, dict):
                return usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")

            return (
                getattr(usage, "prompt_tokens", None),
                getattr(usage, "completion_tokens", None),
                getattr(usage, "total_tokens", None),
            )

        if callable(original_completion):
            def patched_completion(*args, **kwargs):
                start_time = time.time()
                model = kwargs.get("model", args[0] if args else "unknown")

                monitor = get_monitor_safely()
                call_rec = None
                if monitor is None:
                    call_rec = {"type": "sync", "model": model, "start_time": start_time}
                    temp_calls.append(call_rec)

                try:
                    result = original_completion(*args, **kwargs)
                    end_time = time.time()
                    duration = end_time - start_time

                    p, c, t = extract_tokens(result)

                    if monitor is not None:
                        monitor.record_llm_call(
                            model=str(model),
                            prompt_tokens=p,
                            completion_tokens=c,
                            total_tokens=t,
                            start_time=start_time,
                            end_time=end_time,
                            duration=duration,
                            success=True,
                            context="early_patch:sync"
                        )
                    else:
                        call_rec.update(
                            end_time=end_time,
                            duration=duration,
                            success=True,
                            tokens={"prompt": p, "completion": c, "total": t},
                        )
                    return result
                except Exception as e:
                    end_time = time.time()
                    duration = end_time - start_time
                    if monitor is not None:
                        monitor.record_llm_call(
                            model=str(model),
                            start_time=start_time,
                            end_time=end_time,
                            duration=duration,
                            success=False,
                            error=str(e),
                            context="early_patch:sync"
                        )
                    else:
                        call_rec.update(end_time=end_time, duration=duration, success=False, error=str(e))
                    raise

            litellm.completion = patched_completion

        if callable(original_acompletion):
            async def patched_acompletion(*args, **kwargs):
                start_time = time.time()
                model = kwargs.get("model", args[0] if args else "unknown")

                monitor = get_monitor_safely()
                call_rec = None
                if monitor is None:
                    call_rec = {"type": "async", "model": model, "start_time": start_time}
                    temp_calls.append(call_rec)

                try:
                    result = await original_acompletion(*args, **kwargs)
                    end_time = time.time()
                    duration = end_time - start_time

                    p, c, t = extract_tokens(result)

                    if monitor is not None:
                        monitor.record_llm_call(
                            model=str(model),
                            prompt_tokens=p,
                            completion_tokens=c,
                            total_tokens=t,
                            start_time=start_time,
                            end_time=end_time,
                            duration=duration,
                            success=True,
                            context="early_patch:async"
                        )
                    else:
                        call_rec.update(
                            end_time=end_time,
                            duration=duration,
                            success=True,
                            tokens={"prompt": p, "completion": c, "total": t},
                        )
                    return result
                except Exception as e:
                    end_time = time.time()
                    duration = end_time - start_time
                    if monitor is not None:
                        monitor.record_llm_call(
                            model=str(model),
                            start_time=start_time,
                            end_time=end_time,
                            duration=duration,
                            success=False,
                            error=str(e),
                            context="early_patch:async"
                        )
                    else:
                        call_rec.update(end_time=end_time, duration=duration, success=False, error=str(e))
                    raise

            litellm.acompletion = patched_acompletion

        # 保存供 run_crew 合并 pre-monitor 调用（通常为 0）
        litellm._monitor_temp_calls = temp_calls
        litellm._monitor_original_completion = original_completion
        litellm._monitor_original_acompletion = original_acompletion
        litellm._monitor_early_patch_enabled = True
        return True

    except Exception as e:
        print(f"[EARLY PATCH] Failed: {e}")
        return False


# 必须在导入 CrewAI 之前执行
early_patch_litellm()

# 现在才导入 CrewAI
from crewai import Agent, Task, Crew
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

from src.tools.file_tools import ReadFileTool, WriteFileTool, FileListTool
from src.tools.rag_tools import CodeRAGTool
from src.tools.sam_validate_tool import SAMValidateTool
from src.utils import (
    init_monitor,
    get_monitor,
    init_llm_callback,
    setup_litellm_callback,
    create_monitored_tool,
    install_crewai_llm_event_monitor,
    patch_crewai_all
)


def load_yaml(path: Path):
    import yaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_agents() -> dict:
    """构建三个核心Agent：Architect, Code Developer, SAM Engineer"""
    config = load_yaml(ROOT_DIR / "src" / "config" / "agents.yaml")

    # 初始化所有工具
    read_tool = ReadFileTool(ROOT_DIR)
    write_tool = WriteFileTool(ROOT_DIR)
    file_list_tool = FileListTool(ROOT_DIR)
    rag_tool = CodeRAGTool(ROOT_DIR / "storage" / "code_index")
    sam_validate_tool = SAMValidateTool()

    # 初始化 Knowledge Sources
    # TextFileKnowledgeSource 会自动在路径前添加 "knowledge/" 前缀
    # 所以这里只需要写文件名即可
    # 使用简化版以避免超过 embedding 模型的上下文长度限制
    sam_knowledge = TextFileKnowledgeSource(
        file_paths=["sam_reference.md"],
        chunk_size=1000,  # 减小 chunk 大小
        chunk_overlap=100  # 适当的重叠
    )
    
    # Basic Serverless 架构 Knowledge - 用于 Architect
    # 使用简化版的架构指南，专注于基本的serverless架构模式
    basic_serverless_knowledge = TextFileKnowledgeSource(
        file_paths=["basic_serverless_architecture.md"],
        chunk_size=800,
        chunk_overlap=100
    )

    agents = {}

    # 1. Architect - 架构设计师
    arch_cfg = config["architect"]
    # 为 Architect 工具添加监控
    arch_read = ReadFileTool(ROOT_DIR) # create_monitored_tool(ReadFileTool(ROOT_DIR), "architect")
    arch_write = WriteFileTool(ROOT_DIR) # create_monitored_tool(WriteFileTool(ROOT_DIR), "architect")
    
    agents["architect"] = Agent(
        role=arch_cfg["role"],
        goal=arch_cfg["goal"],
        backstory=arch_cfg["backstory"],
        tools=[arch_read, arch_write],  # 需要write来输出blueprint.json
        knowledge_sources=[basic_serverless_knowledge],  # 添加基本serverless架构知识库
        embedder={
            "provider": "ollama",
            "config": {}
        },
        verbose=True,
        allow_delegation=False,
    )

    # 2. Code Developer - 完整应用开发者
    code_cfg = config["code_developer"]
    # 为 Code Developer 工具添加监控
    code_read = ReadFileTool(ROOT_DIR) # create_monitored_tool(ReadFileTool(ROOT_DIR), "code_developer")
    code_rag = CodeRAGTool(ROOT_DIR / "storage" / "code_index") # create_monitored_tool(CodeRAGTool(ROOT_DIR / "storage" / "code_index"), "code_developer")
    code_write = WriteFileTool(ROOT_DIR) # create_monitored_tool(WriteFileTool(ROOT_DIR), "code_developer")
    
    agents["code_developer"] = Agent(
        role=code_cfg["role"],
        goal=code_cfg["goal"],
        backstory=code_cfg["backstory"],
        tools=[code_read, code_rag, code_write],
        knowledge_sources=[sam_knowledge],  # Explicitly allow access to SAM reference
        embedder={
            "provider": "ollama",
            "config": {}
        },
        verbose=True,
        allow_delegation=False,
    )

    # 3. SAM Engineer - SAM模板专家（替代原来的infra_engineer）
    sam_cfg = config["sam_engineer"]
    # 为 SAM Engineer 工具添加监控
    sam_read = ReadFileTool(ROOT_DIR) # create_monitored_tool(ReadFileTool(ROOT_DIR), "sam_engineer")
    sam_write = WriteFileTool(ROOT_DIR) # create_monitored_tool(WriteFileTool(ROOT_DIR), "sam_engineer")
    sam_list = FileListTool(ROOT_DIR) # create_monitored_tool(FileListTool(ROOT_DIR), "sam_engineer")
    sam_validate = SAMValidateTool() # create_monitored_tool(SAMValidateTool(), "sam_engineer")
    
    agents["sam_engineer"] = Agent(
        role=sam_cfg["role"],
        goal=sam_cfg["goal"],
        backstory=sam_cfg["backstory"],
        tools=[sam_read, sam_write, sam_list, sam_validate],
        knowledge_sources=[sam_knowledge],
        embedder={
            "provider": "ollama",
            "config": {}  # 配置从环境变量读取：EMBEDDINGS_OLLAMA_MODEL_NAME, EMBEDDINGS_OLLAMA_BASE_URL
        },
        verbose=True,
        allow_delegation=False,
    )

    return agents


def build_tasks(agents: dict) -> list:
    """构建任务链：架构设计 → 代码生成 → SAM模板生成"""
    config = load_yaml(ROOT_DIR / "src" / "config" / "tasks.yaml")
    tasks_cfg = config["tasks"]

    tasks: list[Task] = []

    for task_cfg in tasks_cfg:
        agent_id = task_cfg["agent"]
        agent = agents.get(agent_id)
        
        if not agent:
            print(f"Warning: Agent '{agent_id}' not found, skipping task {task_cfg.get('id')}")
            continue
        
        # 创建任务
        task = Task(
            description=task_cfg["description"],
            expected_output=task_cfg.get("expected_output", "Task completed successfully"),
            agent=agent,
            verbose=True,
        )
        
        # 如果指定了output_file，设置输出文件
        if "output_file" in task_cfg:
            task.output_file = task_cfg["output_file"]
        
        tasks.append(task)

    return tasks


def run_crew() -> None:
    """运行Multi-Agent Crew进行单体应用到serverless的迁移"""
    print("=" * 60)
    print("MAG System - Monolith to AWS Serverless Migration")
    print("=" * 60)
    
    # 初始化性能监控
    log_dir = ROOT_DIR / "storage" / "performance_logs"
    monitor = init_monitor(log_dir)

    # Prefer CrewAI event-bus based LLM timing (provider-agnostic).
    # This makes LLM timing reliable even when CrewAI routes through native SDKs.
    install_crewai_llm_event_monitor()
    
    # 转移早期 patch 收集的临时数据到监控器
    try:
        import litellm
        if hasattr(litellm, '_monitor_temp_calls'):
            temp_calls = litellm._monitor_temp_calls
            print(f"\n[MONITOR] Found {len(temp_calls)} LLM calls from early patch")
            
            # 将临时数据转移到监控器
            for call in temp_calls:
                if monitor:
                    tokens = call.get('tokens', {})
                    monitor.record_llm_call(
                        model=call.get('model', 'unknown'),
                        prompt_tokens=tokens.get('prompt') if tokens else None,
                        completion_tokens=tokens.get('completion') if tokens else None,
                        total_tokens=tokens.get('total') if tokens else None,
                        start_time=call.get('start_time'),
                        end_time=call.get('end_time'),
                        duration=call.get('duration'),
                        success=call.get('success', True),
                        error=call.get('error'),
                        context=f"type={call.get('type', 'unknown')}"
                    )
            
            # 清空临时数据
            litellm._monitor_temp_calls.clear()
    except Exception as e:
        print(f"[MONITOR] Failed to transfer temp calls: {e}")
    
    # 初始化 LLM 回调监控（备用方案）
    init_llm_callback()
    setup_litellm_callback()
    
    # Patch CrewAI 以监控 LLM 调用、Agent 和 Task 执行
    # 注意：LLM 调用已经在早期 patch 了，这里主要 patch Agent 和 Task
    patch_crewai_all()
    
    # 记录总开始时间
    workflow_start = time.time()
    
    agents = build_agents()
    tasks = build_tasks(agents)

    print(f"\nInitialized {len(agents)} agents and {len(tasks)} tasks.")
    print("\nAgent roles:")
    for name, agent in agents.items():
        print(f"  - {name}: {agent.role}")
    
    print("\nStarting migration workflow...\n")

    crew = Crew(
        agents=list(agents.values()),
        tasks=tasks,
        verbose=True,
    )
    
    # 显示即将执行的 tasks 概览
    print("\n" + "=" * 60)
    print(f"准备顺序执行 {len(tasks)} 个任务：")
    print("=" * 60)
    for i, task in enumerate(tasks):
        agent_role = task.agent.role if task.agent else "unknown"
        print(f"  Task {i+1}: {agent_role}")
    print("=" * 60 + "\n")
    
    # 执行 crew（CrewAI 会顺序执行所有 tasks）
    crew_start = time.time()
    result = crew.kickoff()
    crew_end = time.time()
    
    # 由于 CrewAI 会顺序执行所有 tasks，我们需要从输出中推断每个 task 的时间
    # 这里我们记录整体的 crew 执行时间
    crew_duration = crew_end - crew_start
    print(f"\nCrew 总执行时间: {crew_duration:.2f}秒 ({crew_duration/60:.2f}分钟)")
    
    # 尝试从 result 中提取 task 信息
    if hasattr(result, 'tasks_output') and result.tasks_output:
        print("\n任务执行摘要：")
        for i, task_output in enumerate(result.tasks_output):
            if i < len(tasks):
                agent_name = tasks[i].agent.role if tasks[i].agent else "unknown"
                print(f"  Task {i+1} ({agent_name}) - 已完成")

    workflow_end = time.time()
    workflow_duration = workflow_end - workflow_start

    print("\n" + "=" * 60)
    print("Migration workflow completed!")
    print("=" * 60)
    print(f"工作流总时间: {workflow_duration:.2f}秒 ({workflow_duration/60:.2f}分钟)")
    print("\nResult:")
    print(json.dumps({"result": str(result)}, indent=2, ensure_ascii=False))
    
    print("\nGenerated artifacts:")
    print("  - storage/blueprint.json (Architecture blueprint)")
    print("  - output/backend/ (Lambda functions and shared code)")
    print("  - output/frontend/ (Migrated frontend application, if applicable)")
    print("  - output/infrastructure/template.yaml (AWS SAM template)")
    print("\nNext steps:")
    print("  1. Review the generated code in output/")
    print("  2. Configure deployment parameters")
    print("  3. Run: sam build && sam deploy --guided")

    # 保存性能报告
    print("\n" + "=" * 60)
    print("生成性能分析报告...")
    print("=" * 60)
    monitor.save_report()
    monitor.print_summary()


if __name__ == "__main__":
    run_crew()


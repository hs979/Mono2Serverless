from pathlib import Path
import json
import os
import time
import sys
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]

load_dotenv(ROOT_DIR / ".env", override=True)


def configure_console_encoding() -> None:
    """Force UTF-8 console output to avoid Windows GBK UnicodeEncodeError."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


configure_console_encoding()


def _get_env(key: str) -> str:
    val = os.getenv(key)
    return (val or "").strip()


def validate_llm_env() -> None:
    """
    在真正调用 LLM 之前做一次快速自检，避免出现难读的 provider 栈追踪。

    支持：
    - Gemini（Google Generative Language API）
    - OpenAI 兼容接口（如 DeepSeek）
    """
    model = _get_env("OPENAI_MODEL_NAME")

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

    if model and "deepseek" in model.lower():
        if not _get_env("OPENAI_API_KEY"):
            raise ValueError(
                "检测到你配置的模型可能是 DeepSeek/OpenAI 兼容接口，但 OPENAI_API_KEY 为空。\n"
                "请在 .env 中设置 OPENAI_API_KEY（并确保 OPENAI_API_BASE 指向对应服务）。"
            )


validate_llm_env()

from crewai import Agent, Task, Crew
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource

from src.tools.file_tools import ReadFileTool, WriteFileTool, FileListTool
from src.tools.rag_tools import CodeRAGTool
from src.tools.sam_validate_tool import SAMValidateTool


def load_yaml(path: Path):
    import yaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


OLLAMA_EMBEDDER_CONFIG = {
    "provider": "ollama",
    "config": {
        "model": "mxbai-embed-large",
        "base_url": "http://127.0.0.1:11434"
    }
}


def build_agents() -> dict:
    """构建四个核心 Agent：Architect, Code Developer, SAM Engineer, Consistency Validator"""
    config = load_yaml(ROOT_DIR / "src" / "config" / "agents.yaml")

    # Knowledge Sources
    sam_knowledge = TextFileKnowledgeSource(
        file_paths=["sam_reference.md"],
        chunk_size=1200,
        chunk_overlap=150
    )

    lambda_coding_knowledge = TextFileKnowledgeSource(
        file_paths=["lambda_coding_reference.md"],
        chunk_size=1200,
        chunk_overlap=150
    )

    basic_serverless_knowledge = TextFileKnowledgeSource(
        file_paths=["basic_serverless_architecture.md"],
        chunk_size=1200,
        chunk_overlap=150
    )

    async_patterns_knowledge = TextFileKnowledgeSource(
        file_paths=["async_serverless_patterns.md"],
        chunk_size=1200,
        chunk_overlap=150
    )

    agents = {}

    # 1. Architect
    arch_cfg = config["architect"]
    agents["architect"] = Agent(
        role=arch_cfg["role"],
        goal=arch_cfg["goal"],
        backstory=arch_cfg["backstory"],
        tools=[ReadFileTool(ROOT_DIR), WriteFileTool(ROOT_DIR)],
        knowledge_sources=[basic_serverless_knowledge, async_patterns_knowledge],
        embedder=OLLAMA_EMBEDDER_CONFIG,
        verbose=True,
        allow_delegation=False,
        max_iter=50
    )

    # 2. Code Developer
    code_cfg = config["code_developer"]
    agents["code_developer"] = Agent(
        role=code_cfg["role"],
        goal=code_cfg["goal"],
        backstory=code_cfg["backstory"],
        tools=[
            ReadFileTool(ROOT_DIR),
            CodeRAGTool(ROOT_DIR / "storage" / "code_index"),
            WriteFileTool(ROOT_DIR),
        ],
        knowledge_sources=[lambda_coding_knowledge, async_patterns_knowledge],
        embedder=OLLAMA_EMBEDDER_CONFIG,
        verbose=True,
        allow_delegation=False,
        max_iter=100
    )

    # 3. SAM Engineer
    sam_cfg = config["sam_engineer"]
    agents["sam_engineer"] = Agent(
        role=sam_cfg["role"],
        goal=sam_cfg["goal"],
        backstory=sam_cfg["backstory"],
        tools=[
            ReadFileTool(ROOT_DIR),
            WriteFileTool(ROOT_DIR),
            FileListTool(ROOT_DIR),
            SAMValidateTool(ROOT_DIR),
        ],
        knowledge_sources=[sam_knowledge],
        embedder=OLLAMA_EMBEDDER_CONFIG,
        verbose=True,
        allow_delegation=False,
        max_iter=50
    )

    # 4. Consistency Validator
    cv_cfg = config["consistency_validator"]
    agents["consistency_validator"] = Agent(
        role=cv_cfg["role"],
        goal=cv_cfg["goal"],
        backstory=cv_cfg["backstory"],
        tools=[
            ReadFileTool(ROOT_DIR),
            WriteFileTool(ROOT_DIR),
            FileListTool(ROOT_DIR),
            SAMValidateTool(ROOT_DIR),
        ],
        knowledge_sources=[sam_knowledge, lambda_coding_knowledge, async_patterns_knowledge],
        embedder=OLLAMA_EMBEDDER_CONFIG,
        verbose=True,
        allow_delegation=False,
        max_iter=30
    )

    return agents


def build_tasks(agents: dict) -> list:
    """构建任务链：架构设计 → 代码生成 → SAM模板生成 → 一致性验证"""
    config = load_yaml(ROOT_DIR / "src" / "config" / "tasks.yaml")
    tasks_cfg = config["tasks"]

    tasks: list[Task] = []

    # 这些 task 清空前序上下文，避免 context window 溢出。
    # 它们完全依赖磁盘文件而非 CrewAI 传递的上游 task output。
    context_clearing_tasks = {
        "generate_complete_application",
        "generate_shared_resources_template",
        "generate_functions_template",
        "assemble_final_template",
        "validate_consistency",
    }

    for task_cfg in tasks_cfg:
        agent_id = task_cfg["agent"]
        agent = agents.get(agent_id)

        if not agent:
            print(f"Warning: Agent '{agent_id}' not found, skipping task {task_cfg.get('id')}")
            continue

        task_kwargs = {
            "description": task_cfg["description"],
            "expected_output": task_cfg.get("expected_output", "Task completed successfully"),
            "agent": agent,
            "verbose": True,
        }

        if task_cfg.get("id") in context_clearing_tasks:
            task_kwargs["context"] = []

        task = Task(**task_kwargs)

        if "output_file" in task_cfg:
            task.output_file = task_cfg["output_file"]

        tasks.append(task)

    return tasks


def run_crew() -> None:
    """运行 Multi-Agent Crew 进行单体应用到 serverless 的迁移"""
    try:
        print("=" * 60)
        print("MAG System - Monolith to AWS Serverless Migration")
        print("=" * 60)

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
            memory=False,
            embedder=OLLAMA_EMBEDDER_CONFIG,
        )

        print("\n" + "=" * 60)
        print(f"准备顺序执行 {len(tasks)} 个任务：")
        print("=" * 60)
        for i, task in enumerate(tasks):
            agent_role = task.agent.role if task.agent else "unknown"
            print(f"  Task {i+1}: {agent_role}")
        print("=" * 60 + "\n")

        crew_start = time.time()
        result = crew.kickoff()
        crew_end = time.time()

        crew_duration = crew_end - crew_start
        print(f"\nCrew 总执行时间: {crew_duration:.2f}秒 ({crew_duration/60:.2f}分钟)")

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
        print("  - output/lambdas/ (Lambda functions and shared code)")
        print("  - output/layers/ (Shared Lambda layers, if applicable)")
        print("  - output/template.yaml (AWS SAM template)")
        print("  - output/consistency_report.json (Cross-artifact validation report)")
        print("\nNext steps:")
        print("  1. Review the generated code in output/")
        print("  2. Configure deployment parameters")
        print("  3. Run: sam build && sam deploy --guided")

    except BaseException as e:
        import traceback
        error_msg = f"\nCRITICAL ERROR: {str(e)}\n\n{traceback.format_exc()}"
        try:
            print(error_msg)
        except UnicodeEncodeError:
            print(error_msg.encode("utf-8", errors="replace").decode("utf-8"))

        crash_log = ROOT_DIR / "crash_report.log"
        with open(crash_log, "w", encoding="utf-8") as f:
            f.write(error_msg)
        print(f"\nCrash report saved to: {crash_log}")
        raise


if __name__ == "__main__":
    run_crew()

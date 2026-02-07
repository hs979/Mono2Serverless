from pathlib import Path
import json
import os
import time
from dotenv import load_dotenv

# ⚠️ 关键：在导入 CrewAI 之前先 patch LiteLLM
# 这样 CrewAI 导入时就会使用我们 patch 过的版本
def early_patch_litellm():
    """在导入 CrewAI 之前 patch LiteLLM"""
    try:
        import litellm
        from functools import wraps
        
        # 导入监控模块（但不初始化，稍后初始化）
        # 这里我们只是设置 patch，监控器稍后才创建
        
        # 保存原始方法
        _original_completion = litellm.completion
        _original_acompletion = litellm.acompletion if hasattr(litellm, 'acompletion') else None
        
        # 创建全局调用记录（临时，稍后会被监控器接管）
        _temp_calls = []
        
        def patched_completion(*args, **kwargs):
            start_time = time.time()
            model = kwargs.get('model', args[0] if args else 'unknown')
            
            # 临时记录（稍后转移到监控器）
            _temp_calls.append({
                'type': 'sync',
                'model': model,
                'start_time': start_time
            })
            
            print(f"[LLM PATCH] Sync call to: {model}")
            
            try:
                result = _original_completion(*args, **kwargs)
                end_time = time.time()
                _temp_calls[-1]['end_time'] = end_time
                _temp_calls[-1]['duration'] = end_time - start_time
                _temp_calls[-1]['success'] = True
                
                # 尝试提取 token 信息
                if hasattr(result, 'usage'):
                    _temp_calls[-1]['tokens'] = {
                        'prompt': getattr(result.usage, 'prompt_tokens', None),
                        'completion': getattr(result.usage, 'completion_tokens', None),
                        'total': getattr(result.usage, 'total_tokens', None)
                    }
                
                return result
            except Exception as e:
                end_time = time.time()
                _temp_calls[-1]['end_time'] = end_time
                _temp_calls[-1]['duration'] = end_time - start_time
                _temp_calls[-1]['success'] = False
                _temp_calls[-1]['error'] = str(e)
                raise
        
        async def patched_acompletion(*args, **kwargs):
            start_time = time.time()
            model = kwargs.get('model', args[0] if args else 'unknown')
            
            _temp_calls.append({
                'type': 'async',
                'model': model,
                'start_time': start_time
            })
            
            print(f"[LLM PATCH] Async call to: {model}")
            
            try:
                result = await _original_acompletion(*args, **kwargs)
                end_time = time.time()
                _temp_calls[-1]['end_time'] = end_time
                _temp_calls[-1]['duration'] = end_time - start_time
                _temp_calls[-1]['success'] = True
                
                if hasattr(result, 'usage'):
                    _temp_calls[-1]['tokens'] = {
                        'prompt': getattr(result.usage, 'prompt_tokens', None),
                        'completion': getattr(result.usage, 'completion_tokens', None),
                        'total': getattr(result.usage, 'total_tokens', None)
                    }
                
                return result
            except Exception as e:
                end_time = time.time()
                _temp_calls[-1]['end_time'] = end_time
                _temp_calls[-1]['duration'] = end_time - start_time
                _temp_calls[-1]['success'] = False
                _temp_calls[-1]['error'] = str(e)
                raise
        
        # 应用 patch
        litellm.completion = patched_completion
        if _original_acompletion:
            litellm.acompletion = patched_acompletion
        
        # 保存这些变量供后续使用
        litellm._monitor_temp_calls = _temp_calls
        litellm._monitor_original_completion = _original_completion
        litellm._monitor_original_acompletion = _original_acompletion
        
        print("[EARLY PATCH] LiteLLM methods patched before CrewAI import")
        return True
        
    except Exception as e:
        print(f"[EARLY PATCH] Failed: {e}")
        return False

# 执行早期 patch
early_patch_litellm()

# 现在才导入 CrewAI（此时它会使用我们 patch 过的 litellm）
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
    patch_crewai_all
)


ROOT_DIR = Path(__file__).resolve().parents[1]

# Load environment variables from .env file
load_dotenv(ROOT_DIR / ".env")


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
    
    # Serverless 架构模式 Knowledge - 用于 Architect
    serverless_patterns_knowledge = TextFileKnowledgeSource(
        file_paths=["serverless_architecture_patterns.md"],
        chunk_size=800,
        chunk_overlap=100
    )

    agents = {}

    # 1. Architect - 架构设计师
    arch_cfg = config["architect"]
    # 为 Architect 工具添加监控
    arch_read = create_monitored_tool(ReadFileTool(ROOT_DIR), "architect")
    arch_write = create_monitored_tool(WriteFileTool(ROOT_DIR), "architect")
    
    agents["architect"] = Agent(
        role=arch_cfg["role"],
        goal=arch_cfg["goal"],
        backstory=arch_cfg["backstory"],
        tools=[arch_read, arch_write],  # 需要write来输出blueprint.json
        knowledge_sources=[serverless_patterns_knowledge],  # 添加架构模式知识库
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
    code_read = create_monitored_tool(ReadFileTool(ROOT_DIR), "code_developer")
    code_rag = create_monitored_tool(CodeRAGTool(ROOT_DIR / "storage" / "code_index"), "code_developer")
    code_write = create_monitored_tool(WriteFileTool(ROOT_DIR), "code_developer")
    
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
    sam_read = create_monitored_tool(ReadFileTool(ROOT_DIR), "sam_engineer")
    sam_write = create_monitored_tool(WriteFileTool(ROOT_DIR), "sam_engineer")
    sam_list = create_monitored_tool(FileListTool(ROOT_DIR), "sam_engineer")
    sam_validate = create_monitored_tool(SAMValidateTool(), "sam_engineer")
    
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


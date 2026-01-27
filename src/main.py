from pathlib import Path
import json

from crewai import Agent, Task, Crew

from src.tools.file_tools import ReadFileTool, WriteFileTool, FileListTool
from src.tools.rag_tools import CodeRAGTool
from src.tools.sam_validate_tool import SAMValidateTool
from src.tools.sam_doc_tool import SAMDocSearchTool


ROOT_DIR = Path(__file__).resolve().parents[1]


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
    sam_doc_tool = SAMDocSearchTool()

    agents = {}

    # 1. Architect - 架构设计师
    arch_cfg = config["architect"]
    agents["architect"] = Agent(
        role=arch_cfg["role"],
        goal=arch_cfg["goal"],
        backstory=arch_cfg["backstory"],
        tools=[read_tool, write_tool],  # 需要write来输出blueprint.json
        verbose=True,
        allow_delegation=False,
    )

    # 2. Code Developer - 完整应用开发者
    code_cfg = config["code_developer"]
    agents["code_developer"] = Agent(
        role=code_cfg["role"],
        goal=code_cfg["goal"],
        backstory=code_cfg["backstory"],
        tools=[read_tool, rag_tool, write_tool],
        verbose=True,
        allow_delegation=False,
    )

    # 3. SAM Engineer - SAM模板专家（替代原来的infra_engineer）
    sam_cfg = config["sam_engineer"]
    agents["sam_engineer"] = Agent(
        role=sam_cfg["role"],
        goal=sam_cfg["goal"],
        backstory=sam_cfg["backstory"],
        tools=[read_tool, write_tool, file_list_tool, sam_validate_tool, sam_doc_tool],
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
    
    result = crew.kickoff()

    print("\n" + "=" * 60)
    print("Migration workflow completed!")
    print("=" * 60)
    print("\nResult:")
    print(json.dumps({"result": str(result)}, indent=2, ensure_ascii=False))
    
    print("\nGenerated artifacts:")
    print("  - storage/blueprint.json (Architecture blueprint)")
    print("  - output/backend/ (Lambda functions and shared code)")
    print("  - output/frontend/ (Migrated frontend application)")
    print("  - output/infrastructure/template.yaml (AWS SAM template)")
    print("\nNext steps:")
    print("  1. Review the generated code in output/")
    print("  2. Configure deployment parameters")
    print("  3. Run: sam build && sam deploy --guided")


if __name__ == "__main__":
    run_crew()


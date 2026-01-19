from pathlib import Path
import json

from crewai import Agent, Task, Crew

from src.tools.file_tools import ReadFileTool, WriteFileTool
from src.tools.rag_tools import CodeRAGTool
from src.tools.sam_validate_tool import SAMValidateTool


ROOT_DIR = Path(__file__).resolve().parents[1]


def load_yaml(path: Path):
    import yaml

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_agents() -> dict:
    config = load_yaml(ROOT_DIR / "src" / "config" / "agents.yaml")

    read_tool = ReadFileTool(ROOT_DIR)
    write_tool = WriteFileTool(ROOT_DIR)
    rag_tool = CodeRAGTool(ROOT_DIR / "storage" / "code_index")
    sam_validate_tool = SAMValidateTool()

    agents = {}

    arch_cfg = config["architect"]
    agents["architect"] = Agent(
        role=arch_cfg["role"],
        goal=arch_cfg["goal"],
        backstory=arch_cfg["backstory"],
        tools=[read_tool],
        verbose=True,
    )

    infra_cfg = config["infra_engineer"]
    agents["infra_engineer"] = Agent(
        role=infra_cfg["role"],
        goal=infra_cfg["goal"],
        backstory=infra_cfg["backstory"],
        tools=[write_tool, sam_validate_tool],
        verbose=True,
    )

    code_cfg = config["code_developer"]
    agents["code_developer"] = Agent(
        role=code_cfg["role"],
        goal=code_cfg["goal"],
        backstory=code_cfg["backstory"],
        tools=[read_tool, rag_tool, write_tool],
        verbose=True,
    )

    return agents


def build_tasks(agents: dict) -> list:
    config = load_yaml(ROOT_DIR / "src" / "config" / "tasks.yaml")
    tasks_cfg = config["tasks"]

    tasks: list[Task] = []

    for task_cfg in tasks_cfg:
        agent = agents[task_cfg["agent"]]
        description = task_cfg["description"]
        tasks.append(Task(description=description, agent=agent, verbose=True))

    return tasks


def run_crew() -> None:
    agents = build_agents()
    tasks = build_tasks(agents)

    crew = Crew(agents=list(agents.values()), tasks=tasks, verbose=True)
    result = crew.kickoff()

    print("Crew run completed.")
    print(json.dumps({"result": str(result)}, indent=2))


if __name__ == "__main__":
    run_crew()


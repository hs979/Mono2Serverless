from pathlib import Path
from typing import Optional


class ReadFileTool:
    """Simple file reader tool for agents.

    Agents should use paths relative to the mag-system root when possible.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]

    def read(self, path: str) -> str:
        target = (self.root / path).resolve()
        with target.open("r", encoding="utf-8", errors="ignore") as f:
            return f.read()


class WriteFileTool:
    """Simple file writer tool for agents."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]

    def write(self, path: str, content: str) -> str:
        target = (self.root / path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as f:
            f.write(content)
        return str(target)


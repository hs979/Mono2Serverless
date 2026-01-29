from pathlib import Path
from typing import Optional, List, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# --- Input Schemas ---

class ReadFileInput(BaseModel):
    """Input schema for ReadFileTool."""
    path: str = Field(..., description="Relative path to the file to read (e.g., 'src/main.py').")

class WriteFileInput(BaseModel):
    """Input schema for WriteFileTool."""
    path: str = Field(..., description="Relative path to the file to write.")
    content: str = Field(..., description="The content to write to the file.")

class FileListInput(BaseModel):
    """Input schema for FileListTool."""
    path: str = Field(default=".", description="Relative path to list files from (defaults to root).")
    recursive: bool = Field(default=False, description="If True, list files recursively.")

# --- Tools ---

class ReadFileTool(BaseTool):
    name: str = "ReadFileTool"
    description: str = "Read content from a file at the given path."
    args_schema: Type[BaseModel] = ReadFileInput
    root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])

    def __init__(self, root: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        if root:
            self.root = root

    def _run(self, path: str) -> str:
        try:
            target = (self.root / path).resolve()
            if not target.exists():
                return f"Error: File not found: {path}"
            with target.open("r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

class WriteFileTool(BaseTool):
    name: str = "WriteFileTool"
    description: str = "Write content to a file at the given path. Creates directories if needed."
    args_schema: Type[BaseModel] = WriteFileInput
    root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])

    def __init__(self, root: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        if root:
            self.root = root

    def _run(self, path: str, content: str) -> str:
        try:
            target = (self.root / path).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

class FileListTool(BaseTool):
    name: str = "FileListTool"
    description: str = "List files and directories at the given path. Useful for exploring file structure."
    args_schema: Type[BaseModel] = FileListInput
    root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])

    def __init__(self, root: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        if root:
            self.root = root

    def _run(self, path: str = ".", recursive: bool = False) -> List[str]:
        target = (self.root / path).resolve()
        
        if not target.exists():
            return [f"Error: Path does not exist: {path}"]
        
        if not target.is_dir():
            return [f"Error: Path is not a directory: {path}"]
        
        try:
            if recursive:
                files = []
                for p in target.rglob('*'):
                    if p.is_file():
                        rel_path = p.relative_to(target)
                        files.append(str(rel_path))
                return sorted(files)
            else:
                items = []
                for p in target.iterdir():
                    name = p.name
                    if p.is_dir():
                        name += "/"
                    items.append(name)
                return sorted(items)
        except Exception as e:
            return [f"Error listing directory: {str(e)}"]

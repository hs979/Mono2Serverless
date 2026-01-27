from pathlib import Path
from typing import Optional, List


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


class FileListTool:
    """File and directory listing tool for agents.
    
    Allows agents to discover file structures, especially useful for
    SAM Engineer to scan generated Lambda directories.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]

    def list_dir(self, path: str, recursive: bool = False) -> List[str]:
        """List files and directories at the given path.
        
        Args:
            path: Relative path from root
            recursive: If True, recursively list all files
            
        Returns:
            List of file/directory names (or paths if recursive)
        """
        target = (self.root / path).resolve()
        
        if not target.exists():
            return [f"Error: Path does not exist: {path}"]
        
        if not target.is_dir():
            return [f"Error: Path is not a directory: {path}"]
        
        try:
            if recursive:
                # Return all files recursively with relative paths
                files = []
                for p in target.rglob('*'):
                    if p.is_file():
                        rel_path = p.relative_to(target)
                        files.append(str(rel_path))
                return sorted(files)
            else:
                # Return immediate children only
                items = []
                for p in target.iterdir():
                    name = p.name
                    if p.is_dir():
                        name += "/"
                    items.append(name)
                return sorted(items)
        except Exception as e:
            return [f"Error listing directory: {str(e)}"]


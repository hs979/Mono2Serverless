import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

class SAMValidateInput(BaseModel):
    """Input schema for SAMValidateTool."""
    yaml_content: str = Field(..., description="The content of the SAM template.yaml file to validate.")

class SAMValidateTool(BaseTool):
    name: str = "SAMValidateTool"
    description: str = "Validate an AWS SAM template using cfn-lint. Returns success status and validation output."
    args_schema: Type[BaseModel] = SAMValidateInput

    def _run(self, yaml_content: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "template.yaml"
            path.write_text(yaml_content, encoding="utf-8")

            try:
                proc = subprocess.run(
                    ["cfn-lint", str(path)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except FileNotFoundError:
                return "Error: cfn-lint command not found. Please ensure it is installed."

            output = proc.stdout + proc.stderr
            if proc.returncode == 0:
                return "Validation Successful! No errors found."
            else:
                return f"Validation Failed:\n{output}"

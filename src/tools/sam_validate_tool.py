import subprocess
import tempfile
from pathlib import Path
from typing import Tuple


class SAMValidateTool:
    """Validate an AWS SAM template.yaml using cfn-lint.

    The Infra Agent should call this tool with the YAML content it has
    generated. The tool writes to a temporary file, invokes `cfn-lint`, and
    returns (ok, output).
    """

    def __init__(self) -> None:
        pass

    def validate(self, yaml_content: str) -> Tuple[bool, str]:
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
                # cfn-lint not installed: treat as non-fatal but report back
                return False, "cfn-lint not found. Please install it in the environment."

            ok = proc.returncode == 0
            output = proc.stdout + proc.stderr
            return ok, output


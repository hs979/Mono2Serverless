import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Set

import ast


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MONOLITH_DIR = ROOT_DIR / "input_monolith"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "storage" / "analysis_report.json"


PY_ENTRY_METHOD_DECORATORS = {"get", "post", "put", "delete", "patch"}
EXPRESS_HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

# 需要忽略的目录列表（用于项目结构可视化和代码分析）
IGNORE_DIRS = {
    'venv',
    'env',
    '.venv',
    '__pycache__',
    'node_modules',
    '.git',
    '.idea',
    '.vscode',
    'dist',
    'build',
    '.pytest_cache',
    '.mypy_cache',
    'htmlcov',
    '.tox',
    'eggs',
    '.eggs',
}


def build_project_structure(root: Path) -> str:
    lines: List[str] = []

    def _walk(current: Path, prefix: str = "") -> None:
        # 过滤隐藏文件/目录和需要忽略的目录
        entries = sorted([
            p for p in current.iterdir() 
            if not p.name.startswith(".") and p.name not in IGNORE_DIRS
        ])
        for idx, entry in enumerate(entries):
            connector = "└── " if idx == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if idx == len(entries) - 1 else "│   "
                _walk(entry, prefix + extension)

    lines.append(root.name + "/")
    if root.exists():
        _walk(root)
    return "\n".join(lines)


def tag_file(source: str) -> List[str]:
    tags: Set[str] = set()
    lower = source.lower()
    
    # AWS SDK 检测
    if "boto3" in lower:
        tags.add("AWS_SDK")
    
    # DynamoDB 数据库检测
    # Python: boto3 + dynamodb 相关操作
    # JavaScript: AWS SDK + DynamoDB
    if any(keyword in lower for keyword in [
        "dynamodb",
        "dynamo",
        "putitem",
        "getitem",
        "updateitem",
        "deleteitem",
        "scan(",
        "query(",
        ".table(",
        "batchwriteitem",
        "batchgetitem",
    ]):
        tags.add("DynamoDB")
    
    # 保留 Database 标签作为通用数据访问层标识
    # 但优先识别 DynamoDB
    if "DynamoDB" not in tags:
        # 检测其他可能的数据库（作为后备）
        if any(keyword in lower for keyword in [
            "sqlite",
            "pymysql",
            "mysql",
            "postgresql",
            "postgres",
            "mongodb",
        ]):
            tags.add("Database")
    
    # 认证相关
    if "jwt" in lower or "jsonwebtoken" in lower:
        tags.add("Auth")
    
    # Cognito 认证检测
    if "cognito" in lower or "cognitoidentityserviceprovider" in lower:
        tags.add("Cognito")
    
    return sorted(tags)


def module_name_from_path(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root)
    return ".".join(rel.with_suffix("").parts)


def analyze_python_file(root: Path, file_path: Path) -> Dict[str, Any]:
    rel_path = str(file_path.relative_to(root).as_posix())
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        source = f.read()

    tags = tag_file(source)
    dependency_targets: Set[str] = set()
    entry_points: List[Dict[str, Any]] = []
    symbol_table: List[Dict[str, Any]] = []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "rel_path": rel_path,
            "tags": tags,
            "dependencies": [],
            "entry_points": [],
            "symbols": [],
        }

    module_name = module_name_from_path(root, file_path)

    class Visitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import) -> None:  # type: ignore[override]
            for alias in node.names:
                dependency_targets.add(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # type: ignore[override]
            if node.module:
                dependency_targets.add(node.module)

        def _record_function(self, func: ast.AST, parent_class: str | None = None) -> None:
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return
            start = getattr(func, "lineno", None)
            end = getattr(func, "end_lineno", start)
            if parent_class:
                symbol_id = f"{module_name}.{parent_class}.{func.name}"
            else:
                symbol_id = f"{module_name}.{func.name}"
            symbol_table.append(
                {
                    "id": symbol_id,
                    "file_path": rel_path,
                    "start_line": start,
                    "end_line": end,
                }
            )

            # Flask / FastAPI style decorators
            for dec in getattr(func, "decorator_list", []):
                if not isinstance(dec, ast.Call):
                    continue
                # app.get("/path") / app.post("/path") / app.route("/path", methods=[...])
                if isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value, ast.Name):
                    attr = dec.func.attr.lower()
                    if attr == "route":
                        http_method = "GET"
                        path = None
                        if dec.args:
                            arg0 = dec.args[0]
                            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                                path = arg0.value
                        for kw in dec.keywords:
                            if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                                for elt in kw.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        http_method = elt.value.upper()
                        if path:
                            entry_points.append(
                                {
                                    "file": rel_path,
                                    "method": http_method,
                                    "path": path,
                                    "handler": func.name,
                                }
                            )
                    elif attr in PY_ENTRY_METHOD_DECORATORS:
                        # FastAPI style: @app.get("/items")
                        path = None
                        if dec.args:
                            arg0 = dec.args[0]
                            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                                path = arg0.value
                        if path:
                            entry_points.append(
                                {
                                    "file": rel_path,
                                    "method": attr.upper(),
                                    "path": path,
                                    "handler": func.name,
                                }
                            )

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # type: ignore[override]
            self._record_function(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # type: ignore[override]
            self._record_function(node)
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # type: ignore[override]
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", start)
            class_id = f"{module_name}.{node.name}"
            symbol_table.append(
                {
                    "id": class_id,
                    "file_path": rel_path,
                    "start_line": start,
                    "end_line": end,
                }
            )
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._record_function(child, parent_class=node.name)
            self.generic_visit(node)

    Visitor().visit(tree)

    return {
        "rel_path": rel_path,
        "tags": tags,
        "dependencies": sorted(dependency_targets),
        "entry_points": entry_points,
        "symbols": symbol_table,
    }


def analyze_js_like_file(root: Path, file_path: Path) -> Dict[str, Any]:
    import re

    rel_path = str(file_path.relative_to(root).as_posix())
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        source = f.read()

    tags = tag_file(source)
    dependency_targets: Set[str] = set()
    entry_points: List[Dict[str, Any]] = []
    symbol_table: List[Dict[str, Any]] = []

    # Dependencies: require()/import
    dep_patterns = [
        re.compile(r"require\(['\"]([^'\"]+)['\"]\)"),
        re.compile(r"from\s+['\"]([^'\"]+)['\"]"),
        re.compile(r"import\s+[^'\"]+['\"]([^'\"]+)['\"]"),
    ]
    for pat in dep_patterns:
        for m in pat.finditer(source):
            dependency_targets.add(m.group(1))

    # Entry points: Express.js app.get/app.post/router.get/...
    route_pattern = re.compile(
        r"\b(app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z0-9_$.]+)",
        re.IGNORECASE,
    )
    for m in route_pattern.finditer(source):
        method = m.group(2).upper()
        path = m.group(3)
        handler = m.group(4)
        entry_points.append(
            {
                "file": rel_path,
                "method": method,
                "path": path,
                "handler": handler,
            }
        )

    # Symbol table (best-effort using regex)
    module_name = module_name_from_path(root, file_path)
    lines = source.splitlines()

    func_decl = re.compile(r"^\s*function\s+([A-Za-z0-9_]+)\s*\(")
    class_decl = re.compile(r"^\s*class\s+([A-Za-z0-9_]+)\b")
    const_func = re.compile(
        r"^\s*(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>)"
    )

    for idx, line in enumerate(lines, start=1):
        m1 = func_decl.search(line)
        m2 = class_decl.search(line)
        m3 = const_func.search(line)
        name = None
        kind = None
        if m1:
            name = m1.group(1)
            kind = "function"
        elif m2:
            name = m2.group(1)
            kind = "class"
        elif m3:
            name = m3.group(1)
            kind = "function"

        if name:
            symbol_id = f"{module_name}.{name}"
            symbol_table.append(
                {
                    "id": symbol_id,
                    "file_path": rel_path,
                    "start_line": idx,
                    "end_line": idx,
                }
            )

    return {
        "rel_path": rel_path,
        "tags": tags,
        "dependencies": sorted(dependency_targets),
        "entry_points": entry_points,
        "symbols": symbol_table,
    }


def analyze_project_config(monolith_root: Path) -> Dict[str, Any]:
    """分析项目依赖配置文件（requirements.txt 和 package.json）"""
    config_info = {}
    
    # 解析 Python requirements.txt
    requirements_file = monolith_root / "requirements.txt"
    if requirements_file.exists():
        with open(requirements_file, 'r', encoding='utf-8') as f:
            requirements = []
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if line and not line.startswith('#'):
                    # 解析依赖: Flask==3.0.0 -> {name: Flask, version: 3.0.0}
                    if '==' in line:
                        name, version = line.split('==', 1)
                        requirements.append({"name": name.strip(), "version": version.strip()})
                    elif '>=' in line:
                        name, version = line.split('>=', 1)
                        requirements.append({"name": name.strip(), "version": f">={version.strip()}"})
                    else:
                        requirements.append({"name": line, "version": None})
            if requirements:
                config_info['python_dependencies'] = requirements
    
    #解析 JavaScript/Node.js package.json
    package_json = monolith_root / "package.json"
    if package_json.exists():
        try:
            with open(package_json, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
                nodejs_info = {}
                
                # 生产依赖
                if 'dependencies' in package_data and package_data['dependencies']:
                    nodejs_info['dependencies'] = [
                        {"name": name, "version": version}
                        for name, version in package_data['dependencies'].items()
                    ]
                
                # 开发依赖
                if 'devDependencies' in package_data and package_data['devDependencies']:
                    nodejs_info['devDependencies'] = [
                        {"name": name, "version": version}
                        for name, version in package_data['devDependencies'].items()
                    ]
                
                if nodejs_info:
                    config_info['nodejs_dependencies'] = nodejs_info
        except (json.JSONDecodeError, KeyError):
            pass  # 忽略解析错误
    
    return config_info


def run_static_analysis(monolith_root: Path) -> Dict[str, Any]:
    project_structure = build_project_structure(monolith_root)
    
    # 分析项目配置（依赖文件）
    config_info = analyze_project_config(monolith_root)
    
    dependency_graph: Dict[str, List[str]] = {}
    file_tags: Dict[str, List[str]] = {}
    entry_points: List[Dict[str, Any]] = []
    symbol_table: List[Dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(monolith_root):
        # 过滤掉需要忽略的目录（修改 dirnames 会影响 os.walk 的遍历）
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith('.')]
        
        for name in filenames:
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in {".py", ".js", ".ts"}:
                continue
            path = Path(dirpath) / name
            if ext == ".py":
                result = analyze_python_file(monolith_root, path)
            else:
                result = analyze_js_like_file(monolith_root, path)

            rel_path = result["rel_path"]
            dependency_graph[rel_path] = result["dependencies"]
            if result["tags"]:
                file_tags[rel_path] = result["tags"]
            entry_points.extend(result["entry_points"])
            symbol_table.extend(result["symbols"])

    result = {
        "project_structure": project_structure,
        "entry_points": entry_points,
        "dependency_graph": dependency_graph,
        "file_tags": file_tags,
        "symbol_table": symbol_table,
    }
    
    # 只在有配置信息时添加
    if config_info:
        result["config_info"] = config_info
    
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="MAG static analyzer")
    parser.add_argument(
        "--monolith-root",
        type=str,
        default=str(DEFAULT_MONOLITH_DIR),
        help="Path to the monolith source root (default: input_monolith)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output path for analysis_report.json",
    )

    args = parser.parse_args()

    monolith_root = Path(args.monolith_root).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not monolith_root.exists():
        raise SystemExit(f"Monolith root not found: {monolith_root}")
    
    report = run_static_analysis(monolith_root)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Static analysis report written to {output_path}")


if __name__ == "__main__":
    main()


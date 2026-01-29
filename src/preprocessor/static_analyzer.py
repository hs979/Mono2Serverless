import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

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
    'coverage'
}

# 前端代码文件扩展名
FRONTEND_EXTENSIONS = {'.js', '.ts', '.jsx', '.tsx', '.vue'}

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


def detect_frontend_characteristics(source: str, file_path: str) -> List[str]:
    """
    检测前端文件特征，判断是否需要修改
    """
    traits = []
    filename = Path(file_path).name.lower()
    
    # 0. 文件名模式检测 - 配置文件优先识别
    if filename in {'config.js', 'config.ts', 'settings.js', 'constants.js', 'env.js'}:
        traits.append("Frontend_Config")
    
    # 1. API 调用检测
    # axios.get, axios.post, fetch(...)
    # $http.get (AngularJS/Vue legacy)
    if re.search(r'\b(axios|fetch|\$http)\.(get|post|put|delete|patch|request)\b', source, re.IGNORECASE):
        traits.append("Frontend_API_Consumer")
    elif re.search(r'\bfetch\s*\(', source):
        traits.append("Frontend_API_Consumer")
    # AWS Amplify API 检测
    elif re.search(r'\bAPI\.(get|post|put|delete|patch|graphql)\b', source):
        traits.append("Frontend_API_Consumer")
    
    # 检测从 aws-amplify 导入 API
    if re.search(r'from [\'"]aws-amplify[\'"]', source) or \
       re.search(r'import .+ from [\'"]aws-amplify', source):
        if re.search(r'\bAPI\b', source):
            if "Frontend_API_Consumer" not in traits:
                traits.append("Frontend_API_Consumer")
    
    # 2. 硬编码路径/URL 检测
    # 匹配 '/api/...' 或 'http://localhost' 或 'http://127.0.0.1'
    if re.search(r"['\"]/api/[^'\"]*['\"]", source) or \
       re.search(r"['\"]https?://(localhost|127\.0\.0\.1)[^'\"]*['\"]", source):
        traits.append("Hardcoded_URL")
        # 不再自动添加 Frontend_API_Consumer

    # 3. 敏感配置/认证检测
    # Amplify, aws-exports, process.env.VUE_APP_API_URL 等
    if re.search(r'\b(Amplify|Auth)\.configure\b', source) or \
       "aws-exports" in source or \
       re.search(r'\bprocess\.env\.', source):
        if "Frontend_Config" not in traits:
            traits.append("Frontend_Config")
    
    # 配置对象检测
    if re.search(r'(?:const|let|var)\s+\w*config\w*\s*=\s*\{', source, re.IGNORECASE):
        if "Frontend_Config" not in traits:
            traits.append("Frontend_Config")

    # 4. 认证集成检测（router 中的认证逻辑）
    # 只标记包含认证相关代码的路由文件，纯路由定义不打标签
    if "router" in filename or re.search(r'\b(Router|Switch|Route)\b', source):
        # 检查是否包含认证相关代码
        if re.search(r'\b(getCurrentUser|currentAuthenticatedUser|signIn|signOut|Auth\.)', source):
            traits.append("Frontend_Auth_Integration")
    
    # 5. Service Worker 特殊处理
    if 'serviceworker' in filename or filename == 'sw.js':
        # Service Worker 不应该有 Frontend_API_Consumer 标签
        traits = [t for t in traits if t != "Frontend_API_Consumer"]
        if "Frontend_Config" not in traits:
            traits.append("Frontend_Config")

    return traits


def tag_file(source: str, file_path: str) -> List[str]:
    tags: Set[str] = set()
    lower = source.lower()
    
    # 前端特征分析
    # 如果文件路径包含 frontend, client, ui, web 等关键词，或者扩展名是前端特有的
    is_frontend_path = any(part in {'frontend', 'client', 'ui', 'web', 'public'} for part in Path(file_path).parts)
    ext = Path(file_path).suffix.lower()
    
    if is_frontend_path or ext in {'.jsx', '.tsx', '.vue'}:
        frontend_traits = detect_frontend_characteristics(source, file_path)
        tags.update(frontend_traits)
        
        # 如果没有任何特殊特征，且是前端代码文件，可能是一个纯 UI 组件
        if not frontend_traits and ext in FRONTEND_EXTENSIONS:
            tags.add("Frontend_UI_Component")
        
        # 前端文件：只返回前端标签，不检测后端标签
        return sorted(tags)

    # 后端/通用特征分析
    
    # AWS SDK 检测
    if "boto3" in lower:
        tags.add("AWS_SDK")
    
    # DynamoDB 数据库检测
    if any(keyword in lower for keyword in [
        "dynamodb", "dynamo", "putitem", "getitem", "updateitem", "deleteitem", 
        ".table(", "batchwriteitem"
    ]):
        tags.add("DynamoDB")
    
    if "DynamoDB" not in tags:
        if any(keyword in lower for keyword in [
            "sqlite", "pymysql", "mysql", "postgresql", "postgres", "mongodb"
        ]):
            tags.add("Database")
    
    # 认证相关
    if "jwt" in lower or "jsonwebtoken" in lower:
        tags.add("Auth")
    
    # Cognito 认证检测
    # if "cognito" in lower or "cognitoidentityserviceprovider" in lower:
        # tags.add("Cognito")
    
    return sorted(tags)


def module_name_from_path(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root)
    return ".".join(rel.with_suffix("").parts)


def analyze_python_file(root: Path, file_path: Path) -> Dict[str, Any]:
    rel_path = str(file_path.relative_to(root).as_posix())
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        source = f.read()

    tags = tag_file(source, rel_path)
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


def _find_function_end_js(lines: List[str], start_idx: int) -> int:
    """
    从start_idx开始，通过括号匹配找到函数结束行
    
    Args:
        lines: 源代码行列表
        start_idx: 函数开始行索引（0-based）
    
    Returns:
        函数结束行号（1-based）
    """
    brace_count = 0
    started = False
    
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        
        # 跳过字符串中的括号（简化处理）
        # 移除单引号和双引号字符串
        line_cleaned = re.sub(r"'[^']*'", "", line)
        line_cleaned = re.sub(r'"[^"]*"', "", line_cleaned)
        line_cleaned = re.sub(r"`[^`]*`", "", line_cleaned)
        
        for char in line_cleaned:
            if char == '{':
                brace_count += 1
                started = True
            elif char == '}':
                brace_count -= 1
                if started and brace_count == 0:
                    return idx + 1  # 返回1-based行号
        
        # 防止无限循环，最多扫描1000行
        if idx - start_idx > 1000:
            break
    
    # 如果没找到结束，返回开始行+1
    return start_idx + 2


def analyze_js_like_file(root: Path, file_path: Path) -> Dict[str, Any]:
    import re

    rel_path = str(file_path.relative_to(root).as_posix())
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        source = f.read()

    tags = tag_file(source, rel_path)
    dependency_targets: Set[str] = set()
    entry_points: List[Dict[str, Any]] = []
    symbol_table: List[Dict[str, Any]] = []
    
    # 判断是否是前端文件
    is_frontend_path = any(part in {'frontend', 'client', 'ui', 'web', 'public', 'src', 'www'} for part in Path(file_path).parts)
    ext = Path(file_path).suffix.lower()
    is_frontend = is_frontend_path or ext in {'.jsx', '.tsx', '.vue'}
    
    # 前端文件判断：如果没有明显的前端特征标签，但路径表明是前端，也认为是前端
    if is_frontend:
        # 前端文件：只需要标签，不需要依赖和符号表
        return {
            "rel_path": rel_path,
            "tags": tags,
            "dependencies": [],
            "entry_points": [],
            "symbols": [],
        }

    # 后端文件：提取依赖
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
        entry_points.append(
            {
                "file": rel_path,
                "method": method,
                "path": path,
            }
        )

    # Symbol table - 增强的JavaScript函数识别
    module_name = module_name_from_path(root, file_path)
    lines = source.splitlines()
    
    # 扩展的函数识别模式
    patterns = {
        # function name() {}
        "function_decl": re.compile(r"^\s*(?:async\s+)?(?:export\s+)?function\s+([A-Za-z0-9_$]+)\s*\("),
        # class Name {}
        "class_decl": re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z0-9_$]+)\b"),
        # const/let/var name = function() {} 或 const name = () => {}
        "const_func": re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>)"
        ),
        # router.get('/path', async (req, res) => {}) - Express路由
        "router_func": re.compile(
            r"^\s*(?:router|app)\.(get|post|put|delete|patch|use)\s*\(\s*['\"]([^'\"]+)['\"]"
        ),
        # exports.name = function() {} 或 module.exports.name = 
        "exports_func": re.compile(
            r"^\s*(?:module\.)?exports\.([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>)"
        ),
        # 对象方法: methodName() {} 或 async methodName() {}
        "object_method": re.compile(
            r"^\s*(?:async\s+)?([A-Za-z0-9_$]+)\s*\([^)]*\)\s*\{"
        ),
        # WebSocket/EventEmitter事件监听器: .on('event', callback)
        # 匹配: wss.on('connection', ...) 或 ws.on('message', ...) 或 process.on('SIGINT', ...)
        "event_listener": re.compile(
            r"^\s*([A-Za-z0-9_$]+)\.on\s*\(\s*['\"]([^'\"]+)['\"]"
        ),
    }

    for idx, line in enumerate(lines, start=1):
        name = None
        kind = "function"
        
        # 尝试匹配各种模式
        if m := patterns["function_decl"].search(line):
            name = m.group(1)
        elif m := patterns["class_decl"].search(line):
            name = m.group(1)
            kind = "class"
        elif m := patterns["const_func"].search(line):
            name = m.group(1)
        elif m := patterns["router_func"].search(line):
            # Express路由：使用 method_path 作为标识
            method = m.group(1).upper()
            path = m.group(2)
            name = f"{method}_{path.replace('/', '_').replace(':', '_')}"
            kind = "route_handler"
        elif m := patterns["event_listener"].search(line):
            # WebSocket/EventEmitter事件监听器
            # 例如: wss.on('connection', ...) -> wss_on_connection
            #      ws.on('message', ...) -> ws_on_message
            obj_name = m.group(1)
            event_name = m.group(2)
            name = f"{obj_name}_on_{event_name}"
            kind = "event_handler"
        elif m := patterns["exports_func"].search(line):
            name = m.group(1)
        elif m := patterns["object_method"].search(line):
            # 对象方法，但要排除if/for等关键字
            potential_name = m.group(1)
            if potential_name not in {'if', 'for', 'while', 'switch', 'catch', 'with'}:
                name = potential_name

        if name:
            # 尝试找到函数结束位置（简单的括号匹配）
            end_line = _find_function_end_js(lines, idx - 1)
            
            symbol_id = f"{module_name}.{name}"
            symbol_table.append(
                {
                    "id": symbol_id,
                    "file_path": rel_path,
                    "start_line": idx,
                    "end_line": end_line,
                    "kind": kind,
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


def _prioritize_schema_files(files: List[str]) -> List[str]:
    """
    根据文件路径优先级筛选最有可能包含表结构定义的文件
    
    优先级：
    - P1 (高): 表结构初始化文件 (init-db, setup-db, create-tables等)
    - P2 (中): 数据库配置和CRUD文件 (db.js/py, database.js/py, models.py等)
    - P3 (低): 业务逻辑文件 (routes/, frontend/, middleware/等) - 忽略
    
    返回最多3个最高优先级的文件
    """
    from pathlib import PurePath
    
    def get_priority(file_path: str) -> int:
        """计算文件优先级，数字越小优先级越高"""
        path = PurePath(file_path)
        filename = path.name.lower()
        parts = [p.lower() for p in path.parts]
        
        # P3 - 低优先级（忽略）：返回99
        ignore_dirs = {'frontend', 'client', 'public', 'routes', 'views', 'controllers', 
                       'middleware', 'components', 'pages', 'src/components', 'src/pages'}
        if any(ignore_dir in parts for ignore_dir in ignore_dirs):
            return 99
        
        # P1 - 高优先级：表结构定义文件
        # init-db, init_dynamodb, setup-db, create-tables等
        p1_patterns = [
            'init-db', 'init_db', 'init_dynamodb', 'initdb',
            'setup-db', 'setup_db', 'setup_dynamodb',
            'create-tables', 'create_tables', 'createtables',
            '_tables.py'  # 如 init_dynamodb_tables.py
        ]
        if any(pattern in filename for pattern in p1_patterns):
            return 1
        
        # P2 - 中优先级：数据库配置和CRUD
        # db.js/py, database.js/py, dynamodb.js/py (不在routes目录)
        p2_filenames = {'db.js', 'db.py', 'database.js', 'database.py', 
                        'dynamodb.js', 'dynamodb.py', 'models.py'}
        p2_allowed_dirs = {'config', 'database', 'utils', 'services', 'app/models', ''}  # '' 表示根目录
        
        if filename in p2_filenames:
            # 检查是否在允许的目录中
            parent_dir = parts[-2] if len(parts) > 1 else ''
            # 允许根目录或特定目录
            if parent_dir in p2_allowed_dirs or len(parts) == 1:
                return 2
            # 也允许 database/ 目录
            if 'database' in parts:
                return 2
        
        # 默认：较低优先级（但不忽略）
        return 50
    
    # 计算每个文件的优先级
    file_priorities = [(f, get_priority(f)) for f in files]
    
    # 过滤掉忽略的文件（priority == 99）
    file_priorities = [(f, p) for f, p in file_priorities if p < 99]
    
    # 按优先级排序
    file_priorities.sort(key=lambda x: (x[1], x[0]))  # 先按优先级，再按文件名
    
    # 返回最多3个最高优先级的文件
    top_files = [f for f, _ in file_priorities[:3]]
    
    return top_files


def extract_dynamodb_info(monolith_root: Path, file_tags: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    提取DynamoDB基本信息（简化版本）：
    1. 是否使用DynamoDB
    2. 可能的表名列表（从环境变量默认值、硬编码字符串提取）
    3. 包含schema定义的文件列表（优先级筛选后的TOP3）
    
    注意：不再尝试提取完整的KeySchema/GSI等复杂结构，
    这些信息应由SAM Engineer在运行时读取schema文件获取。
    """
    info = {
        "used": False,
        "probable_tables": [],
        "schema_files": []
    }
    
    # 找到标记为DynamoDB的文件
    db_files = [f for f, tags in file_tags.items() if "DynamoDB" in tags]
    if not db_files:
        return info
    
    info["used"] = True
    # 优先级筛选：只保留最有可能包含schema的TOP3文件
    info["schema_files"] = _prioritize_schema_files(db_files)
    
    # 提取可能的表名（环境变量默认值、硬编码字符串）
    for rel_file_path in db_files:
        file_path = monolith_root / rel_file_path
        if not file_path.exists():
            continue
            
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            
            # Python模式1：os.environ.get('XXX_TABLE_XXX', 'default-table')
            # 只匹配包含TABLE关键字的环境变量，避免误识别AWS_REGION、SECRET_KEY等
            pattern1 = re.findall(
                r"environ\.get\s*\(\s*['\"]([A-Z_]*TABLE[A-Z_]*)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
                source
            )
            # 提取第二个捕获组（表名）
            info["probable_tables"].extend([m[1] for m in pattern1])
            
            # Python模式2：os.getenv('XXX_TABLE_XXX', 'default-table')
            # 只匹配包含TABLE关键字的环境变量
            pattern2 = re.findall(
                r"getenv\s*\(\s*['\"]([A-Z_]*TABLE[A-Z_]*)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
                source
            )
            # 提取第二个捕获组（表名）
            info["probable_tables"].extend([m[1] for m in pattern2])
            
            # JavaScript模式1：process.env.XXX_TABLE_XXX || 'default-table'
            # 只匹配包含TABLE关键字的环境变量，避免误识别AWS_REGION、NODE_ENV等
            pattern3 = re.findall(
                r"process\.env\.([A-Z_]*TABLE[A-Z_]*)\s*\|\|\s*['\"]([^'\"]+)['\"]",
                source
            )
            # 提取第二个捕获组（表名）
            info["probable_tables"].extend([m[1] for m in pattern3])
            
            # 通用模式：TableName='hardcoded' 或 TableName: 'hardcoded'
            pattern4 = re.findall(
                r"[Tt]ableName\s*[=:]\s*['\"]([^'\"]+)['\"]",
                source
            )
            info["probable_tables"].extend(pattern4)
            
            # JavaScript模式2：配置对象中的表名
            # const tables = { TODO_TABLE: 'todo-table', ... }
            pattern5 = re.findall(
                r"(?:TODO|USER|ORDER|PRODUCT|CART|BOOKING|FLIGHT|LOYALTY)_TABLE\s*:\s*['\"]([^'\"]+)['\"]",
                source,
                re.IGNORECASE
            )
            info["probable_tables"].extend(pattern5)
            
        except Exception as e:
            print(f"Warning: Failed to extract table names from {rel_file_path}: {e}")
            continue
    
    # 去重并排序
    info["probable_tables"] = sorted(list(set(info["probable_tables"])))
    
    return info




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
            
            file_path = Path(dirpath) / name
            ext = file_path.suffix.lower()
            
            # 扩展：支持更多的前端文件类型
            if ext not in {".py", ".js", ".ts", ".jsx", ".tsx", ".vue"}:
                continue
                
            if ext == ".py":
                result = analyze_python_file(monolith_root, file_path)
            else:
                # JS, TS, JSX, TSX, Vue 统一走 JS 分析逻辑（主要靠正则）
                result = analyze_js_like_file(monolith_root, file_path)

            rel_path = result["rel_path"]
            dependency_graph[rel_path] = result["dependencies"]
            if result["tags"]:
                file_tags[rel_path] = result["tags"]
            entry_points.extend(result["entry_points"])
            symbol_table.extend(result["symbols"])
    
    # 提取DynamoDB基本信息（表名列表和schema文件位置）
    dynamodb_info = extract_dynamodb_info(monolith_root, file_tags)

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
    
    # 添加DynamoDB基本信息
    if dynamodb_info["used"]:
        result["dynamodb_info"] = dynamodb_info
    
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

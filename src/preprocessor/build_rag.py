import argparse
import os
import json
from pathlib import Path
from typing import List, Dict, Any

from llama_index.core import Document, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MONOLITH_DIR = ROOT_DIR / "input_monolith"
DEFAULT_INDEX_DIR = ROOT_DIR / "storage" / "code_index"
DEFAULT_ANALYSIS_REPORT = ROOT_DIR / "storage" / "analysis_report.json"

# 从 RAG 索引中排除的文件名黑名单。
# 这些文件通常是入口点或初始化脚本，内容以路由注册、全局配置为主，
# 几乎对所有查询都有一定的词汇覆盖，导致它们长期占据检索排名前列。
# Agent 可以直接用 ReadFileTool 按需读取这些已知文件，无需通过 RAG 检索。
RAG_EXCLUDE_FILENAMES = {
    # Python 入口 / 初始化脚本
    'app.py',           # Flask/FastAPI 入口，主要含路由注册
    'init_dynamodb.py', # DynamoDB 表创建脚本，已被 SAM template 替代
    'init_db.py',
    'create_tables.py',
    'setup_db.py',
    # Node.js 入口 / 初始化脚本
    'server.js',        # Express 应用入口
    'app.js',           # Express 应用入口（备选命名）
    'index.js',         # Node.js 模块入口
    # 配置文件（通常含环境变量读取，与具体业务逻辑无关）
    'config.js',
    'config.py',
    'settings.py',
}


def load_analysis_report(report_path: Path) -> Dict[str, Any]:
    """加载静态分析报告"""
    if not report_path.exists():
        print(f"Warning: Analysis report not found at {report_path}. Using empty report.")
        return {}
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading analysis report: {e}")
        return {}


def extract_code_chunk(source: str, start_line: int, end_line: int) -> str:
    """
    从源代码中提取指定行范围的代码片段
    
    Args:
        source: 完整源代码
        start_line: 起始行号（1-based）
        end_line: 结束行号（1-based）
    
    Returns:
        提取的代码片段
    """
    lines = source.splitlines()
    # start_line 和 end_line 是 1-based，需要转换为 0-based 索引
    chunk_lines = lines[start_line - 1 : end_line]
    return "\n".join(chunk_lines)


SLIDING_WINDOW_LINES = 50    # 每个滑动窗口 chunk 的行数
SLIDING_WINDOW_OVERLAP = 10  # 相邻 chunk 之间的行重叠数


def sliding_window_chunks(source: str, rel_path: str, window: int = SLIDING_WINDOW_LINES,
                           overlap: int = SLIDING_WINDOW_OVERLAP) -> List[Document]:
    """
    对没有函数级别符号的文件应用滑动窗口分片（方案二）。

    将文件按固定行数切成大小均匀的 chunk，避免整文件作为单个 Document
    时因体积过大而在向量检索中压制其他函数级 chunk。

    每个 chunk 的大小控制在 [window - overlap, window] 行之间，
    与函数级 chunk 的平均大小接近，从而使检索得分在同一量级上可比较。
    """
    lines = source.splitlines()
    total = len(lines)
    if total == 0:
        return []

    docs: List[Document] = []
    step = max(1, window - overlap)
    start = 0

    while start < total:
        end = min(start + window, total)
        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines)

        if chunk_text.strip():  # 跳过纯空白 chunk
            docs.append(Document(
                text=chunk_text,
                metadata={
                    "file_path": rel_path,
                    "function_name": "window_chunk",
                    "type": "window",
                    "start_line": start + 1,   # 1-based
                    "end_line": end
                }
            ))

        if end >= total:
            break
        start += step

    return docs


def build_documents(monolith_root: Path, analysis_report: Dict[str, Any]) -> List[Document]:
    """
    遍历源代码，按以下策略构建 RAG 文档（方案二）：

    - 有函数/类级别符号的文件 → 按 symbol_table 分片（函数/类粒度）
    - 无符号的文件（配置文件、简单脚本等）→ 滑动窗口分片

    方案二的核心改进：
    原先无符号文件整文件作为单个 Document，体积远大于函数级 chunk，
    向量空间中"覆盖面"更广，导致几乎任何查询都能命中（排名靠前但不精确）。
    改为滑动窗口后，所有 chunk 大小趋于一致，检索得分可在同一量级上比较。
    """
    docs: List[Document] = []
    symbol_table = analysis_report.get("symbol_table", [])

    # 构建 rel_path -> symbols 的映射
    # 注意：symbol_table 中的 file_path 可能带有 app_name 前缀（见 static_analyzer.py）
    # 因此需要同时支持带前缀和不带前缀两种形式
    file_symbols: Dict[str, List[Dict[str, Any]]] = {}
    for symbol in symbol_table:
        fp = symbol["file_path"]
        if fp not in file_symbols:
            file_symbols[fp] = []
        file_symbols[fp].append(symbol)

    allowed_ext = {".py", ".js", ".ts", ".jsx", ".tsx", ".vue"}

    print(f"Scanning files in {monolith_root}...")
    print(f"Symbol table contains {len(symbol_table)} symbols across {len(file_symbols)} files")
    print(f"Sliding window config: {SLIDING_WINDOW_LINES} lines / {SLIDING_WINDOW_OVERLAP} overlap")

    stats = {
        "total_files": 0,
        "excluded_files": 0,
        "symbol_chunked_files": 0,
        "window_chunked_files": 0,
        "symbol_chunks": 0,
        "window_chunks": 0,
    }

    # 需要忽略的目录（与 static_analyzer.py 保持一致）
    ignore_dirs = {
        'venv', 'env', '.venv', '__pycache__', 'node_modules',
        '.git', '.idea', '.vscode', 'dist', 'build',
        '.pytest_cache', '.mypy_cache', 'htmlcov', '.tox',
        'eggs', '.eggs', 'coverage'
    }

    for dirpath, dirnames, filenames in os.walk(monolith_root):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith('.')]

        for name in filenames:
            if name.startswith("."):
                continue

            file_path = Path(dirpath) / name
            ext = file_path.suffix.lower()

            if ext not in allowed_ext:
                continue

            rel_path = file_path.relative_to(monolith_root).as_posix()

            # 跳过黑名单文件：这些文件属于入口/配置/初始化脚本，
            # 因体积或覆盖面广而容易在检索中产生噪声排名。
            # Agent 可通过 ReadFileTool 直接访问它们。
            if file_path.name in RAG_EXCLUDE_FILENAMES:
                print(f"  [SKIP] {rel_path} (excluded by RAG_EXCLUDE_FILENAMES)")
                stats["excluded_files"] += 1
                continue

            stats["total_files"] += 1

            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            # static_analyzer 给 rel_path 加了 app_name 前缀（e.g., "bookstore/routes/auth.js"）
            # 而 os.walk 得到的 rel_path 没有前缀（e.g., "routes/auth.js"）
            # 需要同时查找两种形式
            app_name = monolith_root.name
            prefixed_rel_path = f"{app_name}/{rel_path}"

            symbols = file_symbols.get(prefixed_rel_path) or file_symbols.get(rel_path) or []

            if symbols:
                # 有符号：按函数/类粒度分片
                for symbol in symbols:
                    chunk_text = extract_code_chunk(source, symbol["start_line"], symbol["end_line"])
                    symbol_id = symbol["id"]
                    function_name = symbol_id.split(".")[-1]

                    docs.append(Document(
                        text=chunk_text,
                        metadata={
                            "file_path": rel_path,
                            "function_name": function_name,
                            "symbol_id": symbol_id,
                            "type": symbol.get("kind", "function"),
                            "start_line": symbol["start_line"],
                            "end_line": symbol["end_line"]
                        }
                    ))
                    stats["symbol_chunks"] += 1

                stats["symbol_chunked_files"] += 1
            else:
                # 无符号：滑动窗口分片（替代整文件索引）
                window_docs = sliding_window_chunks(source, rel_path)
                docs.extend(window_docs)
                stats["window_chunked_files"] += 1
                stats["window_chunks"] += len(window_docs)

    print(f"\n=== Indexing Statistics (Strategy: Symbol + Sliding Window + Blacklist) ===")
    print(f"Files excluded (blacklist)  : {stats['excluded_files']}")
    print(f"Files indexed               : {stats['total_files']}")
    print(f"  - Symbol-level chunked    : {stats['symbol_chunked_files']} files "
          f"→ {stats['symbol_chunks']} chunks")
    print(f"  - Window chunked          : {stats['window_chunked_files']} files "
          f"→ {stats['window_chunks']} chunks  "
          f"(window={SLIDING_WINDOW_LINES}, overlap={SLIDING_WINDOW_OVERLAP})")
    print(f"\nTotal documents indexed     : {len(docs)}")
    print(f"==========================================================================\n")

    return docs


def build_and_persist_index(monolith_root: Path, index_dir: Path, analysis_report: Dict[str, Any]) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)

    documents = build_documents(monolith_root, analysis_report)
    if not documents:
        print(f"No documents found in {monolith_root}")
        return

    print(f"Building index for {len(documents)} code chunks...")
    
    # 使用 CodeBERT 进行 embedding，支持语义搜索
    embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")

    index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
    index.storage_context.persist(persist_dir=str(index_dir))

    print(f"RAG index built successfully! Persisted to {index_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAG index over monolith source code")
    parser.add_argument(
        "--monolith-root",
        type=str,
        default=str(DEFAULT_MONOLITH_DIR),
        help="Monolith root directory",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default=str(DEFAULT_INDEX_DIR),
        help="Directory to persist the vector index",
    )
    parser.add_argument(
        "--analysis-report",
        type=str,
        default=str(DEFAULT_ANALYSIS_REPORT),
        help="Path to static analysis report json",
    )

    args = parser.parse_args()

    monolith_root = Path(args.monolith_root).resolve()
    index_dir = Path(args.index_dir).resolve()
    report_path = Path(args.analysis_report).resolve()

    if not monolith_root.exists():
        raise SystemExit(f"Monolith root not found: {monolith_root}")

    # 加载静态分析报告
    analysis_report = load_analysis_report(report_path)
    
    build_and_persist_index(monolith_root, index_dir, analysis_report)


if __name__ == "__main__":
    main()

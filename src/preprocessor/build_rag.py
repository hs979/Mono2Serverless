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


def build_documents(monolith_root: Path, analysis_report: Dict[str, Any]) -> List[Document]:
    """
    遍历源代码，按策略构建文档：
    
    策略：
    - 所有代码文件统一按后端文件处理
    - 索引方式：按函数/类分片（从 symbol_table 读取）
    - Metadata：包含 file_path, function_name, symbol_id, type, start_line, end_line
    - 特殊情况：没有符号的文件（配置文件等）整文件索引，但保留 metadata
    """
    docs: List[Document] = []
    symbol_table = analysis_report.get("symbol_table", [])
    
    # 构建 file_path -> symbols 的映射
    file_symbols: Dict[str, List[Dict[str, Any]]] = {}
    for symbol in symbol_table:
        file_path = symbol["file_path"]
        if file_path not in file_symbols:
            file_symbols[file_path] = []
        file_symbols[file_path].append(symbol)
    
    # 扩展支持的文件类型
    allowed_ext = {".py", ".js", ".ts", ".jsx", ".tsx", ".vue"}
    
    print(f"Scanning files in {monolith_root}...")
    print(f"Symbol table contains {len(symbol_table)} symbols across {len(file_symbols)} files")
    
    # 统计信息
    stats = {
        "total_files": 0,
        "chunked_files": 0,
        "whole_files": 0,
        "total_chunks": 0
    }
    
    for dirpath, _, filenames in os.walk(monolith_root):
        for name in filenames:
            if name.startswith("."):
                continue
                
            file_path = Path(dirpath) / name
            ext = file_path.suffix.lower()
            
            if ext not in allowed_ext:
                continue
                
            rel_path = file_path.relative_to(monolith_root).as_posix()
            stats["total_files"] += 1
            
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            # 统一处理：按函数/类分片（使用 symbol_table），附带 metadata
            if rel_path in file_symbols and file_symbols[rel_path]:
                # 有符号定义，按函数/类分片
                for symbol in file_symbols[rel_path]:
                    chunk_text = extract_code_chunk(
                        source, 
                        symbol["start_line"], 
                        symbol["end_line"]
                    )
                    
                    # 从 symbol id 提取函数名（格式：module.ClassName.method_name 或 module.function_name）
                    symbol_id = symbol["id"]
                    function_name = symbol_id.split(".")[-1]  # 取最后一部分作为函数名
                    
                    docs.append(Document(
                        text=chunk_text,
                        metadata={
                            "file_path": rel_path,
                            "function_name": function_name,
                            "symbol_id": symbol_id,
                            "type": symbol.get("kind", "function"),  # Python 没有 kind，默认 function
                            "start_line": symbol["start_line"],
                            "end_line": symbol["end_line"]
                        }
                    ))
                    stats["total_chunks"] += 1
                
                stats["chunked_files"] += 1
            else:
                # 没有符号定义，整文件索引（配置文件、简单脚本等）
                docs.append(Document(
                    text=source,
                    metadata={
                        "file_path": rel_path,
                        "function_name": "whole_file",
                        "type": "file",
                        "start_line": 1,
                        "end_line": len(source.splitlines())
                    }
                ))
                stats["whole_files"] += 1
    
    # 打印统计信息
    print(f"\n=== Indexing Statistics ===")
    print(f"Total files scanned: {stats['total_files']}")
    print(f"  - Chunked (function/class level): {stats['chunked_files']} files ({stats['total_chunks']} chunks)")
    print(f"  - Whole file (config/simple scripts): {stats['whole_files']} files")
    print(f"\nTotal documents indexed: {len(docs)}")
    print(f"===========================\n")
    
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

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


def should_index_frontend_file(rel_path: str, file_tags: Dict[str, List[str]]) -> bool:
    """
    判断前端文件是否需要索引
    策略：
    1. 如果在 file_tags 中有记录，且包含 API/Config/Auth 相关标签 -> 索引
    2. 如果没有特殊标签（即纯 UI 组件） -> 不索引
    """
    # 转换为正斜杠路径以匹配 JSON 里的 key
    normalized_path = rel_path.replace("\\", "/")
    
    tags = file_tags.get(normalized_path, [])
    
    # 必须索引的关键特征（已更新标签：Frontend_Router → Frontend_Auth_Integration）
    critical_traits = {
        "Frontend_API_Consumer", 
        "Frontend_Config", 
        "Hardcoded_URL",
        "Frontend_Auth_Integration",  # 原 Frontend_Router，更准确反映认证逻辑
        # "Frontend_GraphQL",           # GraphQL 相关
        # "Frontend_Amplify_Init",      # Amplify 初始化
        # "AWS_Amplify",
        # "Auth"
    }
    
    # 只要包含任何一个关键特征，就需要索引
    if any(trait in tags for trait in critical_traits):
        return True
        
    # 如果明确标记为纯 UI 组件，或者是前端文件但没有任何关键特征，则不索引
    # 这里的逻辑是：只关注那些Agent需要修改逻辑的文件
    return False


def build_documents(monolith_root: Path, analysis_report: Dict[str, Any]) -> List[Document]:
    """
    遍历源代码，按策略构建文档：
    
    策略：
    1. 前端文件（.js/.ts/.jsx/.tsx/.vue in frontend/client/ui/web/public）：
       - 过滤：只索引有关键特征的文件（API/Config/Auth），跳过纯 UI 组件
       - 索引方式：整文件索引
       - Metadata：无（空对象）
    
    2. 后端文件（Python/Node.js）：
       - 索引方式：按函数/类分片（从 symbol_table 读取）
       - Metadata：包含 file_path, function_name, symbol_id, type, start_line, end_line
       - 特殊情况：没有符号的后端文件（配置文件）整文件索引，但保留 metadata
    """
    docs: List[Document] = []
    file_tags = analysis_report.get("file_tags", {})
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
    frontend_ext = {".js", ".ts", ".jsx", ".tsx", ".vue"}
    
    print(f"Scanning files in {monolith_root}...")
    print(f"Symbol table contains {len(symbol_table)} symbols across {len(file_symbols)} files")
    
    # 统计信息
    stats = {
        "total_files": 0,
        "backend_chunked_files": 0,
        "backend_whole_files": 0,
        "frontend_whole_files": 0,
        "skipped_files": 0,
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
            
            # 判断是否为前端文件
            is_frontend = any(part in {'frontend', 'client', 'ui', 'web', 'public'} for part in file_path.parts)
            
            # 前端文件过滤逻辑
            if is_frontend and ext in frontend_ext:
                if not should_index_frontend_file(rel_path, file_tags):
                    # 跳过不需要修改的纯前端文件
                    stats["skipped_files"] += 1
                    continue
            
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            # 策略分叉：前端和后端分开处理
            if is_frontend and ext in frontend_ext:
                # === 前端文件：整文件索引，无 metadata ===
                docs.append(Document(
                    text=source,
                    metadata={}  # 前端文件不附带 metadata
                ))
                stats["frontend_whole_files"] += 1
            else:
                # === 后端文件：按函数/类分片（使用 symbol_table），附带 metadata ===
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
                    
                    stats["backend_chunked_files"] += 1
                else:
                    # 后端文件但没有符号定义，整文件索引（配置文件、简单脚本等）
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
                    stats["backend_whole_files"] += 1
    
    # 打印统计信息
    print(f"\n=== Indexing Statistics ===")
    print(f"Total files scanned: {stats['total_files']}")
    print(f"\nBackend files:")
    print(f"  - Chunked (with metadata): {stats['backend_chunked_files']} ({stats['total_chunks']} chunks)")
    print(f"  - Whole file (with metadata): {stats['backend_whole_files']}")
    print(f"\nFrontend files:")
    print(f"  - Whole file (no metadata): {stats['frontend_whole_files']}")
    print(f"  - Skipped (pure UI): {stats['skipped_files']}")
    print(f"\nTotal documents: {len(docs)}")
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

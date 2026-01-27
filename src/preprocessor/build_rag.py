import argparse
import os
import ast
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Set

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


def get_python_functions(source: str) -> List[Dict[str, Any]]:
    """
    使用 AST 解析 Python 代码，提取函数和类作为分片
    """
    chunks = []
    try:
        tree = ast.parse(source)
        lines = source.splitlines()
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # ast 行号从 1 开始
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", start_line)
                
                # 提取源码片段
                chunk_lines = lines[start_line - 1 : end_line]
                chunk_text = "\n".join(chunk_lines)
                
                node_type = "class" if isinstance(node, ast.ClassDef) else "function"
                
                chunks.append({
                    "name": node.name,
                    "type": node_type,
                    "text": chunk_text,
                    "start_line": start_line,
                    "end_line": end_line
                })
    except SyntaxError:
        pass
    return chunks


def should_index_frontend_file(rel_path: str, file_tags: Dict[str, List[str]]) -> bool:
    """
    判断前端文件是否需要索引
    策略：
    1. 如果在 file_tags 中有记录，且包含 API/Config/Router 相关标签 -> 索引
    2. 如果没有特殊标签（即纯 UI 组件） -> 不索引
    """
    # 转换为正斜杠路径以匹配 JSON 里的 key
    normalized_path = rel_path.replace("\\", "/")
    
    tags = file_tags.get(normalized_path, [])
    
    # 必须索引的关键特征
    critical_traits = {
        "Frontend_API_Consumer", 
        "Frontend_Config", 
        "Hardcoded_URL",
        "Frontend_Router",
        "AWS_Amplify",
        "Auth"
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
    1. Python 后端文件：按函数/类分片 (AST)
    2. 前端文件：经过静态分析筛选后，整文件索引
    """
    docs: List[Document] = []
    file_tags = analysis_report.get("file_tags", {})
    
    # 扩展支持的前端文件
    allowed_ext = {".py", ".js", ".ts", ".jsx", ".tsx", ".vue"}
    frontend_ext = {".js", ".ts", ".jsx", ".tsx", ".vue"}
    
    print(f"Scanning files in {monolith_root}...")
    
    for dirpath, _, filenames in os.walk(monolith_root):
        for name in filenames:
            if name.startswith("."):
                continue
                
            file_path = Path(dirpath) / name
            ext = file_path.suffix.lower()
            
            if ext not in allowed_ext:
                continue
                
            rel_path = file_path.relative_to(monolith_root).as_posix()
            
            # 判断是否为前端文件
            is_frontend = any(part in {'frontend', 'client', 'ui', 'web', 'public'} for part in file_path.parts)
            
            # 前端文件过滤逻辑
            if is_frontend and ext in frontend_ext:
                if not should_index_frontend_file(rel_path, file_tags):
                    # 跳过不需要修改的纯前端文件
                    continue
            
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            chunks = []
            
            # 仅对 Python 后端文件进行函数级分片
            if ext == ".py":
                chunks = get_python_functions(source)
            
            # 策略：如果是 Python 且成功提取到函数，则存函数分片
            if chunks:
                for chunk in chunks:
                    docs.append(Document(
                        text=chunk["text"],
                        metadata={
                            "file_path": rel_path,
                            "function_name": chunk["name"],
                            "type": chunk["type"],
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"]
                        }
                    ))
            else:
                # 兜底策略 / 前端策略：
                # 1. 前端文件直接走这里（整文件索引）
                # 2. 无法识别函数的 Python 脚本走这里
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

import argparse
import os
import ast
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple

from llama_index.core import Document, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MONOLITH_DIR = ROOT_DIR / "input_monolith"
DEFAULT_INDEX_DIR = ROOT_DIR / "storage" / "code_index"


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
                # splitlines 得到的列表索引从 0 开始，所以 start_line - 1
                # end_line 不需要减（切片不包含结束索引），但因为我们要包含最后一行，
                # 且 end_line 是 1-based，所以 lines[start-1 : end] 正好对应
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


def get_js_ts_functions(source: str) -> List[Dict[str, Any]]:
    """
    使用正则和括号匹配启发式提取 JS/TS 函数
    注意：这不是完美的 AST 解析，但在没有引入大型 parser 依赖的情况下够用
    """
    chunks = []
    lines = source.splitlines()
    
    # 匹配常见的函数定义模式
    # 1. function foo() {
    # 2. const foo = () => {
    # 3. const foo = async function() {
    # 4. class Foo {
    patterns = [
        (re.compile(r"function\s+([a-zA-Z0-9_]+)\s*\("), "function"),
        (re.compile(r"(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[a-zA-Z0-9_]+)\s*=>\s*\{"), "function"),
        (re.compile(r"(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?function\s*\("), "function"),
        (re.compile(r"class\s+([a-zA-Z0-9_]+)"), "class")
    ]

    for i, line in enumerate(lines):
        for pattern, node_type in patterns:
            match = pattern.search(line)
            if match:
                # 找到函数/类定义的开始
                name = match.group(1)
                start_line = i + 1
                
                # 简单的括号计数法寻找结束行
                # 从当前行开始往后找
                open_braces = 0
                found_brace = False
                end_line = start_line
                
                for j in range(i, len(lines)):
                    current_line_content = lines[j]
                    open_braces += current_line_content.count('{')
                    open_braces -= current_line_content.count('}')
                    
                    if '{' in current_line_content:
                        found_brace = True
                    
                    if found_brace and open_braces == 0:
                        end_line = j + 1
                        break
                
                # 如果没找到闭合括号（可能是单行箭头函数无括号，或者解析错误），
                # 暂时只取当前行或少量上下文，这里保守策略：如果没闭合，就取到文件末尾或下一段
                # 为简单起见，如果找到闭合才添加
                if found_brace and open_braces == 0:
                    chunk_lines = lines[start_line - 1 : end_line]
                    chunk_text = "\n".join(chunk_lines)
                    
                    chunks.append({
                        "name": name,
                        "type": node_type,
                        "text": chunk_text,
                        "start_line": start_line,
                        "end_line": end_line
                    })
                break # 每一行只匹配一种模式
                
    return chunks


def build_documents(monolith_root: Path) -> List[Document]:
    """
    遍历源代码，按函数/类进行分片构建文档
    """
    docs: List[Document] = []
    
    allowed_ext = {".py", ".js", ".ts", ".jsx", ".tsx"}
    
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
            
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue

            chunks = []
            if ext == ".py":
                chunks = get_python_functions(source)
            elif ext in {".js", ".ts", ".jsx", ".tsx"}:
                chunks = get_js_ts_functions(source)
            
            # 策略：如果有提取到函数/类，就存函数/类
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
                # 兜底策略：如果文件里没提取到任何函数（可能是脚本、配置、或解析失败）
                # 存整个文件，保证代码不丢失
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


def build_and_persist_index(monolith_root: Path, index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)

    documents = build_documents(monolith_root)
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
    parser = argparse.ArgumentParser(description="Build RAG index over monolith source code (Function-Level)")
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

    args = parser.parse_args()

    monolith_root = Path(args.monolith_root).resolve()
    index_dir = Path(args.index_dir).resolve()

    if not monolith_root.exists():
        raise SystemExit(f"Monolith root not found: {monolith_root}")

    build_and_persist_index(monolith_root, index_dir)


if __name__ == "__main__":
    main()

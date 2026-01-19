import argparse
import os
from pathlib import Path
from typing import List

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import CodeSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MONOLITH_DIR = ROOT_DIR / "input_monolith"
DEFAULT_INDEX_DIR = ROOT_DIR / "storage" / "code_index"


def iter_source_files(root: Path) -> List[Path]:
    allowed_ext = {".py", ".js", ".ts"}
    result: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in allowed_ext:
                result.append(Path(dirpath) / name)
    return result


def guess_language(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".py":
        return "python"
    if ext in {".js", ".jsx"}:
        return "javascript"
    if ext in {".ts", ".tsx"}:
        return "typescript"
    return "text"


def build_documents(monolith_root: Path) -> List[Document]:
    """
    构建文档索引，采用智能分层分片策略
    
    策略说明:
    1. 小文件(≤150行): 整文件索引，保持完整上下文
    2. 服务/模型/路由文件(≤600行): 整文件索引，便于理解模块逻辑
    3. 大文件: 按语义单元(函数/类)分片，chunk_lines=200覆盖98%+的函数
    """
    docs: List[Document] = []
    files = iter_source_files(monolith_root)

    for file_path in files:
        rel_path = file_path.relative_to(monolith_root).as_posix()
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            text = f.read()

        line_count = text.count("\n") + 1
        language = guess_language(file_path)

        # 策略1: 小文件 - 整文件索引（保留完整上下文）
        # 根据统计，大部分小文件都在这个范围内
        if line_count <= 150:
            docs.append(Document(
                text=text, 
                metadata={
                    "path": rel_path, 
                    "language": language,
                    "chunk_type": "whole_file",
                    "line_count": line_count
                }
            ))
            continue

        # 策略2: 服务/模型/工具/路由文件 - 整文件索引（即使较大）
        # 这些文件通常需要整体理解，提高阈值到600行
        if any(part in {"services", "models", "utils", "routes", "logic"} for part in file_path.parts):
            if line_count <= 600:
                docs.append(Document(
                    text=text,
                    metadata={
                        "path": rel_path,
                        "language": language,
                        "chunk_type": "whole_file",
                        "line_count": line_count
                    }
                ))
                continue

        # 策略3: 大文件 - 按语义单元（函数/类）分片
        # 使用chunk_lines=200以保持函数完整性（覆盖98%+的函数）
        splitter = CodeSplitter(
            language=language,
            chunk_lines=200,        # 提高到200行，避免切断大部分函数
            chunk_lines_overlap=30, # 保留上下文，帮助理解函数间关系
            max_chars=8000,         # 相应提高字符限制（200行 * 40字符/行）
        )
        nodes = splitter.get_nodes_from_documents(
            [Document(text=text, metadata={
                "path": rel_path, 
                "language": language,
                "chunk_type": "function_level",
                "line_count": line_count
            })]
        )
        
        # 为每个分片节点添加行数信息
        for node in nodes:
            if hasattr(node, 'metadata'):
                node.metadata["original_file_lines"] = line_count
        
        docs.extend(nodes)

    return docs


def build_and_persist_index(monolith_root: Path, index_dir: Path) -> None:
    index_dir.mkdir(parents=True, exist_ok=True)

    documents = build_documents(monolith_root)
    if not documents:
        raise SystemExit(f"No source files found under {monolith_root}")

    embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")

    index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
    index.storage_context.persist(persist_dir=str(index_dir))

    print(f"RAG index built with {len(documents)} nodes and persisted to {index_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAG index over monolith source code")
    parser.add_argument(
        "--monolith-root",
        type=str,
        default=str(DEFAULT_MONOLITH_DIR),
        help="Monolith root directory (default: input_monolith)",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default=str(DEFAULT_INDEX_DIR),
        help="Directory to persist the vector index (default: storage/code_index)",
    )

    args = parser.parse_args()

    monolith_root = Path(args.monolith_root).resolve()
    index_dir = Path(args.index_dir).resolve()

    if not monolith_root.exists():
        raise SystemExit(f"Monolith root not found: {monolith_root}")

    build_and_persist_index(monolith_root, index_dir)


if __name__ == "__main__":
    main()


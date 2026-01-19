from pathlib import Path
from typing import Optional

from llama_index.core import StorageContext, VectorStoreIndex


class CodeRAGTool:
    """Wrapper around a persisted LlamaIndex code index.

    Exposes a simple `.query()` method that agents can call to retrieve
    semantically related code snippets based on the monolith source.
    """

    def __init__(self, index_dir: Optional[Path] = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.index_dir = index_dir or (root / "storage" / "code_index")
        storage_context = StorageContext.from_defaults(persist_dir=str(self.index_dir))
        self.index = VectorStoreIndex.from_storage(storage_context)
        self.query_engine = self.index.as_query_engine()

    def query(self, text: str) -> str:
        response = self.query_engine.query(text)
        return str(response)


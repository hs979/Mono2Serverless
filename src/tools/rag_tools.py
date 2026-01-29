from pathlib import Path
from typing import Optional, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from llama_index.core import StorageContext, load_index_from_storage

class CodeRAGInput(BaseModel):
    """Input schema for CodeRAGTool."""
    query: str = Field(..., description="The search query to find relevant code snippets.")

class CodeRAGTool(BaseTool):
    name: str = "CodeRAGTool"
    description: str = "Search the code knowledge base for semantically relevant code snippets."
    args_schema: Type[BaseModel] = CodeRAGInput
    index_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2] / "storage" / "code_index")
    query_engine: Optional[object] = Field(default=None, exclude=True) # Exclude from serialization

    def __init__(self, index_dir: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        if index_dir:
            self.index_dir = index_dir
        
        # Initialize LlamaIndex
        try:
            if self.index_dir.exists():
                storage_context = StorageContext.from_defaults(persist_dir=str(self.index_dir))
                index = load_index_from_storage(storage_context)
                self.query_engine = index.as_query_engine()
            else:
                print(f"Warning: RAG index directory not found at {self.index_dir}")
        except Exception as e:
            print(f"Error initializing RAG tool: {e}")

    def _run(self, query: str) -> str:
        if not self.query_engine:
            return "Error: RAG tool not initialized correctly or index not found."
        try:
            response = self.query_engine.query(query)
            return str(response)
        except Exception as e:
            return f"Error querying RAG: {str(e)}"

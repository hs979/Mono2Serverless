from pathlib import Path
from typing import Optional, Type
import os
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI

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
            # Explicitly set the embedding model to match build_rag.py
            Settings.embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")
            
            # Configure LLM for LlamaIndex to use DeepSeek/OpenAI from env
            api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            api_key = os.getenv("OPENAI_API_KEY")
            model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-3.5-turbo")
            
            Settings.llm = OpenAI(
                model=model_name,
                api_key=api_key,
                api_base=api_base,
                temperature=0.1
            )

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

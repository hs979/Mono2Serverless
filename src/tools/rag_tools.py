"""
CrewAI Code RAG Tool using Official LlamaIndexTool

This module provides a code retrieval tool that:
- Uses CrewAI's official LlamaIndexTool wrapper
- Returns raw code snippets instead of LLM-synthesized answers
- Avoids "double inference" (tool LLM + agent LLM)
- Saves API costs by letting the agent's LLM do all the reasoning

Architecture:
  User Query → Agent → CodeRAGTool (retriever only) → Raw Code Snippets → Agent LLM → Final Answer
"""

from pathlib import Path
from typing import Optional
from crewai_tools import LlamaIndexTool
from llama_index.core import StorageContext, load_index_from_storage, Settings
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer, ResponseMode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


from llama_index.core.base.response.schema import Response
from llama_index.core.response_synthesizers import BaseSynthesizer

class SimpleCodeFormatter(BaseSynthesizer):
    """
    Custom response synthesizer that formats retrieved code without LLM synthesis.
    
    This synthesizer takes raw retrieval results and formats them into a
    structured, readable format with metadata. No LLM calls are made.
    """
    
    def _get_prompts(self):
        """Return empty prompts (not used in this synthesizer)."""
        return {}
    
    def _update_prompts(self, prompts):
        """Update prompts (not used in this synthesizer)."""
        pass
    
    def synthesize(self, query, nodes, **kwargs) -> Response:
        """
        Format retrieved nodes directly without LLM processing.
        
        Args:
            query: Query bundle or string
            nodes: List of NodeWithScore objects from retriever
        
        Returns:
            Response object with formatted text
        """
        query_str = str(query)
        
        if not nodes:
            return Response(
                response=(
                    f"No relevant code snippets found for: '{query_str}'\n"
                    f"The knowledge base may not contain information about this topic."
                )
            )
        
        # Format results
        results = []
        results.append(f"Found {len(nodes)} relevant code snippet(s):\n")
        results.append("=" * 70)
        
        for i, node_with_score in enumerate(nodes, 1):
            metadata = node_with_score.node.metadata
            
            # Extract metadata
            file_path = metadata.get('file_path', 'unknown')
            function_name = metadata.get('function_name', 'unknown')
            symbol_type = metadata.get('type', 'code')
            start_line = metadata.get('start_line', '?')
            end_line = metadata.get('end_line', '?')
            score = node_with_score.score if hasattr(node_with_score, 'score') else 0.0
            
            # Format each result
            result = [
                f"\n### Code Snippet {i} | Relevance Score: {score:.3f}",
                f"[File] {file_path}",
                f"[Symbol] {function_name} ({symbol_type})",
                f"[Lines] {start_line}-{end_line}",
                f"\n**Code:**",
                f"```",
                node_with_score.node.text.strip(),
                f"```",
                "=" * 70
            ]
            results.append("\n".join(result))
        
        formatted_text = "\n".join(results)
        return Response(response=formatted_text, source_nodes=nodes)
    
    async def asynthesize(self, query, nodes, **kwargs) -> Response:
        """Async version (just calls sync version)."""
        return self.synthesize(query, nodes, **kwargs)
    
    def get_response(self, query_str: str, text_chunks, **kwargs) -> Response:
        """Required by base class but not used in our implementation."""
        raise NotImplementedError("Use synthesize() instead")
    
    async def aget_response(self, query_str: str, text_chunks, **kwargs) -> Response:
        """Required by base class but not used in our implementation."""
        raise NotImplementedError("Use asynthesize() instead")


def create_code_rag_tool(
    index_dir: Optional[Path] = None,
    similarity_top_k: int = 5,
    name: str = "CodeRAGTool",
    description: str = (
        "Search the code knowledge base for semantically relevant code snippets. "
        "Returns raw code with metadata (file path, function name, lines, similarity score). "
        "Use this to find code related to specific functionality, APIs, database operations, "
        "authentication logic, routes, or any technical implementation details."
    )
) -> LlamaIndexTool:
    """
    Factory function to create a Code RAG Tool using CrewAI's official LlamaIndexTool.
    
    This tool uses a retriever (not query_engine) wrapped with custom formatting.
    It returns raw code snippets without LLM synthesis, avoiding double inference costs.
    
    Args:
        index_dir: Path to the persisted vector index. Defaults to storage/code_index.
        similarity_top_k: Number of most similar code chunks to retrieve. Default: 5.
        name: Tool name visible to the agent.
        description: Tool description for the agent to understand when to use it.
    
    Returns:
        LlamaIndexTool instance ready to use with CrewAI agents.
    
    Raises:
        FileNotFoundError: If index_dir doesn't exist.
        Exception: If index loading or retriever creation fails.
    
    Example:
        >>> from src.tools.rag_tools import create_code_rag_tool
        >>> tool = create_code_rag_tool(similarity_top_k=3)
        >>> # Use in CrewAI agent
        >>> agent = Agent(
        ...     role="Code Analyst",
        ...     tools=[tool],
        ...     ...
        ... )
    """
    # Set default index directory
    if index_dir is None:
        index_dir = Path(__file__).resolve().parents[2] / "storage" / "code_index"
    
    if not index_dir.exists():
        raise FileNotFoundError(
            f"RAG index directory not found at {index_dir}\n"
            f"Please run build_rag.py first to create the index:\n"
            f"  python src/preprocessor/build_rag.py"
        )
    
    # Configure embedding model (must match build_rag.py)
    # CRITICAL: We do NOT set Settings.llm here - no LLM needed for retrieval!
    print(f"Loading code index from: {index_dir}")
    Settings.embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")
    
    # Load the persisted index
    storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
    index = load_index_from_storage(storage_context)
    
    # Create retriever (NOT a full query engine with LLM)
    # Retriever returns raw NodeWithScore objects without LLM synthesis
    retriever = index.as_retriever(similarity_top_k=similarity_top_k)
    
    # Create a custom response synthesizer that just formats (no LLM)
    response_synthesizer = SimpleCodeFormatter()
    
    # Create query engine with retriever + custom formatter (no LLM needed!)
    query_engine = RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=response_synthesizer
    )
    
    # Use CrewAI's official LlamaIndexTool wrapper
    # This ensures full compatibility with CrewAI's tool calling mechanism
    tool = LlamaIndexTool.from_query_engine(
        query_engine=query_engine,
        name=name,
        description=description,
        return_direct=False  # Let agent process the results
    )
    
    print(f"[OK] CodeRAGTool created successfully!")
    print(f"  - Using official LlamaIndexTool wrapper")
    print(f"  - Retriever mode (no LLM synthesis)")
    print(f"  - Retrieving top {similarity_top_k} results per query")
    
    return tool


# Backward compatibility: expose both factory function and direct usage
CodeRAGTool = create_code_rag_tool  # Allow: tool = CodeRAGTool(...)

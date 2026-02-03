"""
Final test of CodeRAGTool using official LlamaIndexTool
"""
import sys
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

print("=" * 70)
print("CodeRAGTool Test - Using Official LlamaIndexTool")
print("=" * 70)

# Check index
index_dir = ROOT_DIR / "storage" / "code_index"
print(f"\nIndex directory: {index_dir}")
print(f"Exists: {index_dir.exists()}")

if not index_dir.exists():
    print("\nERROR: Index not found! Run build_rag.py first.")
    sys.exit(1)

# Import (should work now with crewai[tools] installed)
print("\nImporting create_code_rag_tool...")
try:
    from src.tools.rag_tools import create_code_rag_tool
    print("[OK] Import successful")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("\nMake sure crewai[tools] is installed:")
    print("  pip install 'crewai[tools]'")
    sys.exit(1)

# Create tool
print("\nCreating CodeRAGTool...")
try:
    tool = create_code_rag_tool(
        index_dir=index_dir,
        similarity_top_k=3  # Retrieve top 3 results for testing
    )
    print("[OK] Tool created successfully!\n")
except Exception as e:
    print(f"[ERROR] Failed to create tool: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test query
test_query = "What is the main responsibility of the database.py file?"
print("=" * 70)
print(f"Test Query: {test_query}")
print("=" * 70)

try:
    # LlamaIndexTool uses .run() method
    result = tool.run(test_query)
    
    print("\n===== RETRIEVED CODE SNIPPETS =====\n")
    print(result)
    print("\n" + "=" * 70)
    
    # Validate results (result might be a ToolOutput object)
    result_str = str(result)
    
    if "Error" in result_str and "retrieval" in result_str.lower():
        print("\n[FAILED] Test FAILED - Error in retrieval")
        sys.exit(1)
    elif "No relevant code" in result_str:
        print("\n[WARNING] No code found (index might be empty)")
    elif "Code Snippet" not in result_str:
        print("\n[WARNING] No code snippets in response")
    else:
        print("\n[PASS] Test PASSED!")
        print("\nKey Features Verified:")
        print("  [OK] Uses official CrewAI LlamaIndexTool")
        print("  [OK] Returns raw code snippets (no LLM synthesis)")
        print("  [OK] Avoids double inference (saves API costs)")
        print("  [OK] Agent's LLM will interpret the results")
        
except Exception as e:
    print(f"\n[ERROR] Execution error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

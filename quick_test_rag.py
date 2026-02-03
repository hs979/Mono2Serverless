import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 1. 设置路径和环境变量
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR))
load_dotenv(ROOT_DIR / ".env")

def test_rag_standalone():
    print(f"\n{'='*50}")
    print("Quick Test: CodeRAGTool Standalone Verification")
    print(f"{'='*50}")

    # 2. 检查索引路径
    index_dir = ROOT_DIR / "storage" / "code_index"
    print(f"Checking index directory: {index_dir}")
    if not index_dir.exists():
        print(f"Error: Index directory does not exist at {index_dir}")
        print("Please ensure you have prepared the 'storage/code_index' directory as stated.")
        return

    # 3. 导入并创建工具
    try:
        print("Importing create_code_rag_tool...")
        from src.tools.rag_tools import create_code_rag_tool
        
        print("Creating CodeRAGTool (loading index)...")
        tool = create_code_rag_tool(
            index_dir=index_dir,
            similarity_top_k=3  # 测试时只检索3个结果
        )
        
        print("✓ CodeRAGTool created successfully!")

    except ImportError as e:
        print(f"✗ ImportError: {e}")
        print("Ensure 'src' directory is in PYTHONPATH.")
        return
    except FileNotFoundError as e:
        print(f"✗ {e}")
        return
    except Exception as e:
        print(f"✗ Initialization Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # 4. 执行测试查询
    test_query = "What is the main responsibility of the database.py file?"
    print(f"\n{'='*60}")
    print(f"Test Query: '{test_query}'")
    print('='*60)
    
    try:
        # BaseTool 使用 _run() 方法
        result = tool._run(test_query)
        
        print(f"\n📋 Retrieved Code Snippets:\n")
        print(result)
        print(f"\n{'='*60}")
        
        # 验证结果
        if "Error" in result:
            print("\n✗ Test Failed: Tool reported an error.")
        elif "No relevant code" in result:
            print("\n⚠️  Warning: No relevant code found (index might be empty).")
        elif len(result) < 50:
            print("\n⚠️  Warning: Response seems too short.")
        else:
            print("\n✓ Test Passed: CodeRAGTool is working correctly!")
            print("  - Tool returns raw code snippets (no LLM synthesis)")
            print("  - Agent's LLM will interpret these results")
             
    except Exception as e:
        print(f"\n✗ Execution Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rag_standalone()

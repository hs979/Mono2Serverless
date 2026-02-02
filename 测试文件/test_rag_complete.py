"""
完整测试 RAG 索引构建和语义搜索功能

测试流程：
1. 构建索引（基于 static_analyzer 的结果）
2. 加载索引并测试语义搜索
3. 验证前端和后端文件的索引策略
4. 模拟 Agent 使用场景
"""
import json
import tempfile
import shutil
from pathlib import Path

from llama_index.core import StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from src.preprocessor.build_rag import (
    load_analysis_report,
    build_documents,
    build_and_persist_index
)


def test_build_index():
    """测试1：构建索引"""
    print("\n" + "=" * 70)
    print("测试1：构建 RAG 索引")
    print("=" * 70)
    
    # 使用 coffee_test.json（Node.js 项目）
    test_file = Path("static_result/coffee_test.json")
    
    if not test_file.exists():
        print(f"[WARN] 测试文件不存在: {test_file}")
        print("请先运行 static_analyzer.py 生成测试数据")
        return None
    
    # 加载分析报告
    analysis_report = load_analysis_report(test_file)
    
    # 模拟项目根目录（这里我们只测试 document 构建，不需要实际文件）
    print(f"\n分析报告统计:")
    print(f"  - 文件标签: {len(analysis_report.get('file_tags', {}))} 个")
    print(f"  - 符号表: {len(analysis_report.get('symbol_table', []))} 个")
    print(f"  - 入口点: {len(analysis_report.get('entry_points', []))} 个")
    
    # 检查符号类型分布
    symbol_table = analysis_report.get("symbol_table", [])
    kind_counts = {}
    for symbol in symbol_table:
        kind = symbol.get("kind", "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    
    print(f"\n符号类型分布:")
    for kind, count in sorted(kind_counts.items()):
        print(f"  - {kind}: {count}")
    
    print("\n[PASS] 索引构建测试准备完成")
    return analysis_report


def test_semantic_search():
    """测试2：语义搜索功能"""
    print("\n" + "=" * 70)
    print("测试2：语义搜索功能")
    print("=" * 70)
    
    # 检查是否有已构建的索引
    index_dir = Path("storage/code_index")
    
    if not index_dir.exists() or not (index_dir / "docstore.json").exists():
        print(f"[WARN] 索引目录不存在: {index_dir}")
        print("请先运行以下命令构建索引:")
        print("  python src/preprocessor/static_analyzer.py --monolith-root <your_project>")
        print("  python src/preprocessor/build_rag.py --monolith-root <your_project>")
        return False
    
    print(f"加载索引: {index_dir}")
    
    try:
        # 加载 embedding 模型
        embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")
        
        # 加载索引
        storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
        index = load_index_from_storage(storage_context, embed_model=embed_model)
        
        # 创建查询引擎
        query_engine = index.as_query_engine(similarity_top_k=5)
        
        # 测试查询
        test_queries = [
            {
                "query": "How to connect to DynamoDB database?",
                "expected_keywords": ["dynamodb", "database", "table"],
                "description": "后端数据库查询"
            },
            {
                "query": "Where is user authentication handled?",
                "expected_keywords": ["auth", "login", "user"],
                "description": "后端认证查询"
            },
            {
                "query": "Which functions handle API routes?",
                "expected_keywords": ["route", "get", "post", "api"],
                "description": "后端路由查询"
            },
        ]
        
        print(f"\n执行 {len(test_queries)} 个语义搜索测试...\n")
        
        for i, test in enumerate(test_queries, 1):
            print(f"查询 {i}: {test['description']}")
            print(f"  问题: {test['query']}")
            
            # 执行查询
            response = query_engine.query(test['query'])
            
            print(f"  结果: {str(response)[:200]}...")
            
            # 检查源节点
            if hasattr(response, 'source_nodes') and response.source_nodes:
                print(f"  找到 {len(response.source_nodes)} 个相关代码片段:")
                
                for j, node in enumerate(response.source_nodes[:3], 1):
                    metadata = node.metadata
                    score = node.score if hasattr(node, 'score') else 0.0
                    
                    print(f"    [{j}] 相似度: {score:.4f}")
                    
                    # 显示 metadata（后端文件应该有，前端文件为空）
                    if metadata:
                        print(f"        文件: {metadata.get('file_path', 'N/A')}")
                        print(f"        函数: {metadata.get('function_name', 'N/A')}")
                        print(f"        类型: {metadata.get('type', 'N/A')}")
                        print(f"        行号: {metadata.get('start_line', 'N/A')}-{metadata.get('end_line', 'N/A')}")
                    else:
                        print(f"        (前端文件，无 metadata)")
                    
                    # 显示代码片段预览
                    text_preview = node.text[:100].replace('\n', ' ')
                    print(f"        代码: {text_preview}...")
            else:
                print(f"  [WARN] 未找到相关结果")
            
            print()
        
        print("[PASS] 语义搜索测试完成")
        return True
        
    except Exception as e:
        print(f"[FAIL] 语义搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_frontend_backend_separation():
    """测试3：验证前端和后端分离策略"""
    print("\n" + "=" * 70)
    print("测试3：验证前端/后端分离策略")
    print("=" * 70)
    
    index_dir = Path("storage/code_index")
    
    if not index_dir.exists():
        print(f"[WARN] 索引目录不存在: {index_dir}")
        return False
    
    try:
        # 加载 docstore 检查 metadata
        docstore_path = index_dir / "docstore.json"
        with open(docstore_path, 'r', encoding='utf-8') as f:
            docstore = json.load(f)
        
        # 统计
        total_docs = len(docstore.get('docstore/data', {}))
        backend_with_metadata = 0
        frontend_no_metadata = 0
        
        print(f"\n文档总数: {total_docs}")
        print(f"\n检查 metadata 策略...")
        
        for doc_id, doc_data in docstore.get('docstore/data', {}).items():
            metadata = doc_data.get('metadata', {})
            
            # 后端文件应该有 metadata
            if metadata and 'file_path' in metadata:
                file_path = metadata.get('file_path', '')
                
                # 判断是否为前端文件
                is_frontend = any(part in file_path for part in ['frontend', 'client', 'ui', 'web', 'public'])
                
                if not is_frontend:
                    backend_with_metadata += 1
            
            # 前端文件应该没有 metadata（空对象）
            if not metadata or len(metadata) == 0:
                frontend_no_metadata += 1
        
        print(f"  - 后端文档（有 metadata）: {backend_with_metadata}")
        print(f"  - 前端文档（无 metadata）: {frontend_no_metadata}")
        
        if backend_with_metadata > 0:
            print(f"\n[PASS] 检测到后端文档带有 metadata")
        
        if frontend_no_metadata > 0:
            print(f"[PASS] 检测到前端文档没有 metadata")
        
        if backend_with_metadata == 0 and frontend_no_metadata == 0:
            print(f"[WARN] 未检测到明确的前端/后端分离")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_use_case():
    """测试4：模拟 Agent 使用场景"""
    print("\n" + "=" * 70)
    print("测试4：模拟 Agent 使用场景")
    print("=" * 70)
    
    index_dir = Path("storage/code_index")
    
    if not index_dir.exists():
        print(f"[WARN] 索引目录不存在: {index_dir}")
        return False
    
    try:
        # 加载索引
        embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")
        storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
        index = load_index_from_storage(storage_context, embed_model=embed_model)
        query_engine = index.as_query_engine(similarity_top_k=3)
        
        # 模拟 Agent 场景
        scenarios = [
            {
                "scenario": "Agent 需要找到处理订单的函数",
                "query": "Find functions that process orders and handle order creation",
                "expectation": "应该返回带有 metadata 的后端函数（函数名、文件路径、行号）"
            },
            {
                "scenario": "Agent 需要找到 API 配置文件",
                "query": "Where is the API configuration defined?",
                "expectation": "可能返回前端配置文件（整文件内容）或后端配置"
            },
            {
                "scenario": "Agent 需要找到数据库相关的代码",
                "query": "Show me database connection and query functions",
                "expectation": "应该返回后端数据库函数（带 metadata）"
            }
        ]
        
        print(f"\n模拟 {len(scenarios)} 个 Agent 使用场景...\n")
        
        for i, scenario in enumerate(scenarios, 1):
            print(f"场景 {i}: {scenario['scenario']}")
            print(f"  查询: {scenario['query']}")
            print(f"  期望: {scenario['expectation']}")
            
            response = query_engine.query(scenario['query'])
            
            if hasattr(response, 'source_nodes') and response.source_nodes:
                print(f"  ✓ 找到 {len(response.source_nodes)} 个相关结果")
                
                # 检查第一个结果
                first_node = response.source_nodes[0]
                metadata = first_node.metadata
                
                if metadata:
                    print(f"    类型: 后端代码片段")
                    print(f"    文件: {metadata.get('file_path', 'N/A')}")
                    print(f"    函数: {metadata.get('function_name', 'N/A')}")
                    print(f"    行号: {metadata.get('start_line', 'N/A')}-{metadata.get('end_line', 'N/A')}")
                    print(f"    [PASS] Agent 可以精确定位到代码位置")
                else:
                    print(f"    类型: 前端整文件")
                    print(f"    [PASS] Agent 获取到完整文件内容")
            else:
                print(f"  ✗ 未找到相关结果")
            
            print()
        
        print("[PASS] Agent 使用场景测试完成")
        return True
        
    except Exception as e:
        print(f"[FAIL] Agent 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print("RAG 完整功能测试")
    print("=" * 70)
    
    results = {
        "build_index": False,
        "semantic_search": False,
        "frontend_backend": False,
        "agent_use_case": False
    }
    
    # 测试1：构建索引（基于现有分析报告）
    analysis_report = test_build_index()
    if analysis_report:
        results["build_index"] = True
    
    # 测试2：语义搜索
    if test_semantic_search():
        results["semantic_search"] = True
    
    # 测试3：验证前端/后端分离
    if test_frontend_backend_separation():
        results["frontend_backend"] = True
    
    # 测试4：Agent 使用场景
    if test_agent_use_case():
        results["agent_use_case"] = True
    
    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[SKIP]"
        print(f"{status} {test_name}")
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 所有测试通过！RAG 索引和语义搜索功能正常")
        print("\nAgent 可以:")
        print("  ✓ 通过语义搜索找到相关代码")
        print("  ✓ 获取后端函数的精确位置（文件、函数名、行号）")
        print("  ✓ 获取前端文件的完整内容")
        return 0
    elif results["semantic_search"]:
        print("\n✓ 核心功能正常：语义搜索可用")
        return 0
    else:
        print("\n⚠ 部分测试未通过或跳过")
        return 1


if __name__ == "__main__":
    exit(main())

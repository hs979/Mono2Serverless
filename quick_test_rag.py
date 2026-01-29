"""
快速测试 RAG 功能（纯本地模式）

用法：
    python quick_test_rag.py [查询内容]

示例：
    python quick_test_rag.py "How to connect to database?"
    python quick_test_rag.py "Find user authentication code"
"""
import sys
from pathlib import Path
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def quick_test(query: str = None):
    """快速测试 RAG 语义搜索（纯本地模式）"""
    
    # 默认查询
    if not query:
        query = "How to connect to DynamoDB database?"
    
    # 检查索引
    index_dir = Path("storage/fp_code_index")
    if not index_dir.exists() or not (index_dir / "docstore.json").exists():
        print("❌ 错误：索引不存在")
        print("\n请先运行以下命令构建索引:")
        print("  1. python src/preprocessor/static_analyzer.py --monolith-root <your_project>")
        print("  2. python src/preprocessor/build_rag.py --monolith-root <your_project>")
        return False
    
    print("=" * 70)
    print("🔍 RAG 语义搜索测试（纯本地模式）")
    print("=" * 70)
    print(f"\n📝 查询: {query}\n")
    
    try:
        # 加载索引
        print("⏳ 加载索引和CodeBERT模型...")
        embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")
        storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
        index = load_index_from_storage(storage_context, embed_model=embed_model)
        
        # 使用纯检索模式，不调用LLM生成回答
        print("🔎 执行语义搜索...\n")
        retriever = index.as_retriever(similarity_top_k=5)
        nodes = retriever.retrieve(query)
        
        if not nodes:
            print("⚠️ 未找到相关结果")
            print("   建议：")
            print("   - 尝试更具体的查询")
            print("   - 检查索引是否正确构建")
            return False
        
        # 显示搜索结果
        print("=" * 70)
        print("📊 搜索结果（纯检索模式）")
        print("=" * 70)
        print(f"\n✅ 找到 {len(nodes)} 个相关代码片段")
        
        # 显示源代码
        print("=" * 70)
        print(f"📂 相关代码片段 (共 {len(nodes)} 个)")
        print("=" * 70)
        
        backend_count = 0
        frontend_count = 0
        
        for i, node in enumerate(nodes, 1):
            print(f"\n[{i}] 相似度: {node.score:.4f}")
            
            metadata = node.metadata
            
            if metadata and 'file_path' in metadata:
                # 后端代码（有 metadata）
                backend_count += 1
                print(f"  📁 文件: {metadata.get('file_path', 'N/A')}")
                
                if 'function_name' in metadata and metadata['function_name']:
                    print(f"  🔧 函数: {metadata.get('function_name', 'N/A')}")
                
                if 'type' in metadata:
                    print(f"  📌 类型: {metadata.get('type', 'N/A')}")
                
                if 'start_line' in metadata and 'end_line' in metadata:
                    print(f"  📍 行号: {metadata.get('start_line', 'N/A')}-{metadata.get('end_line', 'N/A')}")
                
                # 显示代码片段
                code_lines = node.text.strip().split('\n')
                print(f"  📝 代码预览 ({len(code_lines)} 行):")
                
                # 显示前8行代码
                for j, line in enumerate(code_lines[:8], 1):
                    line_num = metadata.get('start_line', 0) + j - 1 if 'start_line' in metadata else j
                    print(f"      {line_num:4d} | {line}")
                
                if len(code_lines) > 8:
                    print(f"      ... (省略 {len(code_lines) - 8} 行)")
            else:
                # 前端代码或无metadata的代码
                frontend_count += 1
                print(f"  📄 类型: 前端文件或未标记文件")
                
                # 尝试从文本中提取文件名
                lines = node.text.split('\n')
                file_path_hint = ""
                for line in lines[:5]:
                    if line.startswith('File:') or line.startswith('Path:'):
                        file_path_hint = line
                        break
                
                if file_path_hint:
                    print(f"  📁 {file_path_hint}")
                else:
                    print(f"  📁 文件: 未在元数据中指定")
                
                # 显示内容预览
                print(f"  📝 内容预览:")
                text_lines = lines[:10]
                for line in text_lines:
                    print(f"      {line}")
                if len(lines) > 10:
                    print(f"      ... (省略 {len(lines) - 10} 行)")
            
            print("-" * 60)
        
        print("\n" + "=" * 70)
        print("✅ 搜索完成")
        print("=" * 70)
        
        # 验证摘要
        print("\n📋 验证摘要:")
        print(f"  ✓ 后端代码片段: {backend_count} 个（有详细元数据）")
        print(f"  ✓ 前端/无标记代码: {frontend_count} 个（完整文件上下文）")
        
        if backend_count > 0:
            print(f"  ✓ 后端代码能精确定位（文件、函数、行号）")
        
        if frontend_count > 0:
            print(f"  ✓ 前端代码提供完整上下文")
        
        # 提供使用建议
        print("\n💡 使用建议:")
        print("  1. 对于后端代码，可以根据文件路径和行号直接定位")
        print("  2. 对于前端代码，建议查看完整文件以理解上下文")
        print("  3. 相似度 > 0.7 的结果通常更相关")
        print("  4. 在MAG系统中，Coding Agent将结合文件映射表和RAG搜索结果")
        
        # 显示一些示例查询
        print("\n🔍 其他可能的查询示例:")
        print("  - 'authentication logic'")
        print("  - 'database query function'") 
        print("  - 'API endpoint definition'")
        print("  - 'config or environment variable usage'")
        print("  - 'error handling code'")
        
        print(f"\n🎉 RAG 检索功能正常！")
        return True
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    # 获取命令行参数
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        # 显示使用说明
        print("=" * 70)
        print("🔍 RAG 语义搜索测试工具（纯本地模式）")
        print("=" * 70)
        print("\n💡 用法:")
        print("   1. 指定查询内容: python quick_test_rag.py \"your query here\"")
        print("   2. 使用默认查询: python quick_test_rag.py")
        print("\n📝 示例查询:")
        print("   - 'Find database connection code'")
        print("   - 'User authentication logic'")
        print("   - 'API endpoint definitions'")
        print("   - 'Configuration settings'")
        print()
        
        # 使用默认查询
        query = None
    
    success = quick_test(query)
    
    if not success:
        print("\n" + "=" * 70)
        print("📚 更多测试选项:")
        print("=" * 70)
        print("  1. 完整测试: python test_rag_complete.py")
        print("  2. 单元测试: python test_build_rag.py")
        print("  3. 查看指南: cat TEST_RAG_GUIDE.md")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
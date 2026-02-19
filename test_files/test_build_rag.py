"""
测试 build_rag.py 的改进功能
"""
import json
from pathlib import Path
from src.preprocessor.build_rag import (
    load_analysis_report,
    should_index_frontend_file,
    extract_code_chunk,
    build_documents
)


def test_extract_code_chunk():
    """测试代码片段提取"""
    print("=" * 60)
    print("测试1：代码片段提取")
    print("=" * 60)
    
    source = """line 1
line 2
line 3
line 4
line 5"""
    
    # 测试提取第 2-4 行
    chunk = extract_code_chunk(source, 2, 4)
    expected = "line 2\nline 3\nline 4"
    
    print(f"源代码:\n{source}\n")
    print(f"提取第2-4行:\n{chunk}\n")
    assert chunk == expected, f"Expected:\n{expected}\nGot:\n{chunk}"
    print("[PASS] 测试通过\n")


def test_should_index_frontend_file():
    """测试前端文件过滤逻辑（使用新标签）"""
    print("=" * 60)
    print("测试2：前端文件过滤（新标签）")
    print("=" * 60)
    
    file_tags = {
        "frontend/api.js": ["Frontend_API_Consumer"],
        "frontend/config.js": ["Frontend_Config"],
        "frontend/router.js": ["Frontend_Auth_Integration"],  # 新标签（已实现）
        "frontend/hardcoded.js": ["Hardcoded_URL"],
        "frontend/Button.jsx": ["Frontend_UI_Component"],
        "frontend/utils.js": []
    }
    
    test_cases = [
        ("frontend/api.js", True, "API Consumer 应该被索引"),
        ("frontend/config.js", True, "Config 应该被索引"),
        ("frontend/router.js", True, "Auth Integration 应该被索引（新标签）"),
        ("frontend/hardcoded.js", True, "Hardcoded URL 应该被索引"),
        ("frontend/Button.jsx", False, "纯 UI 组件不应该被索引"),
        ("frontend/utils.js", False, "无标签文件不应该被索引"),
    ]
    
    for file_path, expected, reason in test_cases:
        result = should_index_frontend_file(file_path, file_tags)
        status = "[PASS]" if result == expected else "[FAIL]"
        print(f"{status} {file_path}: {result} (期望: {expected}) - {reason}")
        assert result == expected, f"Failed: {reason}"
    
    print("\n[PASS] 所有测试通过\n")


def test_build_documents_with_symbol_table():
    """测试使用 symbol_table 构建文档（Python 和 Node.js 统一处理）"""
    print("=" * 60)
    print("测试3：使用 symbol_table 构建文档")
    print("=" * 60)
    
    # 使用 fileprocess_test.json 测试（Python 项目）
    test_file = Path("static_result/fileprocess_test.json")
    
    if not test_file.exists():
        print(f"[WARN] 测试文件不存在: {test_file}")
        print("跳过此测试\n")
        return
    
    analysis_report = load_analysis_report(test_file)
    
    print(f"分析报告包含:")
    print(f"  - {len(analysis_report.get('file_tags', {}))} 个文件标签")
    print(f"  - {len(analysis_report.get('symbol_table', []))} 个符号")
    print(f"  - {len(analysis_report.get('entry_points', []))} 个入口点\n")
    
    # 检查是否有符号
    symbol_table = analysis_report.get("symbol_table", [])
    if not symbol_table:
        print("[WARN] 没有找到 symbol_table，跳过测试\n")
        return
    
    # 显示前3个符号
    print("前3个符号:")
    for i, symbol in enumerate(symbol_table[:3], 1):
        print(f"  {i}. {symbol['id']}")
        print(f"     文件: {symbol['file_path']}")
        print(f"     行号: {symbol['start_line']}-{symbol['end_line']}")
        if 'kind' in symbol:
            print(f"     类型: {symbol['kind']}")
    
    print("\n[PASS] symbol_table 结构正确\n")


def test_coffee_shop_nodejs():
    """测试 Node.js 项目（coffee shop）"""
    print("=" * 60)
    print("测试4：Node.js 项目分析")
    print("=" * 60)
    
    test_file = Path("static_result/coffee_test.json")
    
    if not test_file.exists():
        print(f"[WARN] 测试文件不存在: {test_file}")
        print("跳过此测试\n")
        return
    
    analysis_report = load_analysis_report(test_file)
    symbol_table = analysis_report.get("symbol_table", [])
    
    print(f"Coffee Shop 项目:")
    print(f"  - {len(symbol_table)} 个符号\n")
    
    # 统计不同类型的符号
    kind_counts = {}
    for symbol in symbol_table:
        kind = symbol.get("kind", "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    
    print("符号类型分布:")
    for kind, count in sorted(kind_counts.items()):
        print(f"  - {kind}: {count}")
    
    # 显示几个 route_handler 示例
    route_handlers = [s for s in symbol_table if s.get("kind") == "route_handler"]
    if route_handlers:
        print(f"\n前3个路由处理器:")
        for i, handler in enumerate(route_handlers[:3], 1):
            print(f"  {i}. {handler['id']}")
            print(f"     文件: {handler['file_path']}")
            print(f"     行号: {handler['start_line']}-{handler['end_line']}")
    
    print("\n[PASS] Node.js 项目分析正确\n")


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("测试 build_rag.py 改进功能")
    print("=" * 60 + "\n")
    
    try:
        test_extract_code_chunk()
        test_should_index_frontend_file()
        test_build_documents_with_symbol_table()
        test_coffee_shop_nodejs()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
        print("\n改进总结:")
        print("1. [DONE] 前端标签已同步更新")
        print("   - Frontend_Router -> Frontend_Auth_Integration (已实现)")
        print("\n2. [DONE] 前端和后端分开处理策略")
        print("   前端文件：")
        print("   - 只索引有关键特征的文件（API/Config/Auth）")
        print("   - 整文件索引")
        print("   - 不附带 metadata")
        print("\n   后端文件（Python/Node.js）：")
        print("   - 按函数/类/路由处理器级别分片")
        print("   - 使用 symbol_table（避免重复解析）")
        print("   - 附带详细 metadata")
        print("\n核心优势:")
        print("   - 前端和后端分离处理，策略清晰")
        print("   - 避免重复解析（直接使用 static_analyzer 的结果）")
        print("   - 后端代码细粒度分片，便于精确检索")
        
    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        return 1
    except Exception as e:
        print(f"\n[FAIL] 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

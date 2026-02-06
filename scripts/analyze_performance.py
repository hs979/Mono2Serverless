#!/usr/bin/env python3
"""
性能报告分析脚本
用于快速分析性能监控日志，提供优化建议
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def load_latest_report(log_dir: Path) -> Dict[str, Any]:
    """加载最新的性能报告"""
    reports = sorted(log_dir.glob("performance_report_*.json"), reverse=True)
    
    if not reports:
        print(f"❌ 在 {log_dir} 中未找到性能报告")
        print("请先运行一次 MAG 系统以生成报告")
        sys.exit(1)
    
    latest = reports[0]
    print(f"📊 加载报告: {latest.name}\n")
    
    with open(latest, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_llm_performance(report: Dict[str, Any]) -> None:
    """分析 LLM 性能"""
    print("=" * 80)
    print("🤖 LLM API 调用分析")
    print("=" * 80)
    
    llm_calls = report.get('llm_calls', [])
    summary = report.get('summary', {}).get('llm_calls', {})
    
    if not llm_calls:
        print("⚠️  未记录到 LLM 调用\n")
        return
    
    count = summary.get('count', 0)
    total_time = summary.get('total_time_seconds', 0)
    avg_time = summary.get('average_time_seconds', 0)
    percentage = summary.get('percentage_of_total', 0)
    
    print(f"\n📈 基本统计:")
    print(f"  调用次数: {count}")
    print(f"  总耗时: {total_time:.2f}秒 ({total_time/60:.2f}分钟)")
    print(f"  平均耗时: {avg_time:.2f}秒/次")
    print(f"  占总时间: {percentage:.1f}%")
    
    # 分析调用时间分布
    durations = [call.get('duration_seconds', 0) for call in llm_calls if call.get('duration_seconds')]
    if durations:
        durations.sort()
        min_time = min(durations)
        max_time = max(durations)
        median_time = durations[len(durations) // 2]
        
        print(f"\n⏱️  调用时间分布:")
        print(f"  最快: {min_time:.2f}秒")
        print(f"  最慢: {max_time:.2f}秒")
        print(f"  中位数: {median_time:.2f}秒")
    
    # 分析 Token 使用
    total_tokens_list = [call.get('total_tokens', 0) for call in llm_calls if call.get('total_tokens')]
    if total_tokens_list:
        total_tokens_sum = sum(total_tokens_list)
        avg_tokens = total_tokens_sum / len(total_tokens_list)
        
        print(f"\n💬 Token 使用:")
        print(f"  总 Tokens: {total_tokens_sum:,}")
        print(f"  平均 Tokens/次: {avg_tokens:.0f}")
    
    # 性能评估和建议
    print(f"\n💡 性能评估:")
    if percentage > 70:
        print(f"  ⚠️  LLM 调用占比过高 ({percentage:.1f}%)，这是主要瓶颈！")
        print(f"\n  建议:")
        print(f"  1. 考虑更换响应更快的模型")
        
        if avg_time > 10:
            print(f"  2. 平均响应时间 {avg_time:.1f}秒偏高，建议：")
            print(f"     - 尝试 gpt-4o-mini (通常 2-5 秒)")
            print(f"     - 尝试 gpt-3.5-turbo (通常 1-3 秒)")
            print(f"     - 使用本地 Ollama 模型 (通常 5-15 秒，但无网络延迟)")
        
        print(f"  3. 优化 prompt 以减少 token 使用")
        print(f"  4. 检查是否有不必要的重复调用")
    elif percentage > 50:
        print(f"  ✅ LLM 调用占比合理 ({percentage:.1f}%)")
        print(f"  可以进一步优化，但不是最主要的瓶颈")
    else:
        print(f"  ✅ LLM 调用占比很低 ({percentage:.1f}%)，表现优秀！")
    
    print()


def analyze_task_performance(report: Dict[str, Any]) -> None:
    """分析 Task 性能"""
    print("=" * 80)
    print("📋 Task 执行分析")
    print("=" * 80)
    
    task_times = report.get('task_times', [])
    
    if not task_times:
        print("⚠️  未记录到 Task 执行信息\n")
        return
    
    print(f"\n共 {len(task_times)} 个任务:\n")
    
    for i, task in enumerate(task_times, 1):
        name = task.get('task_name', 'Unknown')
        agent = task.get('agent_name', 'Unknown')
        duration = task.get('duration_seconds', 0)
        success = task.get('success', True)
        
        status = "✅" if success else "❌"
        print(f"  {status} Task {i}: {name[:60]}")
        print(f"     Agent: {agent}")
        print(f"     耗时: {duration:.2f}秒 ({duration/60:.2f}分钟)")
        print()
    
    # 找出最慢的任务
    if task_times:
        slowest = max(task_times, key=lambda x: x.get('duration_seconds', 0))
        print(f"🐌 最慢的任务: {slowest.get('task_name', 'Unknown')[:60]}")
        print(f"   耗时: {slowest.get('duration_seconds', 0):.2f}秒")
        print()


def analyze_tool_performance(report: Dict[str, Any]) -> None:
    """分析工具调用性能"""
    print("=" * 80)
    print("🔧 工具调用分析")
    print("=" * 80)
    
    tool_calls = report.get('tool_calls', [])
    summary = report.get('summary', {}).get('tool_calls', {})
    
    if not tool_calls:
        print("⚠️  未记录到工具调用\n")
        return
    
    count = summary.get('count', 0)
    total_time = summary.get('total_time_seconds', 0)
    percentage = summary.get('percentage_of_total', 0)
    
    print(f"\n📈 基本统计:")
    print(f"  调用次数: {count}")
    print(f"  总耗时: {total_time:.2f}秒")
    print(f"  占总时间: {percentage:.1f}%")
    
    # 按工具名称统计
    tool_stats = {}
    for call in tool_calls:
        tool_name = call.get('tool_name', 'Unknown')
        duration = call.get('duration_seconds', 0)
        
        if tool_name not in tool_stats:
            tool_stats[tool_name] = {'count': 0, 'total_time': 0, 'times': []}
        
        tool_stats[tool_name]['count'] += 1
        tool_stats[tool_name]['total_time'] += duration
        tool_stats[tool_name]['times'].append(duration)
    
    print(f"\n🔨 各工具调用统计:")
    for tool_name, stats in sorted(tool_stats.items(), key=lambda x: x[1]['total_time'], reverse=True):
        count = stats['count']
        total = stats['total_time']
        avg = total / count if count > 0 else 0
        
        print(f"\n  {tool_name}:")
        print(f"    调用次数: {count}")
        print(f"    总耗时: {total:.3f}秒")
        print(f"    平均耗时: {avg:.3f}秒/次")
    
    # 性能评估
    print(f"\n💡 性能评估:")
    if percentage > 20:
        print(f"  ⚠️  工具调用占比较高 ({percentage:.1f}%)，可能存在效率问题")
        print(f"  建议检查最耗时的工具调用")
    elif percentage > 10:
        print(f"  ✅ 工具调用占比正常 ({percentage:.1f}%)")
    else:
        print(f"  ✅ 工具调用很高效 ({percentage:.1f}%)")
    
    print()


def analyze_time_distribution(report: Dict[str, Any]) -> None:
    """分析时间分布"""
    print("=" * 80)
    print("📊 整体时间分布分析")
    print("=" * 80)
    
    summary = report.get('summary', {})
    total_time = summary.get('total_duration_seconds', 0)
    
    llm_percentage = summary.get('llm_calls', {}).get('percentage_of_total', 0)
    llm_time = summary.get('llm_calls', {}).get('total_time_seconds', 0)
    
    tool_percentage = summary.get('tool_calls', {}).get('percentage_of_total', 0)
    tool_time = summary.get('tool_calls', {}).get('total_time_seconds', 0)
    
    other_percentage = summary.get('other_percentage', 0)
    other_time = summary.get('other_time_seconds', 0)
    
    print(f"\n总执行时间: {total_time:.2f}秒 ({total_time/60:.2f}分钟)\n")
    
    # 可视化时间分布（使用进度条）
    bar_length = 60
    
    print("时间分布:")
    print()
    
    # LLM
    llm_bar = int(bar_length * llm_percentage / 100)
    print(f"  🤖 LLM API: {'█' * llm_bar}{' ' * (bar_length - llm_bar)} {llm_percentage:.1f}% ({llm_time:.1f}s)")
    
    # Tool
    tool_bar = int(bar_length * tool_percentage / 100)
    print(f"  🔧 工具调用: {'█' * tool_bar}{' ' * (bar_length - tool_bar)} {tool_percentage:.1f}% ({tool_time:.1f}s)")
    
    # Other
    other_bar = int(bar_length * other_percentage / 100)
    print(f"  ⚙️  其他处理: {'█' * other_bar}{' ' * (bar_length - other_bar)} {other_percentage:.1f}% ({other_time:.1f}s)")
    
    print(f"\n💡 优化建议:")
    
    # 找出最大的瓶颈
    components = [
        ("LLM API 调用", llm_percentage, llm_time),
        ("工具调用", tool_percentage, tool_time),
        ("其他处理", other_percentage, other_time)
    ]
    components.sort(key=lambda x: x[1], reverse=True)
    
    top_component = components[0]
    print(f"\n  主要瓶颈: {top_component[0]} (占 {top_component[1]:.1f}%)")
    
    if top_component[0] == "LLM API 调用":
        print(f"  ➡️  优先优化 LLM 调用速度（切换更快的模型）")
    elif top_component[0] == "工具调用":
        print(f"  ➡️  优先优化工具效率（添加缓存、减少 I/O）")
    else:
        print(f"  ➡️  优先优化 Agent 逻辑（减少不必要的思考步骤）")
    
    print()


def generate_recommendations(report: Dict[str, Any]) -> None:
    """生成综合优化建议"""
    print("=" * 80)
    print("💡 综合优化建议")
    print("=" * 80)
    
    summary = report.get('summary', {})
    llm_stats = summary.get('llm_calls', {})
    tool_stats = summary.get('tool_calls', {})
    
    llm_percentage = llm_stats.get('percentage_of_total', 0)
    llm_avg_time = llm_stats.get('average_time_seconds', 0)
    tool_percentage = tool_stats.get('percentage_of_total', 0)
    
    recommendations = []
    
    # LLM 相关建议
    if llm_percentage > 70:
        recommendations.append({
            'priority': '🔴 高优先级',
            'category': 'LLM 优化',
            'items': [
                f"LLM 调用占 {llm_percentage:.1f}%，建议立即优化",
                "方案 1: 切换到更快的模型（推荐 gpt-4o-mini 或 gpt-3.5-turbo）",
                "方案 2: 使用本地 Ollama 模型减少网络延迟",
                "方案 3: 优化 Agent prompt 减少 token 使用"
            ]
        })
    elif llm_percentage > 50:
        recommendations.append({
            'priority': '🟡 中优先级',
            'category': 'LLM 优化',
            'items': [
                f"LLM 调用占 {llm_percentage:.1f}%，有优化空间",
                "考虑切换到更高性价比的模型"
            ]
        })
    
    # 工具相关建议
    if tool_percentage > 20:
        recommendations.append({
            'priority': '🔴 高优先级',
            'category': '工具优化',
            'items': [
                f"工具调用占 {tool_percentage:.1f}%，效率偏低",
                "检查是否有频繁的文件读写",
                "为 RAG 检索添加缓存机制",
                "考虑批量处理文件操作"
            ]
        })
    elif tool_percentage > 10:
        recommendations.append({
            'priority': '🟡 中优先级',
            'category': '工具优化',
            'items': [
                f"工具调用占 {tool_percentage:.1f}%，可以进一步优化"
            ]
        })
    
    # Agent 相关建议
    other_percentage = summary.get('other_percentage', 0)
    if other_percentage > 30:
        recommendations.append({
            'priority': '🔴 高优先级',
            'category': 'Agent 逻辑优化',
            'items': [
                f"Agent 处理和框架开销占 {other_percentage:.1f}%",
                "优化 Agent 的 goal 和 backstory，使其更聚焦",
                "检查是否有不必要的重复操作",
                "考虑简化任务描述"
            ]
        })
    
    # 打印建议
    if not recommendations:
        print("\n✅ 系统性能良好，暂无重要优化建议\n")
        return
    
    print()
    for rec in recommendations:
        print(f"{rec['priority']} - {rec['category']}")
        print("─" * 60)
        for item in rec['items']:
            print(f"  • {item}")
        print()


def main():
    """主函数"""
    # 获取日志目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    log_dir = project_root / "storage" / "performance_logs"
    
    if not log_dir.exists():
        print(f"❌ 日志目录不存在: {log_dir}")
        print("请先运行一次 MAG 系统以生成性能报告")
        sys.exit(1)
    
    # 加载最新报告
    report = load_latest_report(log_dir)
    
    # 执行各项分析
    analyze_time_distribution(report)
    analyze_llm_performance(report)
    analyze_task_performance(report)
    analyze_tool_performance(report)
    generate_recommendations(report)
    
    print("=" * 80)
    print("✅ 分析完成")
    print("=" * 80)
    print(f"\n详细报告位置: {log_dir}")
    print("\n提示: 可以对比多次运行的报告来评估优化效果\n")


if __name__ == "__main__":
    main()

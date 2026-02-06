"""
性能监控模块
用于记录 LLM API 调用时间、Agent 处理时间等性能指标
"""
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from functools import wraps
import threading


class PerformanceMonitor:
    """性能监控器，记录各种时间指标"""
    
    def __init__(self, log_dir: Path):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录数据
        self.llm_calls: List[Dict[str, Any]] = []
        self.task_times: List[Dict[str, Any]] = []
        self.agent_times: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []
        
        # 会话信息
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_start = time.time()
        
        # 线程锁
        self._lock = threading.Lock()
        
        print(f"📊 性能监控已启动 - Session ID: {self.session_id}")
    
    def record_llm_call(
        self,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        duration: Optional[float] = None,
        success: bool = True,
        error: Optional[str] = None,
        context: Optional[str] = None
    ):
        """记录一次 LLM API 调用"""
        with self._lock:
            if duration is None and start_time and end_time:
                duration = end_time - start_time
            
            record = {
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "duration_seconds": duration,
                "success": success,
                "error": error,
                "context": context  # 例如: "agent: architect, task: blueprint"
            }
            self.llm_calls.append(record)
            
            # 实时打印
            print(f"🤖 LLM 调用 [{model}]: {duration:.2f}s | "
                  f"Tokens: {total_tokens or 'N/A'} | "
                  f"Context: {context or 'N/A'}")
    
    def record_task(
        self,
        task_name: str,
        agent_name: str,
        start_time: float,
        end_time: float,
        success: bool = True,
        output_size: Optional[int] = None
    ):
        """记录一个 Task 的执行"""
        with self._lock:
            duration = end_time - start_time
            record = {
                "timestamp": datetime.now().isoformat(),
                "task_name": task_name,
                "agent_name": agent_name,
                "duration_seconds": duration,
                "success": success,
                "output_size": output_size
            }
            self.task_times.append(record)
            
            print(f"📋 Task 完成 [{task_name}]: {duration:.2f}s | Agent: {agent_name}")
    
    def record_agent_action(
        self,
        agent_name: str,
        action_type: str,
        start_time: float,
        end_time: float,
        details: Optional[str] = None
    ):
        """记录 Agent 的单次操作"""
        with self._lock:
            duration = end_time - start_time
            record = {
                "timestamp": datetime.now().isoformat(),
                "agent_name": agent_name,
                "action_type": action_type,
                "duration_seconds": duration,
                "details": details
            }
            self.agent_times.append(record)
    
    def record_tool_call(
        self,
        tool_name: str,
        agent_name: str,
        start_time: float,
        end_time: float,
        success: bool = True
    ):
        """记录工具调用"""
        with self._lock:
            duration = end_time - start_time
            record = {
                "timestamp": datetime.now().isoformat(),
                "tool_name": tool_name,
                "agent_name": agent_name,
                "duration_seconds": duration,
                "success": success
            }
            self.tool_calls.append(record)
            
            print(f"🔧 Tool 调用 [{tool_name}]: {duration:.3f}s | Agent: {agent_name}")
    
    def start_timer(self) -> float:
        """开始计时"""
        return time.time()
    
    def save_report(self):
        """保存性能报告到文件"""
        total_duration = time.time() - self.session_start
        
        report = {
            "session_id": self.session_id,
            "total_duration_seconds": total_duration,
            "summary": self._generate_summary(),
            "llm_calls": self.llm_calls,
            "task_times": self.task_times,
            "agent_times": self.agent_times,
            "tool_calls": self.tool_calls
        }
        
        # 保存详细报告
        report_file = self.log_dir / f"performance_report_{self.session_id}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, indent=2, ensure_ascii=False, fp=f)
        
        # 保存简化的统计报告
        summary_file = self.log_dir / f"performance_summary_{self.session_id}.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(self._format_summary())
        
        print(f"\n📊 性能报告已保存:")
        print(f"  - 详细报告: {report_file}")
        print(f"  - 统计摘要: {summary_file}")
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成统计摘要"""
        total_duration = time.time() - self.session_start
        
        # LLM 调用统计
        llm_total_time = sum(call.get("duration_seconds", 0) for call in self.llm_calls if call.get("duration_seconds"))
        llm_count = len(self.llm_calls)
        llm_avg_time = llm_total_time / llm_count if llm_count > 0 else 0
        
        # Task 统计
        task_total_time = sum(task.get("duration_seconds", 0) for task in self.task_times)
        task_count = len(self.task_times)
        
        # Tool 调用统计
        tool_total_time = sum(tool.get("duration_seconds", 0) for tool in self.tool_calls)
        tool_count = len(self.tool_calls)
        
        # 计算比例
        llm_percentage = (llm_total_time / total_duration * 100) if total_duration > 0 else 0
        tool_percentage = (tool_total_time / total_duration * 100) if total_duration > 0 else 0
        
        return {
            "total_duration_seconds": total_duration,
            "llm_calls": {
                "count": llm_count,
                "total_time_seconds": llm_total_time,
                "average_time_seconds": llm_avg_time,
                "percentage_of_total": llm_percentage
            },
            "tasks": {
                "count": task_count,
                "total_time_seconds": task_total_time
            },
            "tool_calls": {
                "count": tool_count,
                "total_time_seconds": tool_total_time,
                "percentage_of_total": tool_percentage
            },
            "other_time_seconds": total_duration - llm_total_time - tool_total_time,
            "other_percentage": 100 - llm_percentage - tool_percentage
        }
    
    def _format_summary(self) -> str:
        """格式化统计摘要为文本"""
        summary = self._generate_summary()
        total = summary["total_duration_seconds"]
        
        lines = [
            "=" * 80,
            f"性能分析报告 - Session: {self.session_id}",
            "=" * 80,
            "",
            f"📊 总执行时间: {total:.2f}秒 ({total/60:.2f}分钟)",
            "",
            "=" * 80,
            "🤖 LLM API 调用统计",
            "=" * 80,
            f"  调用次数: {summary['llm_calls']['count']}",
            f"  总耗时: {summary['llm_calls']['total_time_seconds']:.2f}秒",
            f"  平均耗时: {summary['llm_calls']['average_time_seconds']:.2f}秒/次",
            f"  占总时间比例: {summary['llm_calls']['percentage_of_total']:.1f}%",
            "",
            "=" * 80,
            "📋 Task 执行统计",
            "=" * 80,
            f"  任务数量: {summary['tasks']['count']}",
            f"  总耗时: {summary['tasks']['total_time_seconds']:.2f}秒",
            ""
        ]
        
        # 每个 Task 的详细时间
        if self.task_times:
            lines.append("  各任务耗时:")
            for task in self.task_times:
                lines.append(f"    - {task['task_name']}: {task['duration_seconds']:.2f}秒 (Agent: {task['agent_name']})")
            lines.append("")
        
        lines.extend([
            "=" * 80,
            "🔧 工具调用统计",
            "=" * 80,
            f"  调用次数: {summary['tool_calls']['count']}",
            f"  总耗时: {summary['tool_calls']['total_time_seconds']:.2f}秒",
            f"  占总时间比例: {summary['tool_calls']['percentage_of_total']:.1f}%",
            "",
            "=" * 80,
            "📈 时间分布",
            "=" * 80,
            f"  LLM API 调用: {summary['llm_calls']['percentage_of_total']:.1f}% ({summary['llm_calls']['total_time_seconds']:.2f}秒)",
            f"  工具调用: {summary['tool_calls']['percentage_of_total']:.1f}% ({summary['tool_calls']['total_time_seconds']:.2f}秒)",
            f"  其他处理: {summary['other_percentage']:.1f}% ({summary['other_time_seconds']:.2f}秒)",
            "",
        ])
        
        # LLM 调用详细列表
        if self.llm_calls:
            lines.extend([
                "=" * 80,
                "🤖 LLM 调用详细记录",
                "=" * 80,
            ])
            for i, call in enumerate(self.llm_calls, 1):
                duration = call.get("duration_seconds", 0)
                tokens = call.get("total_tokens", "N/A")
                context = call.get("context", "N/A")
                lines.append(f"  #{i}: {duration:.2f}s | Tokens: {tokens} | {context}")
            lines.append("")
        
        return "\n".join(lines)
    
    def print_summary(self):
        """打印统计摘要"""
        print("\n" + self._format_summary())


# 全局监控实例
_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> Optional[PerformanceMonitor]:
    """获取全局监控实例"""
    return _monitor


def init_monitor(log_dir: Path) -> PerformanceMonitor:
    """初始化全局监控实例"""
    global _monitor
    _monitor = PerformanceMonitor(log_dir)
    return _monitor


def time_it(name: str, context: Optional[str] = None):
    """装饰器：自动记录函数执行时间"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_monitor()
            start = time.time()
            try:
                result = func(*args, **kwargs)
                if monitor:
                    end = time.time()
                    monitor.record_agent_action(
                        agent_name=context or "unknown",
                        action_type=name,
                        start_time=start,
                        end_time=end
                    )
                return result
            except Exception as e:
                if monitor:
                    end = time.time()
                    monitor.record_agent_action(
                        agent_name=context or "unknown",
                        action_type=name,
                        start_time=start,
                        end_time=end,
                        details=f"Error: {str(e)}"
                    )
                raise
        return wrapper
    return decorator

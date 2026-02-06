"""
为 CrewAI 工具添加性能监控的包装器
"""
import time
from typing import Any
from functools import wraps
from crewai.tools import BaseTool

from .performance_monitor import get_monitor


def monitor_tool(tool_class):
    """
    装饰器：为 CrewAI 工具类添加性能监控
    包装 _run 方法以记录执行时间
    """
    original_run = tool_class._run
    
    @wraps(original_run)
    def monitored_run(self, *args, **kwargs):
        monitor = get_monitor()
        start = time.time()
        
        try:
            result = original_run(self, *args, **kwargs)
            end = time.time()
            
            if monitor:
                # 尝试获取 agent 名称（如果可用）
                agent_name = getattr(self, '_agent_name', 'unknown')
                monitor.record_tool_call(
                    tool_name=self.name,
                    agent_name=agent_name,
                    start_time=start,
                    end_time=end,
                    success=True
                )
            
            return result
            
        except Exception as e:
            end = time.time()
            
            if monitor:
                agent_name = getattr(self, '_agent_name', 'unknown')
                monitor.record_tool_call(
                    tool_name=self.name,
                    agent_name=agent_name,
                    start_time=start,
                    end_time=end,
                    success=False
                )
            
            raise
    
    tool_class._run = monitored_run
    return tool_class


def create_monitored_tool(tool_instance: BaseTool, agent_name: str = "unknown") -> BaseTool:
    """
    为工具实例添加监控功能
    
    Args:
        tool_instance: CrewAI 工具实例
        agent_name: 使用该工具的 agent 名称
    
    Returns:
        添加了监控的工具实例
    """
    # 保存 agent 名称到工具实例
    tool_instance._agent_name = agent_name
    
    # 包装 _run 方法
    original_run = tool_instance._run
    
    @wraps(original_run)
    def monitored_run(*args, **kwargs):
        monitor = get_monitor()
        start = time.time()
        
        try:
            result = original_run(*args, **kwargs)
            end = time.time()
            
            if monitor:
                monitor.record_tool_call(
                    tool_name=tool_instance.name,
                    agent_name=agent_name,
                    start_time=start,
                    end_time=end,
                    success=True
                )
            
            return result
            
        except Exception as e:
            end = time.time()
            
            if monitor:
                monitor.record_tool_call(
                    tool_name=tool_instance.name,
                    agent_name=agent_name,
                    start_time=start,
                    end_time=end,
                    success=False
                )
            
            raise
    
    tool_instance._run = monitored_run
    return tool_instance

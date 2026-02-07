"""
CrewAI 专用监控器
通过 monkey patch 方式监控 CrewAI 的 LLM 调用和 Agent 执行
"""
import time
from typing import Any, Optional
from functools import wraps

from .performance_monitor import get_monitor


def patch_crewai_llm():
    """
    Patch CrewAI 的 LLM 调用以添加性能监控
    CrewAI 使用 LiteLLM，我们需要在 LiteLLM 层面添加监控
    同时 patch 同步和异步方法
    """
    try:
        import litellm
        
        patched_methods = []
        
        # Patch 同步 completion
        if hasattr(litellm, 'completion'):
            original_completion = litellm.completion
            
            @wraps(original_completion)
            def monitored_completion(*args, **kwargs):
                monitor = get_monitor()
                start_time = time.time()
                
                # 提取模型名称
                model = kwargs.get('model', args[0] if args else 'unknown')
                
                # 获取上下文
                context = _get_current_context()
                
                print(f"⏱️  LLM 同步调用开始 - Model: {model}")
                
                try:
                    # 调用原始函数
                    response = original_completion(*args, **kwargs)
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    # 记录成功的调用
                    if monitor:
                        usage = getattr(response, 'usage', None)
                        prompt_tokens = getattr(usage, 'prompt_tokens', None) if usage else None
                        completion_tokens = getattr(usage, 'completion_tokens', None) if usage else None
                        total_tokens = getattr(usage, 'total_tokens', None) if usage else None
                        
                        monitor.record_llm_call(
                            model=str(model),
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            start_time=start_time,
                            end_time=end_time,
                            success=True,
                            context=context
                        )
                    
                    return response
                    
                except Exception as e:
                    end_time = time.time()
                    
                    # 记录失败的调用
                    if monitor:
                        monitor.record_llm_call(
                            model=str(model),
                            start_time=start_time,
                            end_time=end_time,
                            success=False,
                            error=str(e),
                            context=context
                        )
                    
                    raise
            
            # 替换 LiteLLM 的 completion 函数
            litellm.completion = monitored_completion
            patched_methods.append('completion')
        
        # Patch 异步 acompletion
        if hasattr(litellm, 'acompletion'):
            original_acompletion = litellm.acompletion
            
            @wraps(original_acompletion)
            async def monitored_acompletion(*args, **kwargs):
                monitor = get_monitor()
                start_time = time.time()
                
                # 提取模型名称
                model = kwargs.get('model', args[0] if args else 'unknown')
                
                # 获取上下文
                context = _get_current_context()
                
                print(f"⏱️  LLM 异步调用开始 - Model: {model}")
                
                try:
                    # 调用原始函数
                    response = await original_acompletion(*args, **kwargs)
                    end_time = time.time()
                    duration = end_time - start_time
                    
                    # 记录成功的调用
                    if monitor:
                        usage = getattr(response, 'usage', None)
                        prompt_tokens = getattr(usage, 'prompt_tokens', None) if usage else None
                        completion_tokens = getattr(usage, 'completion_tokens', None) if usage else None
                        total_tokens = getattr(usage, 'total_tokens', None) if usage else None
                        
                        monitor.record_llm_call(
                            model=str(model),
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            start_time=start_time,
                            end_time=end_time,
                            success=True,
                            context=context
                        )
                    
                    return response
                    
                except Exception as e:
                    end_time = time.time()
                    
                    # 记录失败的调用
                    if monitor:
                        monitor.record_llm_call(
                            model=str(model),
                            start_time=start_time,
                            end_time=end_time,
                            success=False,
                            error=str(e),
                            context=context
                        )
                    
                    raise
            
            litellm.acompletion = monitored_acompletion
            patched_methods.append('acompletion')
        
        # Patch text_completion (如果存在)
        if hasattr(litellm, 'text_completion'):
            original_text = litellm.text_completion
            
            @wraps(original_text)
            def monitored_text(*args, **kwargs):
                monitor = get_monitor()
                start_time = time.time()
                model = kwargs.get('model', args[0] if args else 'unknown')
                context = _get_current_context()
                
                print(f"⏱️  LLM 文本调用开始 - Model: {model}")
                
                try:
                    response = original_text(*args, **kwargs)
                    end_time = time.time()
                    
                    if monitor:
                        usage = getattr(response, 'usage', None)
                        monitor.record_llm_call(
                            model=str(model),
                            prompt_tokens=getattr(usage, 'prompt_tokens', None) if usage else None,
                            completion_tokens=getattr(usage, 'completion_tokens', None) if usage else None,
                            total_tokens=getattr(usage, 'total_tokens', None) if usage else None,
                            start_time=start_time,
                            end_time=end_time,
                            success=True,
                            context=context
                        )
                    
                    return response
                except Exception as e:
                    end_time = time.time()
                    if monitor:
                        monitor.record_llm_call(
                            model=str(model),
                            start_time=start_time,
                            end_time=end_time,
                            success=False,
                            error=str(e),
                            context=context
                        )
                    raise
            
            litellm.text_completion = monitored_text
            patched_methods.append('text_completion')
        
        if patched_methods:
            print(f"✅ 已成功 patch LiteLLM 方法: {', '.join(patched_methods)}")
            return True
        else:
            print("⚠️  未找到可 patch 的 LiteLLM 方法")
            return False
        
    except ImportError:
        print("⚠️  LiteLLM 未安装，无法 patch LLM 调用")
        return False
    except Exception as e:
        print(f"⚠️  Patch LiteLLM 时出错: {e}")
        import traceback
        traceback.print_exc()
        return False


def patch_crewai_agent():
    """
    Patch CrewAI 的 Agent 执行以添加性能监控
    """
    try:
        from crewai import Agent
        import inspect
        
        # 保存原始的 execute_task 方法（如果存在）
        if hasattr(Agent, 'execute_task'):
            original_execute = Agent.execute_task
            
            # 获取原始方法的签名
            sig = inspect.signature(original_execute)
            
            @wraps(original_execute)
            def monitored_execute(self, *args, **kwargs):
                monitor = get_monitor()
                start_time = time.time()
                agent_name = getattr(self, 'role', 'unknown')
                
                # 设置当前上下文
                _set_current_context(f"agent={agent_name}")
                
                try:
                    result = original_execute(self, *args, **kwargs)
                    end_time = time.time()
                    
                    if monitor:
                        # 尝试从 args 获取 task
                        task = args[0] if args else None
                        task_desc = getattr(task, 'description', 'N/A')[:100] if task else 'N/A'
                        
                        monitor.record_agent_action(
                            agent_name=agent_name,
                            action_type="execute_task",
                            start_time=start_time,
                            end_time=end_time,
                            details=f"Task: {task_desc}"
                        )
                    
                    return result
                    
                finally:
                    _clear_current_context()
            
            Agent.execute_task = monitored_execute
            print("✅ 已成功 patch Agent.execute_task 方法进行性能监控")
            return True
        else:
            print("⚠️  Agent.execute_task 方法不存在，跳过 patch")
            return False
            
    except ImportError:
        print("⚠️  CrewAI 未安装，无法 patch Agent")
        return False
    except Exception as e:
        print(f"⚠️  Patch Agent 时出错: {e}")
        return False


def patch_crewai_task():
    """
    Patch CrewAI 的 Task 执行以添加性能监控
    注意：CrewAI 的 Task 可能使用 execute_sync 或其他方法
    """
    try:
        from crewai import Task
        import inspect
        
        patched = False
        
        # 尝试 patch execute_sync (更常用的方法)
        if hasattr(Task, 'execute_sync'):
            original_execute = Task.execute_sync
            
            @wraps(original_execute)
            def monitored_execute_sync(self, *args, **kwargs):
                monitor = get_monitor()
                start_time = time.time()
                
                task_desc = getattr(self, 'description', 'unknown')[:50]
                agent_name = getattr(self.agent, 'role', 'unknown') if hasattr(self, 'agent') and self.agent else 'unknown'
                
                # 设置当前上下文
                _set_current_context(f"agent={agent_name}, task={task_desc}")
                
                try:
                    result = original_execute(self, *args, **kwargs)
                    end_time = time.time()
                    
                    if monitor:
                        output_size = len(str(result)) if result else 0
                        monitor.record_task(
                            task_name=task_desc,
                            agent_name=agent_name,
                            start_time=start_time,
                            end_time=end_time,
                            success=True,
                            output_size=output_size
                        )
                    
                    return result
                    
                except Exception as e:
                    end_time = time.time()
                    
                    if monitor:
                        monitor.record_task(
                            task_name=task_desc,
                            agent_name=agent_name,
                            start_time=start_time,
                            end_time=end_time,
                            success=False
                        )
                    
                    raise
                    
                finally:
                    _clear_current_context()
            
            Task.execute_sync = monitored_execute_sync
            print("✅ 已成功 patch Task.execute_sync 方法进行性能监控")
            patched = True
        
        # 如果 execute 方法存在，也 patch 它
        if hasattr(Task, 'execute'):
            original_execute = Task.execute
            
            @wraps(original_execute)
            def monitored_execute(self, *args, **kwargs):
                monitor = get_monitor()
                start_time = time.time()
                
                task_desc = getattr(self, 'description', 'unknown')[:50]
                agent_name = getattr(self.agent, 'role', 'unknown') if hasattr(self, 'agent') and self.agent else 'unknown'
                
                _set_current_context(f"agent={agent_name}, task={task_desc}")
                
                try:
                    result = original_execute(self, *args, **kwargs)
                    end_time = time.time()
                    
                    if monitor:
                        output_size = len(str(result)) if result else 0
                        monitor.record_task(
                            task_name=task_desc,
                            agent_name=agent_name,
                            start_time=start_time,
                            end_time=end_time,
                            success=True,
                            output_size=output_size
                        )
                    
                    return result
                    
                except Exception as e:
                    end_time = time.time()
                    
                    if monitor:
                        monitor.record_task(
                            task_name=task_desc,
                            agent_name=agent_name,
                            start_time=start_time,
                            end_time=end_time,
                            success=False
                        )
                    
                    raise
                    
                finally:
                    _clear_current_context()
            
            Task.execute = monitored_execute
            print("✅ 已成功 patch Task.execute 方法进行性能监控")
            patched = True
        
        if not patched:
            print("⚠️  Task.execute 和 Task.execute_sync 方法都不存在，跳过 patch")
            return False
        
        return True
            
    except ImportError:
        print("⚠️  CrewAI 未安装，无法 patch Task")
        return False
    except Exception as e:
        print(f"⚠️  Patch Task 时出错: {e}")
        return False


# 上下文管理（用于追踪当前执行的 agent 和 task）
_context_stack = []

def _set_current_context(context: str):
    """设置当前执行上下文"""
    _context_stack.append(context)

def _clear_current_context():
    """清除当前执行上下文"""
    if _context_stack:
        _context_stack.pop()

def _get_current_context() -> Optional[str]:
    """获取当前执行上下文"""
    return _context_stack[-1] if _context_stack else None


def patch_all():
    """
    应用所有 patch 以监控 CrewAI 执行
    
    Returns:
        bool: 是否成功应用所有 patch
    """
    print("\n" + "=" * 60)
    print("开始 Patch CrewAI 以添加性能监控...")
    print("=" * 60)
    
    results = []
    
    # Patch LLM 调用
    results.append(patch_crewai_llm())
    
    # Patch Agent 执行
    results.append(patch_crewai_agent())
    
    # Patch Task 执行
    results.append(patch_crewai_task())
    
    success = any(results)  # 只要有一个成功就算成功
    
    if success:
        print("=" * 60)
        print("✅ CrewAI 性能监控 Patch 完成")
        print("=" * 60 + "\n")
    else:
        print("=" * 60)
        print("⚠️  CrewAI 性能监控 Patch 未能完全应用")
        print("=" * 60 + "\n")
    
    return success

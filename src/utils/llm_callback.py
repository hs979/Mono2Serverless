"""
LLM 调用回调处理器
用于监控和记录 LLM API 调用的详细信息
"""
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from langchain.callbacks.base import BaseCallbackHandler
    from langchain.schema import LLMResult
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    BaseCallbackHandler = object

from .performance_monitor import get_monitor


class LLMCallbackHandler(BaseCallbackHandler if LANGCHAIN_AVAILABLE else object):
    """
    LangChain 回调处理器，用于监控 LLM 调用
    """
    
    def __init__(self):
        if LANGCHAIN_AVAILABLE:
            super().__init__()
        self.start_times: Dict[str, float] = {}
        self.context_stack: List[str] = []
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """LLM 调用开始时触发"""
        run_id = kwargs.get("run_id", "unknown")
        self.start_times[str(run_id)] = time.time()
        
        # 尝试获取模型名称
        model = serialized.get("name", "unknown")
        if "kwargs" in serialized and "model_name" in serialized["kwargs"]:
            model = serialized["kwargs"]["model_name"]
        
        # 计算 prompt tokens (粗略估计)
        prompt_tokens = sum(len(p.split()) for p in prompts) if prompts else 0
        
        print(f"⏱️  LLM 调用开始 - Model: {model} | Prompt tokens (估算): ~{prompt_tokens}")
    
    def on_llm_end(
        self,
        response: "LLMResult",
        **kwargs: Any
    ) -> None:
        """LLM 调用结束时触发"""
        run_id = str(kwargs.get("run_id", "unknown"))
        start_time = self.start_times.pop(run_id, None)
        
        if start_time is None:
            return
        
        end_time = time.time()
        duration = end_time - start_time
        
        monitor = get_monitor()
        if not monitor:
            return
        
        # 提取 token 使用信息
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage", {})
        
        prompt_tokens = token_usage.get("prompt_tokens")
        completion_tokens = token_usage.get("completion_tokens")
        total_tokens = token_usage.get("total_tokens")
        
        # 提取模型名称
        model = llm_output.get("model_name", "unknown")
        
        # 获取上下文信息
        context = self.context_stack[-1] if self.context_stack else None
        
        # 记录到监控器
        monitor.record_llm_call(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=True,
            context=context
        )
    
    def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any
    ) -> None:
        """LLM 调用出错时触发"""
        run_id = str(kwargs.get("run_id", "unknown"))
        start_time = self.start_times.pop(run_id, None)
        
        if start_time is None:
            return
        
        end_time = time.time()
        duration = end_time - start_time
        
        monitor = get_monitor()
        if not monitor:
            return
        
        context = self.context_stack[-1] if self.context_stack else None
        
        monitor.record_llm_call(
            model="unknown",
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            success=False,
            error=str(error),
            context=context
        )
        
        print(f"❌ LLM 调用失败 - Error: {error} | Duration: {duration:.2f}s")
    
    def set_context(self, context: str):
        """设置当前上下文（例如：agent 名称、task 名称）"""
        self.context_stack.append(context)
    
    def clear_context(self):
        """清除当前上下文"""
        if self.context_stack:
            self.context_stack.pop()


# 全局回调实例
_callback_handler: Optional[LLMCallbackHandler] = None


def get_llm_callback() -> Optional[LLMCallbackHandler]:
    """获取全局 LLM 回调实例"""
    return _callback_handler


def init_llm_callback() -> LLMCallbackHandler:
    """初始化全局 LLM 回调实例"""
    global _callback_handler
    if not LANGCHAIN_AVAILABLE:
        print("⚠️  警告: LangChain 未安装，LLM 回调监控将不可用")
        return None
    
    _callback_handler = LLMCallbackHandler()
    print("✅ LLM 回调监控已初始化")
    return _callback_handler


def setup_litellm_callback():
    """
    设置 LiteLLM 的回调监控
    如果 CrewAI 使用 LiteLLM，可以通过这个函数注册回调
    """
    try:
        import litellm
        from litellm.integrations.custom_logger import CustomLogger
        
        class LiteLLMMonitor(CustomLogger):
            def __init__(self):
                super().__init__()
            
            def log_pre_api_call(self, model, messages, kwargs):
                self.start_time = time.time()
                print(f"⏱️  LiteLLM 调用开始 - Model: {model}")
            
            def log_post_api_call(self, kwargs, response_obj, start_time, end_time):
                duration = end_time - start_time
                monitor = get_monitor()
                
                if monitor and response_obj:
                    usage = getattr(response_obj, "usage", None)
                    model = kwargs.get("model", "unknown")
                    
                    monitor.record_llm_call(
                        model=model,
                        prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
                        completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
                        total_tokens=getattr(usage, "total_tokens", None) if usage else None,
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        success=True
                    )
            
            def log_failure_event(self, kwargs, response_obj, start_time, end_time):
                duration = end_time - start_time if start_time and end_time else 0
                monitor = get_monitor()
                
                if monitor:
                    monitor.record_llm_call(
                        model=kwargs.get("model", "unknown"),
                        duration=duration,
                        success=False,
                        error=str(response_obj)
                    )
        
        # 注册回调
        litellm.callbacks = [LiteLLMMonitor()]
        print("✅ LiteLLM 回调监控已初始化")
        return True
        
    except ImportError:
        print("⚠️  LiteLLM 未安装，跳过 LiteLLM 回调设置")
        return False
    except Exception as e:
        print(f"⚠️  设置 LiteLLM 回调时出错: {e}")
        return False

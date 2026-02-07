"""
诊断脚本：检测 CrewAI 使用的 LLM 调用方式
用于帮助正确 patch LLM 监控
"""
import sys
from pathlib import Path

# 添加项目路径
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

print("=" * 80)
print("CrewAI LLM 调用诊断")
print("=" * 80)

# 1. 检查 LiteLLM
print("\n1. Check LiteLLM...")
try:
    import litellm
    version = getattr(litellm, '__version__', 'unknown')
    print(f"[OK] LiteLLM installed: {version}")
    
    # 列出所有可用的方法
    methods = [m for m in dir(litellm) if not m.startswith('_') and callable(getattr(litellm, m))]
    llm_methods = [m for m in methods if 'complet' in m.lower() or 'chat' in m.lower()]
    
    print(f"\n   可用的 LLM 调用方法:")
    for method in llm_methods:
        print(f"   - {method}")
    
except ImportError as e:
    print(f"❌ LiteLLM 未安装: {e}")

# 2. 检查 CrewAI
print("\n2. 检查 CrewAI...")
try:
    import crewai
    version = getattr(crewai, '__version__', 'unknown')
    print(f"✅ CrewAI 已安装: {version}")
    
    from crewai import Agent, Task, Crew
    
    # 检查 Agent 的方法
    print(f"\n   Agent 方法:")
    agent_methods = [m for m in dir(Agent) if not m.startswith('_') and 'task' in m.lower()]
    for method in agent_methods:
        print(f"   - {method}")
    
    # 检查 Task 的方法
    print(f"\n   Task 方法:")
    task_methods = [m for m in dir(Task) if not m.startswith('_') and 'execut' in m.lower()]
    for method in task_methods:
        print(f"   - {method}")
    
except ImportError as e:
    print(f"❌ CrewAI 未安装: {e}")

# 3. 尝试创建测试 Agent 并查看其 LLM 配置
print("\n3. 检查 Agent 的 LLM 配置...")
try:
    from crewai import Agent
    from dotenv import load_dotenv
    
    load_dotenv(ROOT_DIR / ".env")
    
    test_agent = Agent(
        role="Test Agent",
        goal="Test",
        backstory="Test",
        verbose=False
    )
    
    # 检查 agent 的 LLM 相关属性
    llm_attrs = [attr for attr in dir(test_agent) if 'llm' in attr.lower()]
    print(f"\n   Agent 的 LLM 相关属性:")
    for attr in llm_attrs:
        if not attr.startswith('_'):
            try:
                value = getattr(test_agent, attr)
                print(f"   - {attr}: {type(value).__name__}")
            except:
                print(f"   - {attr}: (无法访问)")
    
    # 检查是否有 client 或其他调用方式
    if hasattr(test_agent, 'llm'):
        print(f"\n   Agent.llm 类型: {type(test_agent.llm)}")
        print(f"   Agent.llm 模块: {type(test_agent.llm).__module__}")
        
        # 检查 llm 对象的方法
        if hasattr(test_agent.llm, '__dict__'):
            print(f"\n   Agent.llm 的属性:")
            for key, value in test_agent.llm.__dict__.items():
                if not key.startswith('_'):
                    print(f"   - {key}: {type(value).__name__}")
    
except Exception as e:
    print(f"❌ 无法创建测试 Agent: {e}")
    import traceback
    traceback.print_exc()

# 4. 检查实际的调用栈
print("\n4. 尝试 Patch 并测试...")
try:
    import litellm
    
    # 记录调用
    call_count = [0]  # 使用列表以便在闭包中修改
    
    original_completion = litellm.completion
    
    def test_patch(*args, **kwargs):
        call_count[0] += 1
        model = kwargs.get('model', 'unknown')
        print(f"   ✅ 捕获到调用 #{call_count[0]}: model={model}")
        print(f"      Args: {[type(a).__name__ for a in args]}")
        print(f"      Kwargs keys: {list(kwargs.keys())}")
        return original_completion(*args, **kwargs)
    
    litellm.completion = test_patch
    
    print("\n   已 patch litellm.completion，尝试调用...")
    
    # 模拟一个简单调用
    try:
        from crewai import Agent
        from dotenv import load_dotenv
        import os
        
        load_dotenv(ROOT_DIR / ".env")
        
        # 确保有环境变量
        if not os.getenv('OPENAI_API_KEY'):
            print("   ⚠️  未设置 OPENAI_API_KEY，跳过测试调用")
        else:
            test_agent = Agent(
                role="Test",
                goal="Say hello",
                backstory="Test agent",
                verbose=True
            )
            
            # 注意：这里不实际执行 task，只是检查 patch 是否工作
            print(f"   Agent 创建成功，patch 测试完成")
            print(f"   捕获到的调用次数: {call_count[0]}")
    
    except Exception as e:
        print(f"   ⚠️  测试调用失败: {e}")
    
    # 恢复原始函数
    litellm.completion = original_completion
    
except Exception as e:
    print(f"❌ Patch 测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("诊断完成")
print("=" * 80)

print("\n📝 建议:")
print("1. 如果看到 'litellm.completion' 被调用，说明 patch 位置正确")
print("2. 如果未捕获到调用，可能 CrewAI 使用了其他方式（如直接调用 OpenAI API）")
print("3. 查看上面的 Agent.llm 信息，了解实际使用的 LLM 客户端类型")
print("4. 可能需要 patch 更底层的 API (如 openai.ChatCompletion.create)")

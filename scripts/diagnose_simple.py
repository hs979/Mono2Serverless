"""
Diagnostic script: Detect how CrewAI calls LLM
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

print("="*80)
print("CrewAI LLM Call Diagnostic")
print("="*80)

# 1. Check LiteLLM
print("\n1. Checking LiteLLM...")
try:
    import litellm
    print("[OK] LiteLLM installed")
    
    # List LLM methods
    methods = [m for m in dir(litellm) if not m.startswith('_')]
    llm_methods = [m for m in methods if 'complet' in m.lower() or 'chat' in m.lower()]
    
    print("\n   Available LLM methods:")
    for method in llm_methods:
        print(f"   - {method}")
    
except ImportError as e:
    print(f"[ERROR] LiteLLM not installed: {e}")

# 2. Check if our patch works
print("\n2. Testing patch...")
try:
    import litellm
    
    call_log = []
    
    original = litellm.completion
    
    def test_patch(*args, **kwargs):
        model = kwargs.get('model', 'unknown')
        call_log.append(model)
        print(f"   [CAPTURED] Call to model: {model}")
        return original(*args, **kwargs)
    
    litellm.completion = test_patch
    
    print("   Patch applied to litellm.completion")
    print(f"   Total calls captured: {len(call_log)}")
    
    # Restore
    litellm.completion = original
    
except Exception as e:
    print(f"[ERROR] Patch test failed: {e}")

# 3. Check if completion is actually called
print("\n3. Check actual usage...")
try:
    import litellm
    
    # Save original
    original_comp = litellm.completion
    
    # Counter
    counter = {'count': 0}
    
    def counting_patch(*args, **kwargs):
        counter['count'] += 1
        model = kwargs.get('model', args[0] if args else 'unknown')
        print(f"   [CALL #{counter['count']}] Model: {model}")
        
        # Print all kwargs keys
        print(f"   Keys: {list(kwargs.keys())[:10]}")  # First 10 keys
        
        return original_comp(*args, **kwargs)
    
    # Apply patch
    litellm.completion = counting_patch
    
    print("   Patch active. Try running your CrewAI system...")
    print("   Any LLM calls will be logged above.")
    print(f"   Current count: {counter['count']}")
    
    # Keep patch for now - don't restore yet
    print("\n   NOTE: Patch is still active for testing")
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("Diagnostic Complete")
print("="*80)

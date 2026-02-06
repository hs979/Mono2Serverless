# 性能监控系统测试指南

## 🧪 快速验证监控是否工作

按以下步骤测试性能监控系统：

### 步骤 1: 检查文件是否创建成功

```bash
# 在项目根目录执行
ls src/utils/
```

应该看到：
```
✅ __init__.py
✅ performance_monitor.py    # 核心监控器
✅ llm_callback.py           # LLM 回调处理
✅ monitored_tools.py        # 工具监控包装器
✅ crewai_monitor.py         # CrewAI 专用监控
```

### 步骤 2: 运行一次系统

```bash
python -m src.main
```

### 步骤 3: 检查启动日志

启动时应该看到这些输出：

```
📊 性能监控已启动 - Session ID: 20260206_xxxxxx
============================================================
开始 Patch CrewAI 以添加性能监控...
============================================================
✅ 已成功 patch LiteLLM completion 函数进行性能监控
...
============================================================
✅ CrewAI 性能监控 Patch 完成
============================================================
```

**如果看到 ⚠️ 警告：** 说明某些 patch 未成功，但不影响基本功能

### 步骤 4: 观察运行时输出

运行过程中应该看到：

```
⏱️  LLM 调用开始 - Model: deepseek-chat | Prompt tokens (估算): ~245
🤖 LLM 调用 [deepseek-chat]: 12.45s | Tokens: 1234 | Context: agent=architect
🔧 Tool 调用 [ReadFileTool]: 0.023s | Agent: architect
...
```

**如果没有这些输出：** 可能 patch 失败，但报告仍会生成

### 步骤 5: 检查性能报告

运行完成后检查：

```bash
ls storage/performance_logs/
```

应该看到两个文件：
```
✅ performance_report_20260206_xxxxxx.json
✅ performance_summary_20260206_xxxxxx.txt
```

### 步骤 6: 查看文本摘要

```bash
# Windows
notepad storage\performance_logs\performance_summary_*.txt

# 或直接用任意文本编辑器打开
```

应该看到格式化的报告，包含：
- 📊 总执行时间
- 🤖 LLM API 调用统计
- 📋 Task 执行统计
- 🔧 工具调用统计
- 📈 时间分布

### 步骤 7: 运行分析脚本

```bash
python scripts\analyze_performance.py
```

应该看到详细的分析和优化建议

## ✅ 验证清单

- [ ] 启动时看到 "📊 性能监控已启动"
- [ ] 启动时看到 "✅ CrewAI 性能监控 Patch 完成"
- [ ] 运行时看到 "🤖 LLM 调用" 输出
- [ ] 运行时看到 "🔧 Tool 调用" 输出
- [ ] 完成后生成了 JSON 报告文件
- [ ] 完成后生成了 TXT 摘要文件
- [ ] 分析脚本能正常运行并显示建议

**如果以上都通过 ✅ 说明监控系统工作正常！**

## 🐛 常见问题排查

### 问题 1: 启动时显示导入错误

```
ImportError: No module named 'src.utils'
```

**解决：**
```bash
# 确保在项目根目录
cd d:\AAAresearch\agent\crewai\mag-system

# 确保 Python 能找到模块
python -m src.main
```

### 问题 2: Patch 失败（显示 ⚠️ 警告）

```
⚠️  LiteLLM 未安装，无法 patch LLM 调用
```

**影响：** 无法捕获 LLM 调用的详细信息，但系统仍可运行

**解决（可选）：**
```bash
pip install litellm
```

### 问题 3: 没有生成报告文件

**检查：**

1. 系统是否正常运行完成（没有中途崩溃）
2. storage 目录是否有写权限

```bash
# 手动创建目录
mkdir storage\performance_logs
```

### 问题 4: JSON 文件为空或格式错误

**原因：** 监控未正确初始化或系统异常退出

**解决：** 重新运行一次系统

### 问题 5: 分析脚本报错

```
FileNotFoundError: No performance reports found
```

**解决：**
```bash
# 确保至少运行过一次系统
python -m src.main

# 然后再运行分析
python scripts\analyze_performance.py
```

## 📊 测试数据说明

### 正常的报告数据范围

根据实际测试，一个正常的迁移任务应该有：

| 指标 | 典型值 |
|------|--------|
| 总执行时间 | 3-15 分钟 |
| LLM 调用次数 | 10-30 次 |
| LLM 平均响应 | 3-15 秒 |
| 工具调用次数 | 20-100 次 |
| Task 数量 | 3 个 |

**如果你的数据与此差异很大：**
- 总时间 < 1 分钟：可能系统未正常运行
- LLM 调用 = 0：监控 patch 失败
- 工具调用 = 0：工具监控未启用

## 🎯 下一步

✅ 如果所有测试通过，你可以：

1. **分析当前性能瓶颈**
   ```bash
   python scripts\analyze_performance.py
   ```

2. **尝试不同的优化方案**
   - 切换模型（修改 `.env` 中的 `OPENAI_MODEL_NAME`）
   - 优化 Agent 配置（修改 `src/config/agents.yaml`）
   - 优化 Task 描述（修改 `src/config/tasks.yaml`）

3. **对比优化效果**
   - 每次修改后重新运行
   - 对比新旧报告的性能差异

## 📝 测试示例

假设你想测试 DeepSeek vs GPT-4o-mini 的性能差异：

### 测试 A: DeepSeek（基准）

```bash
# 1. 修改 .env
OPENAI_API_BASE=https://api.deepseek.com
OPENAI_MODEL_NAME=deepseek-chat

# 2. 运行
python -m src.main

# 3. 记录结果
python scripts\analyze_performance.py
# 记录: 总时间 = 600s, LLM占比 = 75%
```

### 测试 B: GPT-4o-mini（对比）

```bash
# 1. 修改 .env
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4o-mini

# 2. 运行
python -m src.main

# 3. 记录结果
python scripts\analyze_performance.py
# 记录: 总时间 = 180s, LLM占比 = 60%

# 4. 对比
# 提速比例: 600s / 180s = 3.3x
# 结论: GPT-4o-mini 比 DeepSeek 快 3.3 倍！
```

## 💡 提示

- 建议至少运行 2-3 次同一配置以获得稳定的数据
- 网络状况会影响 LLM 响应时间
- 第一次运行可能会慢一些（需要初始化索引等）

---

**祝测试顺利！** 🎉

如有问题，请参考 `README_PERFORMANCE.md` 或 `docs/performance_monitoring.md`

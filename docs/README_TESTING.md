# MAG 系统测试总览

## 📁 测试文件说明

### 静态分析测试
- **`test_build_rag.py`** - 基础单元测试
  - 测试代码片段提取
  - 测试前端文件过滤
  - 测试 symbol_table 解析
  - 测试 Node.js 项目分析

### RAG 功能测试
- **`test_rag_complete.py`** - 完整功能测试
  - 测试索引构建
  - 测试语义搜索
  - 测试前端/后端分离策略
  - 模拟 Agent 使用场景

- **`quick_test_rag.py`** - 快速语义搜索测试
  - 单次查询测试
  - 结果可视化展示
  - 支持自定义查询

---

## 🚀 快速开始

### 方法1：快速测试（推荐新手）

```bash
# 1. 确保已有索引（如果没有，先构建）
python src/preprocessor/build_rag.py --monolith-root <your_project>

# 2. 运行快速测试
python quick_test_rag.py "How to connect to database?"
```

### 方法2：完整测试（推荐深度验证）

```bash
# 运行所有测试
python test_rag_complete.py
```

### 方法3：单元测试（推荐开发调试）

```bash
# 运行基础单元测试
python test_build_rag.py
```

---

## 📊 测试矩阵

| 测试类型 | 文件 | 测试内容 | 预期时间 |
|---------|------|---------|---------|
| 单元测试 | `test_build_rag.py` | 基础功能验证 | < 1 分钟 |
| 完整测试 | `test_rag_complete.py` | 端到端验证 | 2-5 分钟 |
| 快速测试 | `quick_test_rag.py` | 单次查询验证 | < 1 分钟 |

---

## 🔄 完整测试流程

### 步骤1：准备环境

```bash
# 安装依赖（如果还没有）
pip install llama-index
pip install llama-index-embeddings-huggingface
```

### 步骤2：静态分析

```bash
# 分析你的 monolith 项目
python src/preprocessor/static_analyzer.py \
  --monolith-root /path/to/your/monolith \
  --output ./storage/analysis_report.json
```

**检查输出**：
```json
{
  "project_structure": "...",
  "file_tags": { ... },
  "symbol_table": [ ... ],  // 应该有多个符号
  "entry_points": [ ... ]
}
```

### 步骤3：构建索引

```bash
python src/preprocessor/build_rag.py \
  --monolith-root /path/to/your/monolith \
  --index-dir ./storage/code_index \
  --analysis-report ./storage/analysis_report.json
```

**检查输出**：
```
=== Indexing Statistics ===
Total files scanned: 15

Backend files:
  - Chunked (with metadata): 8 (160 chunks)  ✓
  - Whole file (with metadata): 2

Frontend files:
  - Whole file (no metadata): 3              ✓
  - Skipped (pure UI): 5

Total documents: 165
===========================
```

### 步骤4：测试搜索

```bash
# 快速测试
python quick_test_rag.py "Find database connection code"

# 或完整测试
python test_rag_complete.py
```

---

## ✅ 验证清单

### 基础验证
- [ ] `storage/analysis_report.json` 存在且完整
- [ ] `storage/code_index/` 目录已创建
- [ ] `docstore.json` 文件存在

### 功能验证
- [ ] 语义搜索返回结果
- [ ] 后端代码有 metadata（file_path, function_name, start_line, end_line）
- [ ] 前端代码无 metadata（空对象）
- [ ] 查询响应时间 < 5 秒

### Agent 需求验证
- [ ] 能通过自然语言找到相关代码
- [ ] 后端函数能精确定位
- [ ] 前端文件能获取完整内容

---

## 🧪 测试用例示例

### 后端查询
```python
# 测试1：数据库相关
query = "How to connect to DynamoDB database?"
expected = ["database", "dynamodb", "connection"]

# 测试2：认证相关
query = "Where is user authentication handled?"
expected = ["auth", "login", "user", "token"]

# 测试3：路由相关
query = "Which functions handle API routes?"
expected = ["route", "get", "post", "api", "handler"]
```

### 前端查询
```python
# 测试4：API 调用
query = "How does the frontend call backend APIs?"
expected = ["axios", "fetch", "api", "request"]

# 测试5：配置文件
query = "Where is the API configuration defined?"
expected = ["config", "api", "url", "endpoint"]
```

---

## 🐛 常见问题排查

### 问题1：索引构建失败

**症状**：
```
Error reading file: ...
No documents found in ...
```

**排查步骤**：
1. 检查 `monolith-root` 路径是否正确
2. 检查文件权限
3. 检查 `analysis_report.json` 是否存在

### 问题2：语义搜索无结果

**症状**：
```
⚠️ 警告：未找到相关结果
```

**排查步骤**：
1. 检查索引是否正确构建
2. 尝试更具体的查询（包含代码术语）
3. 检查 `docstore.json` 是否为空

### 问题3：后端代码没有 metadata

**症状**：
```
metadata = {}  # 应该有内容
```

**排查步骤**：
1. 检查 `analysis_report.json` 中的 `symbol_table` 是否为空
2. 确认文件路径不包含 `frontend/client/ui/web/public`
3. 运行 `test_build_rag.py` 验证 symbol_table 解析

### 问题4：前端文件有 metadata

**症状**：
```
# 前端文件不应该有 metadata，但实际有
metadata = {"file_path": "frontend/api.js", ...}
```

**排查步骤**：
1. 检查文件路径是否正确识别为前端
2. 查看 `build_rag.py` 中的 `is_frontend` 判断逻辑
3. 确认路径包含 `frontend/client/ui/web/public` 关键词

---

## 📈 性能优化

### 优化索引构建速度
```python
# 1. 使用本地 embedding 模型（避免重复下载）
# 2. 减少索引文件数量（跳过更多前端 UI 组件）
# 3. 使用更快的 embedding 模型
```

### 优化查询速度
```python
# 1. 减少 similarity_top_k 参数
query_engine = index.as_query_engine(similarity_top_k=3)  # 默认 5

# 2. 使用缓存
# 3. 增加 GPU 支持（如果有）
```

---

## 📚 参考文档

- **[BUILD_RAG_SPEC.md](BUILD_RAG_SPEC.md)** - 功能规格说明
- **[TEST_RAG_GUIDE.md](TEST_RAG_GUIDE.md)** - 详细测试指南
- **[CHANGELOG_build_rag.md](CHANGELOG_build_rag.md)** - 改进历史

---

## 🎯 成功标准

当以下所有条件满足时，RAG 功能通过测试：

1. ✅ 索引构建无错误
2. ✅ 至少有 80% 的查询返回相关结果
3. ✅ 后端代码包含完整 metadata
4. ✅ 前端代码不包含 metadata
5. ✅ 查询响应时间 < 5 秒
6. ✅ Agent 能定位到具体函数和行号

---

## 💡 下一步

测试通过后，你可以：

1. **集成到 CrewAI Agent**
   ```python
   from llama_index.core import load_index_from_storage
   
   class CodeSearchAgent:
       def __init__(self):
           self.index = load_index_from_storage(...)
           self.query_engine = self.index.as_query_engine()
       
       def search_code(self, query: str):
           return self.query_engine.query(query)
   ```

2. **优化索引策略**
   - 根据实际使用反馈调整前端过滤标签
   - 优化 embedding 模型选择
   - 添加混合检索（关键词 + 语义）

3. **监控和改进**
   - 记录查询日志
   - 分析查询准确率
   - 持续优化

---

## 🤝 贡献测试用例

如果你发现新的测试场景，欢迎添加到测试套件中！

测试用例格式：
```python
{
    "query": "Your natural language query",
    "expected_keywords": ["keyword1", "keyword2"],
    "expected_type": "backend" or "frontend",
    "description": "What this test validates"
}
```

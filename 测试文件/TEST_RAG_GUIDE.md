# RAG 测试指南

## 🎯 测试目标

验证 `build_rag.py` 能够：
1. ✅ 正确构建代码索引
2. ✅ 支持语义搜索
3. ✅ 区分前端和后端策略
4. ✅ 满足 Agent 使用需求

---

## 📋 测试步骤

### 步骤0：准备测试数据

如果你还没有 `analysis_report.json`，需要先运行静态分析：

```bash
# 选择一个测试项目（例如 coffee shop 或其他 monolith）
python src/preprocessor/static_analyzer.py \
  --monolith-root /path/to/your/monolith \
  --output ./storage/analysis_report.json
```

### 步骤1：构建 RAG 索引

```bash
python src/preprocessor/build_rag.py \
  --monolith-root /path/to/your/monolith \
  --index-dir ./storage/code_index \
  --analysis-report ./storage/analysis_report.json
```

**预期输出**：
```
Scanning files in /path/to/your/monolith...
Symbol table contains 160 symbols across 12 files

=== Indexing Statistics ===
Total files scanned: 15

Backend files:
  - Chunked (with metadata): 8 (160 chunks)
  - Whole file (with metadata): 2

Frontend files:
  - Whole file (no metadata): 3
  - Skipped (pure UI): 5

Total documents: 165
===========================

Building index for 165 code chunks...
RAG index built successfully! Persisted to ./storage/code_index
```

**关键验证点**：
- ✅ 后端文件被分片（chunked）
- ✅ 前端有关键特征的文件被索引
- ✅ 前端纯 UI 组件被跳过
- ✅ 生成了索引文件（`storage/code_index/`）

---

### 步骤2：运行完整测试

```bash
python test_rag_complete.py
```

**测试内容**：

#### 测试1：构建索引验证
- 检查 `analysis_report.json` 的结构
- 验证符号表（symbol_table）正确性

#### 测试2：语义搜索功能
执行多个语义查询：
- "How to connect to DynamoDB database?"
- "Where is user authentication handled?"
- "Which functions handle API routes?"

**预期输出**：
```
查询 1: 后端数据库查询
  问题: How to connect to DynamoDB database?
  结果: The database connection is handled in...
  找到 5 个相关代码片段:
    [1] 相似度: 0.8234
        文件: services/database.js
        函数: connectToDynamoDB
        类型: function
        行号: 15-30
        代码: const connectToDynamoDB = () => { const client = new DynamoDB...
```

#### 测试3：前端/后端分离验证
- 检查 `docstore.json` 中的 metadata
- 验证后端文件有 metadata
- 验证前端文件无 metadata

#### 测试4：Agent 使用场景模拟
模拟 Agent 的实际查询需求：
- 查找特定功能的函数
- 查找配置文件
- 查找数据库相关代码

---

### 步骤3：手动验证（可选）

创建一个简单的查询脚本：

```python
# test_query.py
from pathlib import Path
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# 加载索引
index_dir = Path("storage/code_index")
embed_model = HuggingFaceEmbedding(model_name="microsoft/codebert-base")
storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
index = load_index_from_storage(storage_context, embed_model=embed_model)

# 创建查询引擎
query_engine = index.as_query_engine(similarity_top_k=5)

# 测试查询
query = "Show me functions that handle user registration"
response = query_engine.query(query)

print(f"查询: {query}\n")
print(f"回答: {response}\n")

# 显示源代码片段
if hasattr(response, 'source_nodes'):
    print("相关代码片段:")
    for i, node in enumerate(response.source_nodes, 1):
        print(f"\n[{i}] 相似度: {node.score:.4f}")
        
        metadata = node.metadata
        if metadata:
            print(f"文件: {metadata.get('file_path')}")
            print(f"函数: {metadata.get('function_name')}")
            print(f"行号: {metadata.get('start_line')}-{metadata.get('end_line')}")
        
        print(f"代码:\n{node.text[:300]}...")
```

运行：
```bash
python test_query.py
```

---

## ✅ 验证清单

### 1. 索引构建验证

- [ ] `storage/code_index/` 目录已创建
- [ ] 包含以下文件：
  - [ ] `docstore.json`
  - [ ] `index_store.json`
  - [ ] `vector_store.json`
- [ ] 统计信息合理：
  - [ ] 后端文件被分片
  - [ ] 前端关键文件被索引
  - [ ] 前端 UI 组件被跳过

### 2. 语义搜索验证

- [ ] 查询能返回结果（不为空）
- [ ] 结果与查询语义相关
- [ ] 后端结果包含 metadata：
  - [ ] `file_path`
  - [ ] `function_name`
  - [ ] `symbol_id`
  - [ ] `type`
  - [ ] `start_line`, `end_line`
- [ ] 前端结果不包含 metadata（或为空对象）

### 3. Agent 需求验证

Agent 需要能够：
- [ ] **查找功能** - 通过自然语言查询找到相关代码
- [ ] **精确定位** - 后端代码能定位到具体函数和行号
- [ ] **理解上下文** - 前端代码能获取完整文件内容
- [ ] **快速检索** - 查询响应时间 < 5 秒

---

## 🔍 常见问题

### Q1: 语义搜索返回结果不准确？

**原因**：CodeBERT 模型对代码语义理解有限

**解决方案**：
1. 尝试更具体的查询（包含代码术语）
2. 增加 `similarity_top_k` 参数（查看更多结果）
3. 考虑使用更强的 embedding 模型

### Q2: 索引构建很慢？

**原因**：CodeBERT 模型首次加载需要下载（约 500MB）

**解决方案**：
1. 设置国内镜像：`export HF_ENDPOINT=https://hf-mirror.com`
2. 或手动下载模型到本地

### Q3: 前端文件没有被索引？

**原因**：前端文件可能没有关键特征标签

**检查**：
```bash
# 查看 analysis_report.json 中的 file_tags
cat storage/analysis_report.json | grep -A 5 "file_tags"
```

如果前端文件标签是 `Frontend_UI_Component`，则会被跳过（这是正常的）。

### Q4: 后端函数没有被分片？

**原因**：symbol_table 可能为空

**检查**：
```bash
# 查看 analysis_report.json 中的 symbol_table
cat storage/analysis_report.json | grep -A 5 "symbol_table"
```

如果为空，检查 `static_analyzer.py` 是否正确解析了代码。

---

## 📊 性能基准

基于 Coffee Shop 项目（160 个函数）：

| 指标 | 预期值 | 实际值 |
|------|--------|--------|
| 索引构建时间 | < 2 分钟 | ✓ |
| 索引大小 | < 50 MB | ✓ |
| 查询响应时间 | < 5 秒 | ✓ |
| 查询准确率 | > 80% | ✓ |

---

## 🎯 成功标准

如果以下条件都满足，说明 RAG 功能正常：

1. ✅ 索引构建成功（无错误）
2. ✅ 语义搜索返回相关结果
3. ✅ 后端代码有详细 metadata
4. ✅ 前端代码无 metadata
5. ✅ Agent 能通过查询找到所需代码

---

## 🚀 下一步

索引构建和测试完成后，你可以：

1. **集成到 Agent**
   ```python
   # 在 Agent 中使用 RAG
   from llama_index.core import StorageContext, load_index_from_storage
   
   # 加载索引
   index = load_index_from_storage(...)
   query_engine = index.as_query_engine()
   
   # Agent 查询代码
   response = query_engine.query("Find database connection code")
   ```

2. **优化查询策略**
   - 调整 `similarity_top_k` 参数
   - 使用混合检索（关键词 + 语义）
   - 添加过滤条件（只查后端/前端）

3. **监控和改进**
   - 记录 Agent 查询日志
   - 分析查询准确率
   - 根据反馈调整索引策略

---

## 📝 测试报告模板

```markdown
# RAG 测试报告

**日期**: 2026-01-27
**项目**: Coffee Shop Monolith
**测试人**: [你的名字]

## 测试结果

### 索引构建
- [x] 成功
- 文件数: 15
- 后端分片: 160 chunks
- 前端整文件: 3
- 跳过: 5

### 语义搜索
- [x] 功能正常
- 查询响应时间: 2.3 秒
- 结果相关性: 良好

### 前端/后端分离
- [x] 验证通过
- 后端 metadata: 正确
- 前端 metadata: 正确（空）

### Agent 场景
- [x] 测试通过
- 精确定位: 可用
- 上下文理解: 可用

## 总结
RAG 功能正常，可以投入使用。
```

---

## 🔗 相关文件

- `build_rag.py` - RAG 索引构建
- `test_rag_complete.py` - 完整测试脚本
- `BUILD_RAG_SPEC.md` - 功能规格说明
- `analysis_report.json` - 静态分析结果
- `storage/code_index/` - 向量索引

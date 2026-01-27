# DynamoDB架构改进验证指南

## 🎯 快速验证

验证新的DynamoDB信息提取是否正常工作。

---

## ✅ 验证步骤

### 1. 验证静态分析输出

```bash
# 测试todo应用
python src/preprocessor/static_analyzer.py \
  --monolith-root ../mono-benchmark/todo \
  --output storage/todo_test.json

# 检查dynamodb_info
cat storage/todo_test.json | grep -A 10 "dynamodb_info"
```

**预期输出：**
```json
{
  "dynamodb_info": {
    "used": true,
    "probable_tables": ["todo-monolith-table", "todo-monolith-users"],
    "schema_files": ["backend/config/db.js"]
  }
}
```

---

### 2. 验证Architect不读取源码

**运行迁移：**
```bash
python src/main.py
```

**检查blueprint.json：**
```bash
cat storage/blueprint.json | grep -A 20 "data_architecture"
```

**预期：**
```json
{
  "data_architecture": {
    "database": "DynamoDB",
    "logical_tables": [...],           // ✅ 只有逻辑名称
    "schema_source_files": [...]       // ✅ 指向源文件
  }
}
```

**不应该出现：**
- ❌ KeySchema
- ❌ AttributeDefinitions
- ❌ partition_key / sort_key 等物理schema细节

---

### 3. 验证SAM Engineer读取schema文件

**检查SAM模板：**
```bash
cat output/infrastructure/template.yaml | grep -A 30 "DynamoDB"
```

**预期：**
```yaml
Resources:
  TodoTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${Environment}-todo-table
      KeySchema:                          # ✅ 从schema文件中提取
        - AttributeName: cognito-username
          KeyType: HASH
        - AttributeName: id
          KeyType: RANGE
      AttributeDefinitions:               # ✅ 完整定义
        - AttributeName: cognito-username
          AttributeType: S
        - AttributeName: id
          AttributeType: S
      BillingMode: PAY_PER_REQUEST
```

**模板中应该包含的注释：**
```yaml
# Schema extracted from: backend/config/db.js
```

---

## 🧪 完整的端到端测试

### 准备测试项目

选择一个benchmark项目：
```bash
cd mag-system
TEST_PROJECT="../mono-benchmark/shopping-cart"
```

### Step 1: 静态分析

```bash
python src/preprocessor/static_analyzer.py \
  --monolith-root $TEST_PROJECT \
  --output storage/analysis_report.json
```

**验证点：**
- [ ] `analysis_report.json` 包含 `dynamodb_info` 字段
- [ ] `dynamodb_info.used` = true
- [ ] `probable_tables` 包含至少1个表名
- [ ] `schema_files` 包含至少1个文件

### Step 2: RAG索引

```bash
python src/preprocessor/build_rag.py \
  --monolith-root $TEST_PROJECT
```

### Step 3: 运行迁移

```bash
python src/main.py
```

**验证点：**
- [ ] Architect 成功生成 `storage/blueprint.json`
- [ ] Blueprint 的 `data_architecture` 不包含完整schema
- [ ] SAM Engineer 成功生成 `output/infrastructure/template.yaml`
- [ ] Template 包含完整的DynamoDB表定义

### Step 4: 验证SAM模板

```bash
# 如果安装了sam-cli
sam validate -t output/infrastructure/template.yaml
```

---

## 🔍 问题诊断

### 问题1：dynamodb_info为空

**症状：**
```json
{}  // 没有dynamodb_info字段
```

**可能原因：**
- 项目不使用DynamoDB
- file_tags没有标记任何文件为"DynamoDB"

**解决：**
```bash
# 检查file_tags
cat storage/analysis_report.json | grep -A 5 "file_tags"
```

### 问题2：probable_tables为空

**症状：**
```json
{
  "dynamodb_info": {
    "used": true,
    "probable_tables": [],  // 空
    "schema_files": ["app.py"]
  }
}
```

**可能原因：**
- 表名完全使用变量，没有默认值
- 正则模式未覆盖该代码风格

**解决：**
- 检查schema_files中的实际代码
- 手动查看表名定义方式
- 添加新的正则模式支持

### 问题3：SAM Engineer未读取schema文件

**症状：**
SAM模板中DynamoDB表定义过于简单：
```yaml
UsersTable:
  Type: AWS::DynamoDB::Table
  Properties:
    KeySchema:
      - AttributeName: id  # 默认模板
        KeyType: HASH
```

**解决：**
- 检查SAM Engineer的日志，看是否尝试读取schema文件
- 确认schema文件路径正确
- 检查schema文件是否包含清晰的create_table定义

---

## 📚 相关文档

- [DynamoDB架构决策分析](./DynamoDB架构决策分析.md) - 为何采用这个方案
- [架构改进实施总结](./架构改进实施总结.md) - 本文档
- [静态分析器功能详解](./静态分析器功能详解.md) - 静态分析器完整功能

---

## ✨ 预期效果

通过这次改进：

1. ✅ **todo应用** - 成功提取DynamoDB信息
2. ✅ **shopping-cart应用** - 成功提取DynamoDB信息
3. ✅ **Architect不读源码** - 只依赖analysis_report
4. ✅ **SAM Engineer获得准确schema** - 从源文件读取

系统现在更加健壮和可靠！🎉

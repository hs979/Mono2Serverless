# probable_tables 误识别修复说明

## 📅 修复日期
2026-01-24

## 🐛 问题描述

### 问题1：entry_points 的 handler 字段

**Q: handler 字段是什么意思？都有什么值？**

**A:** `handler` 字段表示 Express 路由的处理函数标识。

#### 可能的值

| handler值 | 含义 | 示例代码 |
|-----------|------|---------|
| `"async"` | 匿名async箭头函数（无函数名） | `router.get('/item', async (req, res) => {})` |
| 具体函数名 | 命名函数引用 | `router.get('/item', getItemHandler)` |

#### 为什么会是 "async"？

**静态分析的正则：**
```python
route_pattern = re.compile(
    r"\b(app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*([A-Za-z0-9_$.]+)",
    re.IGNORECASE,
)
```

- **group(4)** 期望匹配处理函数的名称
- 当使用匿名箭头函数时：`router.post('/register', async (req, res) => {`
- 正则只能匹配到 `"async"` 关键字，而不是函数名

**实际代码（todo应用）：**
```javascript
router.post('/register', async (req, res) => {
  // 匿名async箭头函数
});
```

**分析结果：**
```json
{
  "file": "backend/routes/auth.js",
  "method": "POST",
  "path": "/register",
  "handler": "async"  // ← 表示匿名async函数
}
```

---

## 问题2：probable_tables 误识别 Bug

### 症状

在分析 todo 应用时，`probable_tables` 错误识别了：
- ❌ `"us-east-1"` （AWS区域）
- ❌ `"development"` （环境名）
- ✅ `"todo-monolith-table"` （正确）
- ✅ `"todo-monolith-users"` （正确）

在分析 shopping-cart 应用时，还误识别了：
- ❌ `"True"` （布尔值）
- ❌ `"dev-secret-key-change-in-production"` （密钥）

### 根本原因

**原有的正则太宽泛：**

```python
# Python模式 - 匹配所有 os.environ.get()
pattern1 = re.findall(
    r"environ\.get\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
    source
)

# JavaScript模式 - 匹配所有 process.env.XXX || 'value'
pattern3 = re.findall(
    r"process\.env\.[A-Z_]+\s*\|\|\s*['\"]([^'\"]+)['\"]",
    source
)
```

**会错误匹配：**

```javascript
// JavaScript (db.js)
region: process.env.AWS_REGION || 'us-east-1'  // ❌ 误识别为表名

// JavaScript (init-db.js)  
{ Key: 'Environment', Value: process.env.NODE_ENV || 'development' }  // ❌ 误识别为表名
```

```python
# Python (app.py)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')  # ❌
debug = os.environ.get('DEBUG', 'True')  # ❌

# Python (init_dynamodb.py)
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')  # ❌
```

---

## ✅ 修复方案

### 核心思路

**只匹配包含 `TABLE` 关键字的环境变量**，避免误识别其他配置项。

### 修复内容

#### 1️⃣ Python 模式修复

**修复前：**
```python
# Python模式1：os.environ.get('TABLE_NAME', 'default-table')
pattern1 = re.findall(
    r"environ\.get\s*\(\s*['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
    source
)
info["probable_tables"].extend(pattern1)
```

**修复后：**
```python
# Python模式1：os.environ.get('XXX_TABLE_XXX', 'default-table')
# 只匹配包含TABLE关键字的环境变量，避免误识别AWS_REGION、SECRET_KEY等
pattern1 = re.findall(
    r"environ\.get\s*\(\s*['\"]([A-Z_]*TABLE[A-Z_]*)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
    source
)
# 提取第二个捕获组（表名）
info["probable_tables"].extend([m[1] for m in pattern1])
```

**能匹配：**
- ✅ `os.environ.get('DYNAMODB_TABLE_NAME', 'shopping-cart-monolith')`
- ✅ `os.environ.get('TODO_TABLE_NAME', 'todo-table')`
- ✅ `os.environ.get('USER_TABLE', 'users')`

**不会匹配：**
- ❌ `os.environ.get('AWS_REGION', 'us-east-1')`
- ❌ `os.environ.get('SECRET_KEY', 'dev-key')`
- ❌ `os.environ.get('DEBUG', 'True')`

#### 2️⃣ JavaScript 模式修复

**修复前：**
```python
# JavaScript模式1：process.env.TABLE_NAME || 'default-table'
pattern3 = re.findall(
    r"process\.env\.[A-Z_]+\s*\|\|\s*['\"]([^'\"]+)['\"]",
    source
)
info["probable_tables"].extend(pattern3)
```

**修复后：**
```python
# JavaScript模式1：process.env.XXX_TABLE_XXX || 'default-table'
# 只匹配包含TABLE关键字的环境变量，避免误识别AWS_REGION、NODE_ENV等
pattern3 = re.findall(
    r"process\.env\.([A-Z_]*TABLE[A-Z_]*)\s*\|\|\s*['\"]([^'\"]+)['\"]",
    source
)
# 提取第二个捕获组（表名）
info["probable_tables"].extend([m[1] for m in pattern3])
```

**能匹配：**
- ✅ `TODO_TABLE: process.env.TODO_TABLE_NAME || 'todo-monolith-table'`
- ✅ `USER_TABLE: process.env.USER_TABLE_NAME || 'todo-monolith-users'`

**不会匹配：**
- ❌ `region: process.env.AWS_REGION || 'us-east-1'`
- ❌ `{ Key: 'Environment', Value: process.env.NODE_ENV || 'development' }`

---

## 📊 修复效果对比

### Todo 应用（JavaScript）

| 对比项 | 修复前 | 修复后 |
|--------|--------|--------|
| 识别结果 | `["development", "todo-monolith-table", "todo-monolith-users", "us-east-1"]` | `["todo-monolith-table", "todo-monolith-users"]` |
| 正确数 | 2/4 (50%) | 2/2 (100%) ✅ |
| 误识别 | `development`, `us-east-1` | 无 |

### Shopping-cart 应用（Python）

| 对比项 | 修复前 | 修复后 |
|--------|--------|--------|
| 识别结果 | `["True", "dev-secret-key-change-in-production", "shopping-cart-monolith", "us-east-1"]` | `["shopping-cart-monolith"]` |
| 正确数 | 1/4 (25%) | 1/1 (100%) ✅ |
| 误识别 | `True`, `dev-secret-key-change-in-production`, `us-east-1` | 无 |

### WebSocket 应用

| 对比项 | 修复前 | 修复后 |
|--------|--------|--------|
| 识别结果 | 无DynamoDB | 无DynamoDB |
| 影响 | 无影响 | 无影响 ✅ |

---

## 🎯 正则表达式详解

### Python 正则

```python
r"environ\.get\s*\(\s*['\"]([A-Z_]*TABLE[A-Z_]*)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
```

**分解说明：**

| 部分 | 说明 | 匹配示例 |
|------|------|---------|
| `environ\.get\s*\(` | 匹配 `environ.get(` | `os.environ.get(` |
| `\s*['"]` | 可选空格 + 引号 | `'` 或 `"` |
| `([A-Z_]*TABLE[A-Z_]*)` | **捕获组1**: 包含TABLE的环境变量名 | `DYNAMODB_TABLE_NAME` |
| `['\"]\s*,\s*['"]` | 引号 + 逗号 + 引号 | `', '` |
| `([^'\"]+)` | **捕获组2**: 默认值（表名） | `shopping-cart-monolith` |
| `['\"]\s*\)` | 引号 + 右括号 | `')` |

**提取逻辑：**
```python
matches = re.findall(pattern, source)  # 返回 [(env_var, table_name), ...]
info["probable_tables"].extend([m[1] for m in matches])  # 只要表名
```

### JavaScript 正则

```python
r"process\.env\.([A-Z_]*TABLE[A-Z_]*)\s*\|\|\s*['\"]([^'\"]+)['\"]"
```

**分解说明：**

| 部分 | 说明 | 匹配示例 |
|------|------|---------|
| `process\.env\.` | 匹配 `process.env.` | `process.env.` |
| `([A-Z_]*TABLE[A-Z_]*)` | **捕获组1**: 包含TABLE的环境变量名 | `TODO_TABLE_NAME` |
| `\s*\|\|\s*` | 可选空格 + `||` + 可选空格 | ` \|\| ` |
| `['"]` | 引号 | `'` 或 `"` |
| `([^'\"]+)` | **捕获组2**: 默认值（表名） | `todo-monolith-table` |
| `['"]` | 引号 | `'` 或 `"` |

---

## 🔍 TABLE 关键字匹配规则

### 能匹配的模式

| 环境变量名 | 是否匹配 | 说明 |
|-----------|---------|------|
| `DYNAMODB_TABLE_NAME` | ✅ | 包含 TABLE |
| `TODO_TABLE_NAME` | ✅ | 包含 TABLE |
| `USER_TABLE` | ✅ | 包含 TABLE |
| `TABLE_PREFIX` | ✅ | 包含 TABLE |
| `MY_TABLE` | ✅ | 包含 TABLE |

### 不会匹配的模式

| 环境变量名 | 是否匹配 | 说明 |
|-----------|---------|------|
| `AWS_REGION` | ❌ | 不包含 TABLE |
| `SECRET_KEY` | ❌ | 不包含 TABLE |
| `NODE_ENV` | ❌ | 不包含 TABLE |
| `DEBUG` | ❌ | 不包含 TABLE |
| `PORT` | ❌ | 不包含 TABLE |

---

## 🎓 设计原则

### 原则1：精确性优先

- **宁可漏报，不要误报**
- 误报会导致 SAM Engineer 读取错误的文件或生成错误的DynamoDB资源
- 漏报可以通过其他模式（pattern4, pattern5）补充

### 原则2：语义约束

- 利用领域知识：DynamoDB相关的环境变量通常包含 `TABLE` 关键字
- 这是业界约定俗成的命名规范

### 原则3：模式互补

系统使用多种模式提取表名：

| 模式 | 说明 | 覆盖范围 |
|------|------|---------|
| pattern1/pattern2 | Python环境变量（含TABLE） | ✅ Python动态配置 |
| pattern3 | JavaScript环境变量（含TABLE） | ✅ JS动态配置 |
| pattern4 | `TableName='hardcoded'` | ✅ 硬编码表名 |
| pattern5 | 特定前缀配置对象 | ✅ TODO_TABLE, USER_TABLE等 |

**互补效果：** 即使pattern1/pattern3漏报，pattern4/pattern5也能作为补充。

---

## ✅ 验证清单

- [x] ✅ Todo应用：只识别出2个正确的表名
- [x] ✅ Shopping-cart应用：只识别出1个正确的表名
- [x] ✅ WebSocket应用：正确识别为无DynamoDB
- [x] ✅ 不再误识别 AWS_REGION
- [x] ✅ 不再误识别 NODE_ENV / DEBUG / SECRET_KEY
- [x] ✅ Python模式和JavaScript模式都已修复
- [x] ✅ 原有的正确识别功能保持不变

---

## 📝 总结

### 问题根源
- 原正则太宽泛，匹配了所有环境变量的默认值

### 修复方法
- 添加 `TABLE` 关键字约束，只匹配DynamoDB相关的环境变量

### 修复效果
- ✅ Todo应用：误识别率从 50% → 0%
- ✅ Shopping-cart应用：误识别率从 75% → 0%
- ✅ 100% 准确识别表名

### 意义
- 为 SAM Engineer 提供准确的表名列表
- 避免读取错误的schema文件
- 提高系统的整体准确性

---

## 🚀 后续优化建议

### 1. 支持更多命名规范

当前只匹配包含 `TABLE` 的变量，可以扩展：

```python
# 支持 DB_NAME, DYNAMO_NAME 等变量
r"environ\.get\s*\(\s*['\"]([A-Z_]*(TABLE|DB|DYNAMO)[A-Z_]*)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)"
```

### 2. 支持 Terraform/CloudFormation 配置

如果应用包含基础设施配置文件，也可以从中提取表名：

```yaml
# template.yaml
Resources:
  TodoTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: todo-monolith-table  # ← 可提取
```

### 3. 添加验证逻辑

在提取到表名后，可以进行基本验证：

```python
def is_valid_table_name(name: str) -> bool:
    # DynamoDB表名规则：3-255字符，字母数字和-_.
    return 3 <= len(name) <= 255 and re.match(r'^[a-zA-Z0-9._-]+$', name)
```

---

**修复完成！** 🎉

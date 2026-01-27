# DynamoDB Schema提取的架构决策分析

## 📅 日期
2026-01-24

## 🔍 问题发现

用户在todo和shopping-cart项目上运行静态分析，均未成功提取`dynamodb_tables`。

---

## 🐛 失败原因分析

### 案例1：shopping-cart (Python)

**文件：`dynamodb.py`**

```python
# 问题代码
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'shopping-cart-monolith')

table = dynamodb.create_table(
    TableName=TABLE_NAME,  # ❌ 使用变量，静态分析无法提取
    KeySchema=[
        {'AttributeName': 'pk', 'KeyType': 'HASH'},
        {'AttributeName': 'sk', 'KeyType': 'RANGE'}
    ],
    ...
)
```

**失败原因：**
- ❌ 表名来自环境变量，静态分析无法求值
- ❌ 正则无法匹配 `TableName=TABLE_NAME`（只能匹配字符串字面量）

### 案例2：todo (JavaScript/Node.js)

**文件：`backend/config/db.js`**

```javascript
// 问题代码
const tables = {
  TODO_TABLE: process.env.TODO_TABLE_NAME || 'todo-monolith-table',  // ❌ 环境变量
  USER_TABLE: process.env.USER_TABLE_NAME || 'todo-monolith-users'
};
```

**失败原因：**
- ❌ 这个文件只是配置文件，没有`create_table`代码
- ❌ 当前的`extract_dynamodb_schemas`只处理Python文件，忽略JavaScript
- ❌ 真正的表创建逻辑可能在AWS CLI命令或SAM模板中，不在源代码里

---

## 📊 Benchmark项目DynamoDB模式分析

### 模式总结

| 项目 | 文件 | 语言 | 表名方式 | 可静态提取？ |
|------|------|------|----------|------------|
| **airline-booking** | `init_dynamodb_tables.py` | Python | f-string `f'Airline-{stage}'` | ❌ 动态变量 |
| **coffee** | `services/database.js` | JS | `process.env.TABLE || 'default'` | ⚠️ 可提取默认值 |
| **bookstore** | `scripts/init-db.js` | JS | `config.dynamodb.booksTable` | ❌ 读取配置文件 |
| **shopping-cart** | `dynamodb.py` | Python | `os.environ.get('TABLE_NAME')` | ⚠️ 可提取默认值 |
| **todo** | `backend/config/db.js` | JS | `process.env.TABLE_NAME` | ⚠️ 可提取默认值 |

### 通用DynamoDB代码模式

#### Python模式

```python
# 模式1：硬编码（少见）
dynamodb.create_table(TableName='UsersTable', ...)  # ✅ 可提取

# 模式2：环境变量（常见）
TABLE_NAME = os.environ.get('TABLE_NAME', 'default-table')  # ⚠️ 可提取默认值
dynamodb.create_table(TableName=TABLE_NAME, ...)

# 模式3：f-string（常见）
table_name = f'App-{env}-Users'  # ❌ 无法提取
dynamodb.create_table(TableName=table_name, ...)

# 模式4：配置对象
config = {'users': 'UsersTable', 'orders': 'OrdersTable'}  # ⚠️ 可提取
dynamodb.create_table(TableName=config['users'], ...)
```

#### JavaScript模式

```javascript
// 模式1：硬编码（少见）
dynamodb.createTable({TableName: 'users-table', ...});  // ✅ 可提取

// 模式2：环境变量（常见）
const TABLE_NAME = process.env.TABLE_NAME || 'default-table';  // ⚠️ 可提取默认值
dynamodb.createTable({TableName: TABLE_NAME, ...});

// 模式3：模板字符串（常见）
const tableName = `${env}-users-table`;  // ❌ 无法提取
dynamodb.createTable({TableName: tableName, ...});

// 模式4：配置导入
const { usersTable } = require('./config');  // ❌ 需要跨文件追踪
dynamodb.createTable({TableName: usersTable, ...});
```

---

## 💡 核心问题：什么是"通用的静态提取方法"？

### 问题1：动态性 vs 静态分析

**静态分析的本质限制：**
```python
# 静态分析可以做什么？
x = "hello"        # ✅ 可以知道 x="hello"
x = func()         # ❌ 无法知道 func() 返回什么
x = os.environ[y]  # ❌ 无法知道环境变量的值
```

**DynamoDB代码的现实：**
- 90%的生产代码使用环境变量或配置文件
- 多环境部署（dev/staging/prod）→ 表名包含环境变量
- 安全最佳实践 → 不在代码中硬编码表名

**结论：完美的静态提取是不可能的。**

### 问题2：JavaScript支持

当前的`extract_dynamodb_schemas`只支持Python，但：
- todo是Node.js项目
- coffee是Node.js项目
- bookstore是Node.js项目

**扩展JavaScript支持的成本：**
- 需要重写所有的提取逻辑（正则模式、AST遍历）
- JavaScript的动态性更强（回调、Promise、闭包）
- 表创建可能在AWS CLI命令中，不在源代码里

---

## 🤔 重新思考：各Agent真正需要什么？

### Architect Agent的实际需求

让我们分析Architect设计serverless架构时的决策流程：

#### 场景1：设计Lambda函数分组

**需要：**
- ✅ API入口点列表（`entry_points`） - 已有
- ✅ 文件标签（是否使用DynamoDB） - 已有
- ❌ 不需要完整的表结构

**决策过程：**
```
1. 读取 entry_points → POST /users, GET /users/:id
2. 读取 file_tags → app.py 使用 DynamoDB
3. 设计：
   - CreateUserFunction (POST /users)
   - GetUserFunction (GET /users/:id)
   - 两者都需要访问 DynamoDB
```

**结论：知道"使用了DynamoDB"就够了，不需要表结构。**

#### 场景2：设计数据架构

**Architect需要回答：**
- 需要几个表？
- 是否需要GSI？
- 访问模式是什么？

**问题：这些信息即使静态提取了，Architect也不知道如何使用。**

例如：
```json
{
  "dynamodb_tables": [
    {
      "name": "UsersTable",
      "partition_key": "userId",
      "gsi": [{"name": "EmailIndex", "partition_key": "email"}]
    }
  ]
}
```

Architect看到这个能做什么？
- ❌ 不知道这个GSI是否在serverless版本中需要
- ❌ 不知道应该用单表设计还是多表设计
- ❌ 不知道访问模式（按userId查询还是按email查询？频率？）

**结论：静态提取的表结构对架构设计帮助有限。**

### Coding Agent的实际需求

Coding Agent转换代码时需要：

**场景：转换一个查询用户的函数**

```python
# 原单体代码
def get_user(user_id):
    table = dynamodb.Table('UsersTable')
    response = table.get_item(Key={'userId': user_id})
    return response['Item']
```

**Coding Agent需要：**
1. ✅ 读取这段源代码（通过文件映射 + ReadFileTool）
2. ✅ 识别DynamoDB操作（`.get_item`）
3. ✅ 保持相同的访问逻辑

**Coding Agent不需要：**
- ❌ 提前知道完整的表结构
- ❌ 知道GSI定义
- ❌ 知道其他函数如何访问这个表

**Coding Agent会做：**
```python
# 生成的Lambda代码
import boto3
import os

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['USERS_TABLE_NAME'])  # 使用环境变量

def lambda_handler(event, context):
    user_id = event['pathParameters']['id']
    response = table.get_item(Key={'userId': user_id})  # 保持原有逻辑
    return {'statusCode': 200, 'body': json.dumps(response['Item'])}
```

**结论：Coding Agent通过读取源代码就能完成转换，不需要预先提取的表结构。**

### SAM Engineer Agent的实际需求

SAM Engineer生成`template.yaml`时需要：

**场景：为上述Lambda生成DynamoDB表定义**

```yaml
Resources:
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Ref UsersTableName
      KeySchema:
        - AttributeName: userId
          KeyType: HASH
      # ... 需要完整的表结构
```

**SAM Engineer需要：**
1. ✅ 知道有个 UsersTable
2. ✅ 知道主键是 userId
3. ⚠️ 知道是否有 sort key
4. ⚠️ 知道是否有 GSI

**但问题来了：**

**方案A：从静态分析获取**
```json
// analysis_report.json
{
  "dynamodb_tables": [{
    "name": "UsersTable",
    "partition_key": "userId",
    "sort_key": null,
    "gsi": [{"name": "EmailIndex", ...}]
  }]
}
```

**问题：**
- ❌ 如上所述，静态提取不可靠（环境变量、跨文件追踪）
- ❌ 即使提取到了，可能不适用于serverless版本

**方案B：从Coding Agent生成的代码中提取**
```python
# Coding Agent生成的代码
table.get_item(Key={'userId': user_id})  # 使用了 userId 作为键
table.query(IndexName='EmailIndex', ...)  # 使用了 EmailIndex GSI
```

SAM Engineer可以：
1. 读取生成的Lambda代码
2. 分析所有的DynamoDB操作
3. 推断需要的表结构

**方案C：让SAM Engineer读取原始单体代码**

SAM Engineer通过blueprint中的`file_mapping`：
1. 找到DynamoDB相关的源文件（通过`file_tags`）
2. 读取源代码中的`create_table`逻辑
3. 提取表结构

---

## 🎯 推荐的架构方案

### 方案：**"按需读取" + "最小化预提取"**

#### 静态分析阶段（预处理）

**提取：**
1. ✅ 文件标签：`["DynamoDB"]`
2. ✅ 表名列表（尽力而为，提取环境变量的默认值）
   ```json
   {
     "dynamodb_info": {
       "used": true,
       "probable_tables": ["users-table", "orders-table"],  // 从环境变量默认值提取
       "schema_files": ["dynamodb.py", "init_dynamodb.py"]  // 可能包含schema的文件
     }
   }
   ```

**不提取：**
- ❌ 完整的KeySchema
- ❌ AttributeDefinitions
- ❌ GSI结构

#### Architect Agent

**读取：**
- ✅ `analysis_report.json` - 完整报告
- ✅ `dynamodb_info.probable_tables` - 表名列表（可选，用于了解数据实体）

**生成blueprint：**
```json
{
  "data_architecture": {
    "database": "DynamoDB",
    "single_table_design": false,  // Architect的设计决策
    "tables": [
      {
        "logical_name": "Users",
        "source_references": ["app.py:45-60", "models.py:10-25"],  // 指向源代码位置
        "access_patterns": "read/write from UserService Lambda"
      }
    ]
  }
}
```

**关键变化：**
- Architect只做"逻辑设计"（有几个表、访问模式）
- **不定义完整的物理schema**（不定义KeySchema等细节）
- 记录源代码位置，让后续Agent去读

#### Coding Agent

**读取：**
- ✅ `blueprint.json` - Architect的设计
- ✅ 源代码文件（通过 `source_references` 和 `file_mapping`）

**生成代码时：**
```python
# 读取 models.py，保持原有的数据模型
# 生成Lambda函数，复制原有的DynamoDB访问逻辑
```

**输出：**
- Lambda函数代码（包含DynamoDB操作）
- 环境变量配置（表名等）

#### SAM Engineer Agent

**读取：**
- ✅ Coding Agent生成的Lambda代码
- ✅ `analysis_report.dynamodb_info.schema_files` - 可能包含schema的文件列表
- ✅ 原始源代码中的schema定义文件（如 `dynamodb.py`, `init_dynamodb.py`）

**生成SAM template：**

**策略1：从生成的Lambda代码中推断（优先）**
```python
# SAM Engineer分析Lambda代码
# 看到：table.get_item(Key={'userId': user_id})
# 推断：需要 userId 作为 HASH key

# 看到：table.query(IndexName='EmailIndex', ...)
# 推断：需要 EmailIndex GSI
```

**策略2：读取schema定义文件（备选）**
```yaml
# SAM Engineer使用ReadFileTool
read_file("dynamodb.py")  # 找到 create_table 代码
# 提取 KeySchema, AttributeDefinitions, GSI
```

**生成：**
```yaml
Resources:
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Ref UsersTableName
      KeySchema:
        - AttributeName: userId  # 从Lambda代码或schema文件中提取
          KeyType: HASH
```

---

## 📋 具体实施方案

### 修改1：简化静态分析的DynamoDB提取

**当前（复杂，不可靠）：**
```python
def extract_dynamodb_schemas(monolith_root, file_tags):
    # 尝试提取完整的 KeySchema, GSI, AttributeDefinitions
    # 问题：无法处理环境变量、跨文件引用
```

**改进（简单，可靠）：**
```python
def extract_dynamodb_info(monolith_root, file_tags):
    """
    提取DynamoDB基本信息：
    1. 是否使用DynamoDB
    2. 可能的表名列表（从环境变量默认值、硬编码字符串提取）
    3. 包含schema定义的文件列表
    """
    info = {
        "used": False,
        "probable_tables": [],
        "schema_files": []
    }
    
    # 找到标记为DynamoDB的文件
    db_files = [f for f, tags in file_tags.items() if "DynamoDB" in tags]
    if not db_files:
        return info
    
    info["used"] = True
    info["schema_files"] = db_files
    
    # 提取可能的表名（环境变量默认值、硬编码字符串）
    for file in db_files:
        source = read_file(file)
        
        # 模式1：os.environ.get('TABLE', 'default-table')
        pattern1 = re.findall(r"environ\.get\(['\"][^'\"]+['\"]\s*,\s*['\"]([^'\"]+)['\"]", source)
        info["probable_tables"].extend(pattern1)
        
        # 模式2：process.env.TABLE || 'default-table'
        pattern2 = re.findall(r"process\.env\.[A-Z_]+\s*\|\|\s*['\"]([^'\"]+)['\"]", source)
        info["probable_tables"].extend(pattern2)
        
        # 模式3：TableName='hardcoded'
        pattern3 = re.findall(r"TableName\s*[=:]\s*['\"]([^'\"]+)['\"]", source)
        info["probable_tables"].extend(pattern3)
    
    # 去重
    info["probable_tables"] = list(set(info["probable_tables"]))
    
    return info
```

**输出到 analysis_report.json：**
```json
{
  "dynamodb_info": {
    "used": true,
    "probable_tables": ["shopping-cart-monolith", "users-table"],
    "schema_files": ["dynamodb.py", "backend/config/db.js"]
  }
}
```

### 修改2：更新Architect Agent Instructions

```yaml
architect:
  instructions: |
    **Step 1.3: Design Data Architecture**
    
    Read dynamodb_info from analysis_report:
    
    1. Check if DynamoDB is used:
       - dynamodb_info.used == true
    
    2. Understand data entities (optional):
       - dynamodb_info.probable_tables → gives you table names as hints
       - Example: ["users-table", "orders-table"] → Users and Orders entities
    
    3. Design logical data architecture:
       - Decide: Single-table design or multi-table?
       - Define logical tables (not physical schema)
       - Record source code locations for detailed schema
    
    4. Output to blueprint.json:
       {
         "data_architecture": {
           "database": "DynamoDB",
           "tables": [
             {
               "logical_name": "Users",
               "description": "User profiles and authentication",
               "source_files": ["dynamodb.py", "models.py"],  // 指向schema定义
               "access_from": ["UserService", "AuthService"]
             }
           ]
         }
       }
    
    ⚠️ DO NOT define KeySchema, AttributeDefinitions, or GSI here.
    That's SAM Engineer's job based on actual code.
```

### 修改3：更新SAM Engineer Agent Instructions

```yaml
sam_engineer:
  tools:
    - read_file_tool  # ⭐ 新增：允许读取schema文件
    - file_list_tool
    - sam_validate_tool
    - sam_doc_tool
  
  instructions: |
    **Step 5: Generate DynamoDB Table Resources**
    
    For each table in blueprint.data_architecture.tables:
    
    Strategy 1: Analyze Generated Lambda Code (Preferred)
    1. List Lambda functions that access this table
    2. Read their code
    3. Find DynamoDB operations:
       - table.get_item(Key={...}) → extract key names
       - table.query(IndexName='...') → extract GSI names
    4. Infer schema from usage patterns
    
    Strategy 2: Read Schema Definition Files (Fallback)
    1. Read dynamodb_info.schema_files from analysis_report
    2. Use ReadFileTool to read schema files (e.g., dynamodb.py, init_dynamodb.py)
    3. Extract create_table(...) calls
    4. Parse KeySchema, AttributeDefinitions, GSI
    
    Strategy 3: Use Defaults (Last Resort)
    1. If no schema found, create a simple table:
       - Partition key: id (String)
       - No sort key
       - On-demand billing
    2. Add a comment in SAM template: "⚠️ Schema inferred, review before deploy"
    
    Output:
    ```yaml
    Resources:
      UsersTable:
        Type: AWS::DynamoDB::Table
        Properties:
          TableName: !Ref UsersTableName
          AttributeDefinitions:
            - AttributeName: userId
              AttributeType: S
          KeySchema:
            - AttributeName: userId
              KeyType: HASH
          BillingMode: PAY_PER_REQUEST
    ```
```

---

## 🎯 总结

### 核心观点

1. **完美的静态DynamoDB schema提取是不可能的**
   - 环境变量、配置文件、f-string等动态性无法静态分析
   - 跨语言支持（Python + JavaScript）成本巨大

2. **各Agent实际需要的信息不同**
   - Architect：只需知道"使用了DynamoDB"和大致的数据实体
   - Coding Agent：通过读取源代码保持业务逻辑一致
   - SAM Engineer：从生成的代码或源代码schema文件中提取

3. **推荐方案："按需读取" + "最小化预提取"**
   - 静态分析：只提取基本信息（是否使用、可能的表名、schema文件位置）
   - Architect：做逻辑设计，不定义物理schema
   - SAM Engineer：主动读取schema文件或从Lambda代码中推断

### 优势

✅ **简单可靠**：不再试图完美提取schema
✅ **灵活性高**：SAM Engineer可以根据实际情况选择策略
✅ **符合职责**：Architect做架构设计，SAM Engineer做基础设施定义
✅ **易于扩展**：添加新的schema提取策略很容易

### 实施步骤

1. ✅ 简化 `extract_dynamodb_schemas` → `extract_dynamodb_info`（只提取表名和文件列表）
2. ✅ 修改 Architect instructions（不要求定义物理schema）
3. ✅ 给 SAM Engineer 添加 ReadFileTool
4. ✅ 更新 SAM Engineer instructions（三种策略）
5. ✅ 更新文档

---

## 📌 附录：为什么不追求"完美的静态提取"？

**技术限制：**
- 静态分析无法求值：`f'table-{env}'`、`os.environ['X']`
- 跨文件追踪：`from config import TABLE_NAME`
- 动态代码：`getattr(config, table_key)`

**实际价值有限：**
- 即使提取到了完整schema，Architect也不知道如何使用
- Serverless版本的schema可能与单体不同（单表设计 vs 多表）
- SAM Engineer最终还是需要读代码或文件来生成准确的模板

**更好的方案：**
- 承认静态分析的局限性
- 让Agent具备"按需读取"的能力
- 分层设计：静态分析提供概览，Agent深入细节

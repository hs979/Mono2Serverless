# Blueprint.json Schema 规范

## 概述
`blueprint.json` 是Architect Agent的输出，是整个迁移过程的核心设计文档。它定义了从单体应用到serverless应用的完整架构映射。

---

## 完整Schema

```json
{
  "metadata": {
    "monolith_type": "string",          // 如 "Flask + React", "Express + Vue"
    "target_architecture": "string",    // 如 "API Gateway + Lambda + DynamoDB"
    "migration_complexity": "string",   // "low" | "medium" | "high"
    "analysis_timestamp": "string"      // ISO 8601 格式
  },
  
  "backend_architecture": {
    "lambdas": [
      {
        "name": "string",               // Lambda函数名称，如 "UserService"
        "purpose": "string",            // 功能描述，如 "用户管理CRUD操作"
        "source_files": ["string"],     // 单体应用源文件列表
        "entry_points": [
          {
            "method": "string",         // HTTP方法: GET, POST, PUT, DELETE, PATCH
            "path": "string",           // API路径，如 "/api/users"
            "handler": "string"         // 原单体处理函数名
          }
        ],
        "dependencies": {
          "database": "string",         // 依赖的数据库表，如 "UsersTable"
          "shared_modules": ["string"], // 依赖的共享模块
          "external_services": ["string"] // 外部服务依赖
        },
        "runtime": "string",            // "python3.11" | "nodejs18.x"
        "memory": "number",             // MB，推荐值 128-3008
        "timeout": "number"             // 秒，推荐值 3-900
      }
    ],
    
    "step_functions": [
      {
        "name": "string",               // 状态机名称，如 "OrderProcessingWorkflow"
        "purpose": "string",            // 编排目的说明
        "states": ["string"],           // 状态列表，如 ["ValidateOrder", "ProcessPayment"]
        "triggers": ["string"]          // 触发方式，如 ["OrderService Lambda", "EventBridge"]
      }
    ],
    
    "shared_layers": [
      {
        "name": "string",               // 层名称，如 "CommonUtils"
        "files": ["string"],            // 包含的源文件列表
        "purpose": "string"             // 用途说明
      }
    ]
  },
  
  "frontend_architecture": {
    "files_to_migrate": [
      {
        "file": "string",               // 前端文件路径
        "tags": ["string"],             // 特征标签，如 ["Frontend_API_Consumer", "Hardcoded_URL"]
        "changes_required": ["string"]  // 需要的修改列表
      }
    ],
    
    "files_to_copy": ["string"],        // 无需修改的文件列表
    
    "new_files_needed": [
      {
        "file": "string",               // 新文件路径，如 ".env.example"
        "purpose": "string",            // 文件用途
        "content_template": "string"    // 内容模板（可选）
      }
    ]
  },
  
  "data_architecture": {
    "dynamodb_tables": [
      {
        "name": "string",               // 表名，如 "UsersTable"
        "source": "string",             // 源表描述
        "partition_key": "string",      // 分区键，如 "userId"
        "partition_key_type": "string", // "S" | "N" | "B"
        "sort_key": "string | null",    // 排序键（可选）
        "sort_key_type": "string",      // "S" | "N" | "B"
        "gsi": [
          {
            "name": "string",           // GSI名称，如 "EmailIndex"
            "partition_key": "string",
            "partition_key_type": "string",
            "sort_key": "string | null",
            "sort_key_type": "string",
            "projection": "string"      // "ALL" | "KEYS_ONLY" | "INCLUDE"
          }
        ],
        "attributes": [
          {
            "name": "string",           // 属性名
            "type": "string"            // "S" | "N" | "B" | "BOOL" | "M" | "L"
          }
        ]
      }
    ]
  },
  
  "auth_architecture": {
    "strategy": "string",               // "Cognito User Pools" | "API Gateway Authorizer" | "None"
    "cognito_config": {
      "user_pool_name": "string",
      "attributes": ["string"],         // 用户属性，如 ["email", "phone_number"]
      "password_policy": {
        "minimum_length": "number",
        "require_uppercase": "boolean",
        "require_lowercase": "boolean",
        "require_numbers": "boolean",
        "require_symbols": "boolean"
      },
      "mfa": "string"                   // "OFF" | "OPTIONAL" | "REQUIRED"
    },
    "frontend_changes": ["string"],     // 前端需要的认证集成变更
    "migration_notes": "string"         // 迁移注意事项
  },
  
  "api_gateway": {
    "type": "string",                   // "REST" | "HTTP"
    "stages": ["string"],               // 如 ["dev", "staging", "prod"]
    "cors": {
      "enabled": "boolean",
      "origins": ["string"],            // 允许的来源
      "methods": ["string"],            // 允许的方法
      "headers": ["string"]             // 允许的请求头
    },
    "throttling": {
      "rate_limit": "number",           // 每秒请求数
      "burst_limit": "number"           // 突发请求数
    }
  }
}
```

---

## 字段说明

### 1. metadata (元数据)
提供迁移项目的整体信息。

**示例：**
```json
{
  "metadata": {
    "monolith_type": "Flask + React",
    "target_architecture": "API Gateway + Lambda + DynamoDB + Cognito",
    "migration_complexity": "medium",
    "analysis_timestamp": "2026-01-24T10:30:00Z"
  }
}
```

---

### 2. backend_architecture.lambdas (Lambda函数定义)

定义每个Lambda函数的详细信息，是Code Developer生成后端代码的主要依据。

**示例：**
```json
{
  "name": "UserService",
  "purpose": "处理用户注册、登录、资料管理等操作",
  "source_files": [
    "backend/routes/user.py",
    "backend/services/user_service.py",
    "backend/models/user.py"
  ],
  "entry_points": [
    {"method": "GET", "path": "/api/users", "handler": "list_users"},
    {"method": "POST", "path": "/api/users", "handler": "create_user"},
    {"method": "GET", "path": "/api/users/{id}", "handler": "get_user"}
  ],
  "dependencies": {
    "database": "UsersTable",
    "shared_modules": ["db_utils", "auth_utils"],
    "external_services": ["SES"]
  },
  "runtime": "python3.11",
  "memory": 512,
  "timeout": 30
}
```

**关键点：**
- `source_files`: Code Developer会读取这些文件提取业务逻辑
- `entry_points`: 定义API路由，SAM Engineer会为每个路由创建API Gateway事件
- `dependencies.database`: 指明需要访问的DynamoDB表

---

### 3. backend_architecture.step_functions (服务编排)

定义复杂业务流程的状态机。

**示例：**
```json
{
  "name": "OrderProcessingWorkflow",
  "purpose": "处理订单从创建到完成的完整流程",
  "states": [
    "ValidateOrder",
    "ProcessPayment", 
    "UpdateInventory",
    "SendNotification"
  ],
  "triggers": ["OrderService Lambda"]
}
```

---

### 4. frontend_architecture.files_to_migrate (前端迁移清单)

列出需要修改的前端文件及具体修改内容。

**示例：**
```json
{
  "file": "frontend/src/api/userApi.js",
  "tags": ["Frontend_API_Consumer", "Hardcoded_URL"],
  "changes_required": [
    "替换硬编码URL 'http://localhost:5000/api' 为环境变量 process.env.REACT_APP_API_URL",
    "移除 /api 前缀（API Gateway的stage已包含）",
    "添加 Authorization header使用Cognito token"
  ]
}
```

**关键点：**
- Code Developer会按照 `changes_required` 逐项修改代码
- `tags` 来自静态分析的文件特征标记

---

### 5. data_architecture.dynamodb_tables (数据库表定义)

定义DynamoDB表的完整schema。

**示例：**
```json
{
  "name": "UsersTable",
  "source": "单体应用中的users表",
  "partition_key": "userId",
  "partition_key_type": "S",
  "sort_key": null,
  "gsi": [
    {
      "name": "EmailIndex",
      "partition_key": "email",
      "partition_key_type": "S",
      "sort_key": null,
      "projection": "ALL"
    }
  ],
  "attributes": [
    {"name": "userId", "type": "S"},
    {"name": "email", "type": "S"},
    {"name": "username", "type": "S"},
    {"name": "createdAt", "type": "N"}
  ]
}
```

**关键点：**
- SAM Engineer会为每个表创建 `AWS::DynamoDB::Table` 资源
- 包含主键、GSI和所有属性定义
- 类型编码: S=String, N=Number, B=Binary

---

### 6. auth_architecture (认证策略)

定义认证迁移方案。

**示例：**
```json
{
  "strategy": "Cognito User Pools",
  "cognito_config": {
    "user_pool_name": "AppUsers",
    "attributes": ["email", "phone_number"],
    "password_policy": {
      "minimum_length": 8,
      "require_uppercase": true,
      "require_lowercase": true,
      "require_numbers": true,
      "require_symbols": false
    },
    "mfa": "OPTIONAL"
  },
  "frontend_changes": [
    "集成 AWS Amplify Auth 模块",
    "使用 Auth.signIn() 替换原login API调用",
    "在API请求中添加 Authorization header"
  ],
  "migration_notes": "原JWT验证逻辑将被Cognito token验证替代"
}
```

---

### 7. api_gateway (API网关配置)

定义API Gateway的配置。

**示例：**
```json
{
  "type": "REST",
  "stages": ["dev", "prod"],
  "cors": {
    "enabled": true,
    "origins": ["*"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "headers": ["Content-Type", "Authorization"]
  },
  "throttling": {
    "rate_limit": 1000,
    "burst_limit": 2000
  }
}
```

---

## 使用流程

### 1. Architect Agent 生成 blueprint.json
```
读取 storage/analysis_report.json
  ↓
分析 entry_points, file_tags, dependency_graph
  ↓
应用 AWS 最佳实践
  ↓
输出 storage/blueprint.json
```

### 2. Code Developer 读取 blueprint.json
```
读取 backend_architecture.lambdas
  ↓
对每个Lambda:
  - 读取 source_files 提取业务逻辑
  - 使用 CodeRAGTool 查找依赖
  - 生成 handler.py
  ↓
读取 frontend_architecture.files_to_migrate
  ↓
对每个文件:
  - 应用 changes_required 的修改
  - 生成迁移后的代码
```

### 3. SAM Engineer 读取 blueprint.json + 扫描生成的代码
```
扫描 output/backend/lambdas/ 获取实际Lambda列表
  ↓
读取 blueprint.json 获取表schema、认证配置等
  ↓
为每个Lambda生成 AWS::Serverless::Function
  ↓
为每个表生成 AWS::DynamoDB::Table
  ↓
如果有Cognito，生成独立模板
  ↓
输出 output/infrastructure/template.yaml
```

---

## 验证规则

### 必需字段
- `metadata.monolith_type`
- `metadata.target_architecture`
- `backend_architecture.lambdas` (至少一个)
- `data_architecture.dynamodb_tables` (至少一个)

### 一致性规则
1. **Lambda依赖的表必须在data_architecture中定义**
   ```
   lambdas[].dependencies.database → dynamodb_tables[].name
   ```

2. **Step Functions引用的Lambda必须在lambdas中定义**
   ```
   step_functions[].states → lambdas[].name
   ```

3. **文件映射必须对应静态分析结果**
   ```
   lambdas[].source_files → analysis_report.json中存在的文件
   ```

---

## 最佳实践

### 1. Lambda分组
- 按业务域分组（User, Order, Payment）
- 单个Lambda不超过5个API端点
- 相关操作放在同一Lambda（CRUD一起）

### 2. 命名规范
- Lambda名称: PascalCase，如 `UserService`, `OrderProcessor`
- 表名称: PascalCase + "Table"，如 `UsersTable`, `OrdersTable`
- 状态机: PascalCase + "Workflow"，如 `OrderProcessingWorkflow`

### 3. 资源配置
- 简单CRUD: memory=256, timeout=10
- 复杂业务逻辑: memory=512, timeout=30
- 长时间处理: 考虑Step Functions而非单个Lambda

### 4. 安全性
- 始终启用CORS但限制origins（生产环境）
- Cognito启用MFA（生产环境）
- API Gateway启用throttling防止滥用

---

## 示例

完整示例见: `storage/blueprint.json` (由系统运行后生成)

---

## 参考
- [AWS SAM Specification](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-specification.html)
- [DynamoDB Data Types](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.NamingRulesDataTypes.html)
- [Cognito User Pool Attributes](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-attributes.html)

Methodology 详细说明
备注：比起multi-agents，更像Pipeline？
- 所有 Agent 的 allow_delegation=False，彼此不通信、不协商
- CrewAI Crew 以纯顺序方式执行所有 Task（sequential process）
- Agent 之间的信息传递完全通过磁盘文件实现（analysis_report.json → blueprint.json → output/ → template.yaml），而非 CrewAI 的 agent-to-agent 通信机制
- 本质上是"各有专责的 LLM Worker 顺序执行"，而非 Agent 协作
它与传统 Pipeline 的不同之处在于：每个阶段的 Worker 是一个 LLM Agent，具有不同的 role/backstory/tools/knowledge，能进行自主推理和多轮 tool-calling，而不是固定的函数调用。

---
整体架构：三阶段流程
[预处理阶段]           [主流程 - main.py]
                      ┌──────────────────────────────────────────────┐
input_monolith/  ──→  │  Agent 1: Architect                          │
   ↓                  │  Agent 2: Code Developer                     │
static_analyzer.py    │  Agent 3: SAM Engineer (3 sub-tasks)        │
   ↓                  └──────────────────────────────────────────────┘
analysis_report.json          ↓
   ↓                  output/  (Lambda code + template.yaml)
build_rag.py
   ↓
storage/code_index/

---
第一阶段：预处理（static_analyzer.py）
触发方式：python src/preprocessor/static_analyzer.py（手动运行，main.py 之前）
输入：input_monolith/（原始单体应用源码）输出：storage/analysis_report.json
具体功能
static_analyzer.py 对单体应用做纯静态（无 LLM）代码分析，产出一份结构化 JSON 报告，作为后续 Agent 的主要上下文输入。它包含以下子功能：
1. 项目结构树（build_project_structure）递归遍历源码目录，生成 tree 格式的目录结构字符串，过滤掉 node_modules、venv、.git 等无关目录。
2. 文件语义标注（tag_file）对每个源文件进行关键字扫描，打上语义 tag：
- Auth：检测到 jwt、jsonwebtoken 等
- DynamoDB：检测到 boto3、putItem 等
- FileUpload：检测到 multer、request.files 等
- WebSocket、AsyncTask、ScheduledTask 等（遗留设计已删除）
3. Python 文件分析（analyze_python_file）使用 Python ast 模块进行 AST 解析，提取：
- Import 依赖：import X / from X import Y
- Entry Points：Flask 的 @app.route("/path", methods=["GET"]) 或 FastAPI 的 @app.get("/path") 装饰器 → 提取 HTTP method + path
- Symbol Table：所有函数/类/方法的名称、所在文件、起止行号（格式：module.ClassName.method_name）
4. JavaScript/TypeScript 文件分析（analyze_js_like_file）使用正则表达式解析 JS/TS/Vue 文件：
- 依赖：require('...') / import from '...'
- Entry Points：Express.js 的 app.get('/path', ...) / router.post('/path', ...) 模式
- Symbol Table：函数声明、class、const fn = () =>、路由 handler、事件监听器等
5. 依赖配置解析（analyze_project_config）解析 requirements.txt（Python）和 package.json（Node.js），提取生产依赖列表。
6. DynamoDB 信息提取（extract_dynamodb_info）专门针对 DynamoDB 做更深入分析：
- 从环境变量默认值（os.environ.get('USERS_TABLE', 'users-table')）中提取可能的表名
- 按优先级筛选最可能包含 schema 定义的文件（init_dynamodb.py、db.py 等为高优先级，routes/ 下的文件为低优先级），返回 TOP-3 schema 文件路径
最终 analysis_report.json 结构：
{
  "project_structure": "...(tree string)...",
  "entry_points": [{"file": "...", "method": "GET", "path": "/items"}],
  "dependency_graph": {"app.py": ["flask", "boto3", ...]},
  "file_tags": {"routes/auth.js": ["Auth", "Database"]},
  "symbol_table": [{"id": "app.routes.get_item", "file_path": "...", "start_line": 42, "end_line": 61}],
  "config_info": {"nodejs_dependencies": [...]},
  "dynamodb_info": {"used": true, "probable_tables": ["users-table"], "schema_files": ["db.js"]}
}

---
第二阶段：预处理（build_rag.py）
触发方式：python src/preprocessor/build_rag.py（手动运行，main.py 之前）
输入：input_monolith/（源码）+ storage/analysis_report.json（上一步的报告）
输出：storage/code_index/（持久化的 LlamaIndex 向量索引）
具体功能
build_rag.py 利用 static_analyzer.py 已经提取的 symbol table，将源码以函数/类为粒度切块，构建语义检索索引，供 Code Developer Agent 在代码生成时做语义检索。
分块策略（build_documents）：
- 对于 symbol table 中存在符号定义的文件 → 按函数/类分块（从 symbol 的 start_line/end_line 提取代码片段），每块附带 metadata（文件路径、函数名、symbol id、行号范围）
- 过滤"噪声文件"：
  - app.py/server.js/index.js/config.js/db.py作为"应用入口/全局配置"，内容横跨多个功能域（路由注册、中间件、环境变量读取等），向量嵌入后会"广泛匹配"几乎任何查询，排名长期靠前但返回的内容对 agent 代码生成毫无帮助。而 agent 本就可以精确地通过 ReadFileTool 直接读取这些已知文件，所以将其从 RAG 索引剔除不会造成任何信息损失，反而让真正有业务逻辑的函数级 chunk 更容易浮出水面。
Embedding 模型：microsoft/codebert-base（HuggingFace 本地加载），专为代码语义理解设计。
索引构建：使用 LlamaIndex 的 VectorStoreIndex.from_documents()，将所有 Document 向量化后持久化到 storage/code_index/。

---
第三阶段：主流程（main.py + CrewAI）
工具集（Tools）
所有 Agent 的工具均继承自 crewai.tools.BaseTool，使用 Pydantic Schema 定义输入：
暂时无法在飞书文档外展示此内容
CodeRAGTool 的特殊设计：使用自定义的 SimpleCodeFormatter 作为 response synthesizer，完全不调用 LLM，直接将检索到的代码片段格式化后返回（附带相关性分数、文件路径、行号）。这避免了 "double inference"（tool LLM + agent LLM），节省 API 成本，同时将推理权完全交给 Agent 的 LLM。底层通过 LlamaIndexTool.from_query_engine() 封装为 CrewAI 标准工具。
Knowledge Sources（知识库配置）
使用 CrewAI 的 TextFileKnowledgeSource，文件放置在 knowledge/ 目录。Embedding 采用本地 Ollama 的 mxbai-embed-large 模型（chunk_size=500, chunk_overlap=50）。
暂时无法在飞书文档外展示此内容
这一设计使 Agent 在推理时能召回相关的架构规范和代码模板，而不是纯靠 LLM 预训练知识。

---
三个 Agent 的职责与执行细节
Agent 1：Architect（架构设计师）
工具：ReadFileTool, WriteFileTool
Knowledge：basic_serverless_architecture.md
max_iter：50
对应 Task：architect_blueprint
执行逻辑：
1. 用 ReadFileTool 读取 storage/analysis_report.json
2. 检查 file_tags 中是否有 Auth tag → 决定是否启用 Cognito
3. 检查 dynamodb_info.used → 若为 true，用 ReadFileTool 读取 schema_files 中的文件，提取表结构（partition key、sort key、GSI）
4. 将 entry_points 中的每个 HTTP endpoint 映射为一个独立 Lambda（严格 one-endpoint-one-Lambda）
5. 识别 Lambda 间调用关系，记录在 lambda_invoke_permissions
6. 将认证端点（/register, /login, /logout 等）列入 dropped_functions（"Infrastructure over Code"原则）
7. 一次性写入完整的 storage/blueprint.json
blueprint.json 核心结构：metadata / lambda_functions / dynamodb_tables / s3_buckets / cognito / api_gateway / lambda_invoke_permissions / dropped_functions

---
Agent 2：Code Developer（代码开发者）
工具：ReadFileTool, CodeRAGTool, WriteFileTool
Knowledge：lambda_coding_reference.md
max_iter：100（最高，因任务量最大）
对应 Task：generate_complete_application
执行逻辑（两阶段）：
Phase 1 - Lambda 代码生成：
- 读取 blueprint.json，逐个处理每个 Lambda 定义
- 用 ReadFileTool 读取 blueprint 中标注的 source_files（原始单体代码）
- 用 CodeRAGTool 作为自主兜底逻辑（已修正prompt）
- 将 Flask/Express 路由改写为 Lambda handler 格式（lambda_handler(event, context)），替换数据库调用为 DynamoDB boto3 SDK 调用
- 每个 Lambda 生成 output/lambdas/{domain}/{lambda_name}/handler.py（或 .js）+ requirements.txt（或 package.json）
- 若 3+ Lambda 共享工具函数 → 生成 output/layers/shared/
- 跨 Lambda 调用使用 boto3 lambda.invoke()，调用目标通过环境变量注入
Phase 2 - 部署文档：
- 生成 output/README.md（包含部署步骤、环境变量说明、curl 测试示例等）

---
Agent 3：SAM Engineer（基础设施代码专家）
工具：ReadFileTool, WriteFileTool, FileListTool, SAMValidateTool
Knowledge：sam_reference.md
max_iter：50
对应Task：拆分为 3 个子 Task（为避免 context window 超限）：
Sub-Task 1：generate_shared_resources_template
- context=[]（清空前序上下文，避免 Code Developer 产生的大量代码日志溢出 context window）
- 仅读取 blueprint.json
- 生成 output/temp_shared_resources.yaml（含 API Gateway、Cognito、DynamoDB、S3、SharedUtilsLayer 的 SAM 资源定义）
- 末尾追加元数据注释块，供下一 Task 读取
Sub-Task 2：generate_functions_template
- context=[]
- 读取 temp_shared_resources.yaml 的元数据注释，获取 has_shared_layer、runtime 等信息
- 用 FileListTool 逐个域（domain）扫描 output/lambdas/
- 对每个 Lambda 目录读取 handler 文件，提取 os.environ 键（→ 环境变量）、boto3 客户端调用（→ IAM Policy）
- 以追加写入方式生成 output/temp_functions.yaml
- 处理跨 Lambda 调用权限（LambdaInvokePolicy）
Sub-Task 3：assemble_final_template
- context=[]
- 读取两个 temp 文件，合并为完整的 output/template.yaml
- 调用 SAMValidateTool（底层用 cfn-lint）验证模板合法性，若失败则迭代修复
- 用 FileListTool 交叉检查：每个 output/lambdas/ 目录都有对应 Function 资源
- 生成 output/samconfig.toml
- 删除两个 temp 文件

---
数据流总结
input_monolith/
    ↓ [static_analyzer.py - AST + 正则静态分析]
storage/analysis_report.json
    ↓ [build_rag.py - CodeBERT 向量化]
storage/code_index/  (LlamaIndex 持久化索引)
    ↓
    ↓ [main.py - CrewAI Sequential Pipeline]
    ↓
[Architect] reads analysis_report.json
    → writes storage/blueprint.json
    ↓
[Code Developer] reads blueprint.json + RAG + source files
    → writes output/lambdas/**/handler.py
    → writes output/layers/shared/ (optional)
    → writes output/README.md
    ↓
[SAM Engineer - Task 1] reads blueprint.json
    → writes output/temp_shared_resources.yaml
    ↓
[SAM Engineer - Task 2] reads temp_shared_resources + scans output/lambdas/
    → writes output/temp_functions.yaml
    ↓
[SAM Engineer - Task 3] merges temp files → validates → cleanup
    → writes output/template.yaml
    → writes output/samconfig.toml

---
框架使用方法（Step-by-Step）
# 1. 将单体应用源码放入 input_monolith/ 目录
# 2. 配置 .env（LLM API Key、模型名称）
# 3. 预处理（一次性，源码不变时无需重跑）
python src/preprocessor/static_analyzer.py
python src/preprocessor/build_rag.py
# 4. 启动本地 Ollama embedding 服务（mxbai-embed-large）
ollama serve   # 确保 11434 端口可用
# 5. 运行主流程
python src/main.py
# 6. 部署
cd output/
sam build && sam deploy --guided

---
关于第四个agent的补充：（形成闭环）
从研究角度看，当前 pipeline 确实存在一个结构性缺陷：Code Developer 和 SAM Engineer 是独立执行的两个阶段，SAM Engineer 虽然在 prompt 中被要求忠实于 output/lambdas/，但唯一的验证手段（cfn-lint）只检查 SAM 模板自身的语法合法性，不检查模板与实际代码之间的一致性。加一个 Consistency Validator Agent 形成闭环验证，在论文中能非常有力地说明这是一个自检式 pipeline（self-verifying pipeline）。
Validator agent补充改动总结
1. agents.yaml — 新增 consistency_validator新 agent 定义了 7 个维度的 cross-check 职责（目录↔Function 覆盖、CodeUri、Handler、环境变量、IAM Policy、Layer 一致性、API Event 匹配），并明确要求"发现问题直接修复 + 再验证"的工作模式。工具集与 SAM Engineer 相同：ReadFileTool、WriteFileTool、FileListTool、SAMValidateTool。2. tasks.yaml — 新增 validate_consistency task追加在 assemble_final_template 之后，分 5 步执行：
2. INVENTORY — 从磁盘构建 Lambda 目录清单 + 从 template.yaml 提取所有 Function 资源 + 读取 blueprint.json
3. CHECK — 执行 C1~C7 七项 cross-check，每项记录 severity + description + affected_resource
4. FIX — 对所有 ERROR 级 finding 进行修复（主要改 template.yaml，必要时改 handler 代码）
5. RE-VALIDATE — SAMValidateTool 验证修复后的模板（最多 3 次重试）
6. REPORT — 输出 output/consistency_report.json，包含所有 findings 及修复记录
3. main.py — 注册第 4 个 Agent
- build_agents() 新增 consistency_validator agent，Knowledge 绑定 sam_reference.md + lambda_coding_reference.md（两份都需要，因为它既要看懂 SAM 模板又要验证 Lambda 代码模式）
- build_tasks() 的 context_clearing_tasks 列表中加入 validate_consistency（与 SAM Engineer 的 3 个子 task 一样清空前序上下文，避免 context window 溢出）
- 更新了 run_crew() 末尾的产物提示
Pipeline 最终形态
[Static Analyzer] → [Build RAG] →
  Agent 1: Architect       → blueprint.json
  Agent 2: Code Developer  → output/lambdas/**
  Agent 3: SAM Engineer    → output/template.yaml  (3 sub-tasks)
  Agent 4: Consistency Validator → cross-check + fix + consistency_report.json  ← 闭环

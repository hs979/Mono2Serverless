完整分析：Lambda 调用关系的设计
一、框架是否具备"自动分析 Lambda 间调用关系"的能力？
不具备。这是一个完全依赖 LLM 推理的设计。
static_analyzer.py 的分析能力范围：
分析项	实现方式	是否涉及调用关系
Entry Points	AST 解析装饰器 / 正则匹配路由	否 — 只提取 HTTP endpoint
Dependencies	import / require 语句	否 — 只记录模块级依赖
Symbol Table	函数名 + 行号范围	否 — 只记录定义位置
File Tags	关键字扫描 (Auth/DynamoDB/...)	否
DynamoDB Info	正则提取表名	否
静态分析器没有任何"函数 A 调用了函数 B"的跨文件调用图分析。它只知道"这个文件 import 了那个模块"，不知道"这个路由 handler 内部调用了那个 service 函数"。
二、Lambda 间调用关系是如何被识别的？
完全由 Architect Agent（LLM）在阅读源码后自主推理。流程如下：
static_analyzer → analysis_report.json (只有 entry_points + source files)                         ↓           Architect Agent 读取 analysis_report.json                         ↓        Architect 用 ReadFileTool 读取 source_files（单体源码）                         ↓        LLM 理解业务逻辑：发现 booking.create_booking() 内部调用了        catalog.reserve_seat()、payment.charge()、loyalty.add_points()                         ↓        LLM 推理：这些在 serverless 架构下变成了跨 Lambda 调用                         ↓        写入 blueprint.json 的 lambda_invoke_permissions
关键指令在 tasks.yaml 的 Architect 任务中：
      ============================================================      LAMBDA COMMUNICATION STRATEGY      ============================================================            ALL Lambda-to-Lambda calls use AWS SDK Direct Invocation.            - Do NOT use HTTP fetch/requests/axios to call another Lambda via API Gateway URL      - Use boto3 lambda.invoke(FunctionName=..., InvocationType=..., Payload=...)      // ...      Identification Step (do this during blueprint design):      Identify ALL cross-Lambda call relationships in the monolith and document each      invoker->target pair in blueprint lambda_invoke_permissions. Set to [] if none.
三、实际效果验证
从 airline-booking 的 blueprint 可以看到 LLM 确实成功识别了调用关系：
  "lambda_invoke_permissions": [    {"invoker": "bookings-create", "target": "flights-reserve-seat"},    {"invoker": "bookings-create", "target": "payments-collect"},    {"invoker": "bookings-create", "target": "bookings-confirm"},    {"invoker": "bookings-create", "target": "loyalty-add-points"},    {"invoker": "bookings-create", "target": "bookings-notify"},    {"invoker": "bookings-cancel", "target": "flights-release-seat"},    {"invoker": "bookings-cancel", "target": "payments-refund"},    {"invoker": "bookings-cancel", "target": "bookings-notify"}  ]
而简单应用（todo、shopping-cart）正确返回了 "lambda_invoke_permissions": []。
四、两种 Lambda 调用方式的完整设计链路
链路 A：API Gateway → Lambda（外部调用）
这条链路有完整的机制保证，从静态分析到最终模板全链路覆盖：
[静态分析器] 提取 entry_points: [{method: "GET", path: "/item/{id}"}]    ↓[Architect] 每个 entry_point → 1 个 Lambda（strict one-endpoint-one-Lambda）    ↓[Code Developer] 写 handler.py，入口函数为 lambda_handler(event, context)    ↓[SAM Engineer #2] 读 handler，生成 Events 块：    Events:      ApiEvent:        Type: Api        Properties:          RestApiId: !Ref MyApi          Path: /item/{id}          Method: GET          Auth:            Authorizer: CognitoAuthorizer    ↓[Consistency Validator] C7 检查：每个 blueprint entry_point 是否都有对应的 Api Event
认证流程：Client → API Gateway (Cognito Authorizer 验证 JWT) → Lambda (只拿 claims.sub)。Lambda 代码中不含任何认证逻辑，这就是 "Infrastructure over Code" 原则。
链路 B：Lambda → Lambda（内部调用）
这条链路完全依赖 LLM 推理，没有静态分析的机制保证：
[静态分析器] ❌ 不分析跨函数调用关系    ↓[Architect] LLM 阅读源码，自主推理出 invoker→target 对    写入 blueprint.lambda_invoke_permissions + 对应 Lambda 的 environment_variables    （如 FLIGHTS_RESERVE_SEAT_FUNCTION_NAME: "${FlightsReserveSeatFunction}"）    ↓[Code Developer] 对 "编排者 Lambda" 用 boto3.client('lambda').invoke()    从 os.environ 读取目标 FunctionName    不在本地实现业务逻辑（"纯编排"原则）    ↓[SAM Engineer #2] 读 handler 代码，发现 lambda_client.invoke() 调用    生成 IAM Policy：    Policies:      - LambdaInvokePolicy:          FunctionName: !Ref FlightsReserveSeatFunction    生成 Environment：    Environment:      Variables:        FLIGHTS_RESERVE_SEAT_FUNCTION_NAME: !Ref FlightsReserveSeatFunction    ↓[Consistency Validator] C5 检查：handler 中有 lambda_client.invoke() →    template 中必须有 LambdaInvokePolicy
五、设计缺陷与风险点
链路 A（API Gateway → Lambda）是稳健的：entry_points 由静态分析器机械提取，一路传递到 SAM 模板的 Api Event，并有 C7 检查兜底。
链路 B（Lambda → Lambda）有以下风险：
识别完全靠 LLM：如果 Architect 漏掉了一对调用关系（例如深层嵌套调用、隐式依赖），blueprint 中就不会有这条记录，后续所有 Agent 都不会补上。
没有静态验证手段：与 entry_points 不同，lambda_invoke_permissions 无法通过 cfn-lint 或任何工具校验其完整性。Consistency Validator 的 C5 检查只能验证"代码里有 invoke → 模板里有 Policy"，但无法验证"单体里有跨模块调用 → blueprint 里有对应记录"。
"纯编排"原则难以强制：tasks.yaml 告诉 Code Developer 编排者 Lambda"must ONLY invoke other Lambdas"，不应本地实现业务逻辑。但这是提示引导，LLM 可能仍然把被调用方的逻辑内联写在编排者 handler 中，绕过了 Lambda 间调用。
幻觉风险：在 airline 的 blueprint 中，bookings-create 的 target 包含 bookings-reserve 和 bookings-notify，但这两个函数不在 lambda_functions 列表中（看第 238 和 254 行）。这是 LLM 幻觉——它想象出了原始代码中不存在的独立 Lambda。
如果你想加强链路 B 的可靠性，可以考虑在 static_analyzer.py 中增加跨文件函数调用图分析（Python 可用 AST 分析函数调用节点，JS 可用正则匹配 require().functionName() 模式），将调用关系作为结构化数据传入 analysis_report.json，让 Architect 有机械化的参考而非纯靠推理。不过这是一个较大的工程改动。
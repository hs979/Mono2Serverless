---

## 1. Standard SAM Template Structure

### Header & Globals
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Serverless application infrastructure

Globals:
  Function:
    # 基础配置（必需）
    Runtime: python3.11  # 根据实际代码调整
    Handler: index.handler
    Timeout: 30  # seconds
    MemorySize: 512  # MB
    
    # 环境变量（常用）
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        LOG_LEVEL: INFO
    
    # 监控追踪（推荐）
    Tracing: Active  # Enable X-Ray tracing
    
    # 共享层（可选）
    Layers:
      - !Ref CommonLayer
    
    # 标签（推荐）
    Tags:
      Project: MyProject
      Environment: !Ref Environment
```

### Parameters
```yaml
Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]
```

## 2. Resource Patterns

### Lambda Function Pattern
```yaml
{LambdaName}Function:
  Type: AWS::Serverless::Function
  Properties:
    # ========== 必需配置 ==========
    CodeUri: backend/lambdas/{lambda_name}/
    Handler: handler.lambda_handler
    Runtime: python3.11  # python3.11, nodejs20.x, etc.
    
    # ========== 常用配置 ==========
    MemorySize: 512  # 128-10240 MB (影响CPU和成本)
    Timeout: 30  # seconds (max 900)
    
    Description: "Function description"  # 可选但推荐
    
    # 环境变量
    Environment:
      Variables:
        TABLE_NAME: !Ref TableName
        QUEUE_URL: !Ref QueueName
        BUCKET_NAME: !Ref BucketName
    
    # 共享代码层
    Layers:
      - !Ref CommonLayer
    
    # 权限策略（三选一）
    Policies:
      # 方式1: SAM策略模板（推荐）
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
      - SQSSendMessagePolicy:
          QueueName: !GetAtt QueueName.QueueName
      
      # 方式2: 内联策略（精细控制）
      - Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - s3:GetObject
            Resource: !Sub arn:aws:s3:::${BucketName}/*
          
          # AI/ML服务
          - Effect: Allow
            Action:
              - comprehend:DetectSentiment
              - rekognition:DetectLabels
            Resource: '*'
    
    # ========== 可选配置（特定场景） ==========
    
    # 并发限制（防止成本失控）
    ReservedConcurrentExecutions: 100
    
    # 版本管理（用于蓝绿部署）
    AutoPublishAlias: live
    
    # 异步调用配置（错误处理）
    EventInvokeConfig:
      MaximumRetryAttempts: 1
      DestinationConfig:
        OnFailure:
          Type: SQS
          Destination: !GetAtt DLQ.Arn
    
    # 事件触发器
    Events:
      # API触发
      ApiEvent:
        Type: Api
        Properties:
          Path: /api/resource
          Method: GET
          RestApiId: !Ref MyApi
      
      # SQS触发
      QueueEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt QueueName.Arn
          BatchSize: 10
      
      # S3触发
      S3Event:
        Type: S3
        Properties:
          Bucket: !Ref BucketName
          Events: s3:ObjectCreated:*
      
      # 定时触发
      ScheduleEvent:
        Type: Schedule
        Properties:
          Schedule: rate(5 minutes)
      
      # EventBridge触发
      EventBridgeEvent:
        Type: EventBridgeRule
        Properties:
          EventBusName: !Ref EventBus
          Pattern:
            source:
              - custom.app
      
      # DynamoDB Stream触发
      DynamoDBEvent:
        Type: DynamoDB
        Properties:
          Stream: !GetAtt MyTable.StreamArn
          StartingPosition: TRIM_HORIZON
          BatchSize: 100
      
      # SNS触发
      SNSEvent:
        Type: SNS
        Properties:
          Topic: !Ref MyTopic
```

### API Gateway Pattern (REST API)

**推荐方式：显式定义API资源，让SAM自动生成路径**

```yaml
MyApi:
  Type: AWS::Serverless::Api
  Properties:
    # 必需
    StageName: !Ref Environment
    
    # CORS配置（前端应用必需）
    Cors:
      AllowMethods: "'*'"
      AllowHeaders: "'*'"
      AllowOrigin: "'*'"
    
    # 认证授权（可选）
    Auth:
      DefaultAuthorizer: MyCognitoAuthorizer
      Authorizers:
        MyCognitoAuthorizer:
          UserPoolArn: !GetAtt UserPool.Arn
    
    # 访问日志（生产环境推荐）
    AccessLogSetting:
      DestinationArn: !GetAtt ApiLogGroup.Arn
      Format: '$context.requestId $context.error.message'
    
    # 请求限流（可选）
    MethodSettings:
      - ResourcePath: "/*"
        HttpMethod: "*"
        ThrottlingBurstLimit: 100
        ThrottlingRateLimit: 50
    
    # X-Ray追踪（推荐）
    TracingEnabled: true

# API日志组
ApiLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub /aws/apigateway/${MyApi}
    RetentionInDays: 30
```

### DynamoDB Table Pattern

```yaml
{TableName}:
  Type: AWS::DynamoDB::Table
  # ⚠️ 数据保护策略（强烈推荐）
  # 防止误删除Stack时丢失数据
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    # 必需
    TableName: !Sub ${Environment}-{table-name}
    
    # 键定义（必需）
    AttributeDefinitions:
      - AttributeName: userId
        AttributeType: S
      - AttributeName: createdAt
        AttributeType: S
    
    KeySchema:
      - AttributeName: userId
        KeyType: HASH
      - AttributeName: createdAt
        KeyType: RANGE
    
    # 计费模式（推荐按需）
    BillingMode: PAY_PER_REQUEST
    
    # 全局二级索引（可选）
    GlobalSecondaryIndexes:
      - IndexName: email-index
        KeySchema:
          - AttributeName: email
            KeyType: HASH
        Projection:
          ProjectionType: ALL
    
    # 流式处理（事件驱动架构需要）
    StreamSpecification:
      StreamViewType: NEW_AND_OLD_IMAGES
    
    # 服务器端加密（推荐）
    SSESpecification:
      SSEEnabled: true
    
    # 时间点恢复（生产环境推荐）
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    
    # 标签
    Tags:
      - Key: Environment
        Value: !Ref Environment
```

### SQS Queue Pattern
```yaml
{QueueName}:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub ${Environment}-{queue-name}
    VisibilityTimeout: 300  # 应大于Lambda超时时间
    MessageRetentionPeriod: 345600  # 4天
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt {QueueName}DLQ.Arn
      maxReceiveCount: 3

{QueueName}DLQ:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub ${Environment}-{queue-name}-dlq
    MessageRetentionPeriod: 1209600  # 14天
```

### SNS Topic Pattern

```yaml
{TopicName}:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub ${Environment}-{topic-name}
    DisplayName: "Topic Display Name"

# Lambda订阅（使用Events自动创建）
{SubscriberFunction}:
  Type: AWS::Serverless::Function
  Properties:
    # ... function properties ...
    Events:
      SnsTrigger:
        Type: SNS
        Properties:
          Topic: !Ref {TopicName}
```

### EventBridge Rule Pattern

**1. 定时任务**
```yaml
{RuleName}Scheduled:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub ${Environment}-{rule-name}-schedule
    ScheduleExpression: "rate(5 minutes)"  # 或 "cron(0 12 * * ? *)"
    State: ENABLED
    Targets:
      - Arn: !GetAtt TargetFunction.Arn
        Id: TargetFunctionV1

{FunctionName}EventPermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref TargetFunction
    Action: lambda:InvokeFunction
    Principal: events.amazonaws.com
    SourceArn: !GetAtt {RuleName}Scheduled.Arn
```

**2. 自定义事件**
```yaml
{RuleName}Pattern:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub ${Environment}-{rule-name}
    EventBusName: !Ref EventBus
    EventPattern:
      source:
        - "my.custom.app"
      detail-type:
        - "OrderPlaced"
      detail:
        status: 
          - "created"
    State: ENABLED
    Targets:
      - Arn: !GetAtt TargetFunction.Arn
        Id: TargetFunctionV1
```

### S3 Bucket Pattern
```yaml
{BucketName}:
  Type: AWS::S3::Bucket
  # ⚠️ 数据保护策略（强烈推荐）
  # 防止误删除Stack时丢失数据
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    BucketName: !Sub ${Environment}-{bucket-name}
    
    # 安全配置（推荐）
    PublicAccessBlockConfiguration:
      BlockPublicAcls: true
      BlockPublicPolicy: true
      IgnorePublicAcls: true
      RestrictPublicBuckets: true
    
    # CORS配置（前端上传需要）
    CorsConfiguration:
      CorsRules:
        - AllowedOrigins: ["https://example.com"]
          AllowedMethods: [GET, PUT, POST]
          AllowedHeaders: ["*"]
    
    # 版本控制（推荐，可恢复误删除的文件）
    VersioningConfiguration:
      Status: Enabled
    
    # 生命周期规则（可选）
    LifecycleConfiguration:
      Rules:
        - Id: DeleteOldFiles
          Status: Enabled
          ExpirationInDays: 90
```

### Step Functions Pattern
```yaml
{WorkflowName}StateMachine:
  Type: AWS::Serverless::StateMachine
  Properties:
    Name: !Sub ${Environment}-{workflow-name}
    DefinitionUri: statemachines/{workflow}.asl.json
    DefinitionSubstitutions:
      Function1Arn: !GetAtt Function1.Arn
      TableName: !Ref TableName
    
    # 必需：权限策略
    Policies:
      - LambdaInvokePolicy:
          FunctionName: !Ref Function1
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
    
    # 可选：事件触发
    Events:
      EventBridgeTrigger:
        Type: EventBridgeRule
        Properties:
          EventBusName: !Ref EventBus
          Pattern:
            source:
              - custom.app
```

### Lambda Layer Pattern
```yaml
CommonLayer:
  Type: AWS::Serverless::LayerVersion
  # ⚠️ 可选：保留Layer版本避免依赖它的Lambda失效
  DeletionPolicy: Retain
  Properties:
    LayerName: !Sub ${Environment}-common-dependencies
    Description: Shared dependencies
    ContentUri: layers/common/
    CompatibleRuntimes:
      - python3.11
      - python3.10
    RetentionPolicy: Retain  # 保留旧版本（Lambda属性）
```

### WebSocket API Pattern

```yaml
WebSocketApi:
  Type: AWS::ApiGatewayV2::Api
  Properties:
    Name: !Sub ${Environment}-websocket-api
    ProtocolType: WEBSOCKET
    RouteSelectionExpression: "$request.body.action"

# 连接路由
ConnectRoute:
  Type: AWS::ApiGatewayV2::Route
  Properties:
    ApiId: !Ref WebSocketApi
    RouteKey: $connect
    AuthorizationType: NONE
    Target: !Join ['/', ['integrations', !Ref ConnectInteg]]

ConnectInteg:
  Type: AWS::ApiGatewayV2::Integration
  Properties:
    ApiId: !Ref WebSocketApi
    IntegrationType: AWS_PROXY
    IntegrationUri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${OnConnectFunction.Arn}/invocations

# 断开路由
DisconnectRoute:
  Type: AWS::ApiGatewayV2::Route
  Properties:
    ApiId: !Ref WebSocketApi
    RouteKey: $disconnect
    Target: !Join ['/', ['integrations', !Ref DisconnectInteg]]

DisconnectInteg:
  Type: AWS::ApiGatewayV2::Integration
  Properties:
    ApiId: !Ref WebSocketApi
    IntegrationType: AWS_PROXY
    IntegrationUri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${OnDisconnectFunction.Arn}/invocations

# 部署
Deployment:
  Type: AWS::ApiGatewayV2::Deployment
  DependsOn:
    - ConnectRoute
    - DisconnectRoute
  Properties:
    ApiId: !Ref WebSocketApi

Stage:
  Type: AWS::ApiGatewayV2::Stage
  Properties:
    StageName: !Ref Environment
    DeploymentId: !Ref Deployment
    ApiId: !Ref WebSocketApi

# Lambda权限
OnConnectPermission:
  Type: AWS::Lambda::Permission
  Properties:
    Action: lambda:InvokeFunction
    FunctionName: !Ref OnConnectFunction
    Principal: apigateway.amazonaws.com
```

## 3. Monitoring Patterns

### CloudWatch Alarms
```yaml
# Lambda错误告警
LambdaErrorAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub ${FunctionName}-errors
    AlarmDescription: Lambda function errors
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 1
    MetricName: Errors
    Namespace: AWS/Lambda
    Period: 60
    Statistic: Sum
    Threshold: 0
    Dimensions:
      - Name: FunctionName
        Value: !Ref FunctionName
    AlarmActions:
      - !Ref AlarmTopic

# API Gateway错误告警
ApiErrorAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub ${ApiName}-5xx-errors
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 2
    MetricName: 5XXError
    Namespace: AWS/ApiGateway
    Period: 60
    Statistic: Sum
    Threshold: 5
    Dimensions:
      - Name: ApiName
        Value: !Ref MyApi
    AlarmActions:
      - !Ref AlarmTopic

# DynamoDB限流告警
DynamoThrottleAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub ${TableName}-throttles
    ComparisonOperator: GreaterThanThreshold
    EvaluationPeriods: 1
    Metrics:
      - Id: throttles
        Expression: m1+m2
      - Id: m1
        MetricStat:
          Metric:
            Namespace: AWS/DynamoDB
            MetricName: UserErrors
            Dimensions:
              - Name: TableName
                Value: !Ref TableName
          Period: 60
          Stat: Sum
        ReturnData: false
      - Id: m2
        MetricStat:
          Metric:
            Namespace: AWS/DynamoDB
            MetricName: SystemErrors
            Dimensions:
              - Name: TableName
                Value: !Ref TableName
          Period: 60
          Stat: Sum
        ReturnData: false
    Threshold: 0
    AlarmActions:
      - !Ref AlarmTopic
```

### CloudWatch Log Groups
```yaml
FunctionLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub /aws/lambda/${FunctionName}
    RetentionInDays: 30  # 7, 14, 30, 60, 90, 120, 180, 365, ...

ApiLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub /aws/apigateway/${ApiName}
    RetentionInDays: 30
```

### SNS Alarm Topic
```yaml
AlarmTopic:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub ${Environment}-alarms
    Subscription:
      - Protocol: email
        Endpoint: alerts@example.com
```

## 4. Cognito Pattern

```yaml
UserPool:
  Type: AWS::Cognito::UserPool
  # ⚠️ 数据保护策略（强烈推荐）
  # 防止误删除Stack时丢失用户数据
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    UserPoolName: !Sub ${Environment}-users
    
    # 自动验证
    AutoVerifiedAttributes:
      - email
    
    # 用户属性
    Schema:
      - Name: email
        Required: true
        Mutable: false
    
    # 密码策略
    Policies:
      PasswordPolicy:
        MinimumLength: 8
        RequireUppercase: true
        RequireLowercase: true
        RequireNumbers: true
        RequireSymbols: false
    
    # MFA配置（可选）
    MfaConfiguration: OPTIONAL

UserPoolClient:
  Type: AWS::Cognito::UserPoolClient
  Properties:
    UserPoolId: !Ref UserPool
    ClientName: !Sub ${Environment}-client
    GenerateSecret: false
    ExplicitAuthFlows:
      - ALLOW_USER_PASSWORD_AUTH
      - ALLOW_REFRESH_TOKEN_AUTH

# Identity Pool（联合身份，可选）
IdentityPool:
  Type: AWS::Cognito::IdentityPool
  # ⚠️ 数据保护策略
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    IdentityPoolName: !Sub ${Environment}Identity
    AllowUnauthenticatedIdentities: false
    CognitoIdentityProviders:
      - ClientId: !Ref UserPoolClient
        ProviderName: !GetAtt UserPool.ProviderName
```

## 5. Output Definitions

```yaml
Outputs:
  # API URL
  ApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub "https://${MyApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
    Export:
      Name: !Sub ${AWS::StackName}-ApiUrl
  
  # WebSocket URL
  WebSocketUrl:
    Description: WebSocket API endpoint
    Value: !Sub "wss://${WebSocketApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
  
  # 表名
  TableName:
    Description: DynamoDB table name
    Value: !Ref MyTable
    Export:
      Name: !Sub ${AWS::StackName}-TableName
  
  # 队列URL
  QueueUrl:
    Description: SQS queue URL
    Value: !Ref MyQueue
  
  # UserPool ID
  UserPoolId:
    Description: Cognito User Pool ID
    Value: !Ref UserPool
    Export:
      Name: !Sub ${AWS::StackName}-UserPoolId
```

## 6. SAM Policy Templates Reference

### 最常用的策略模板（基于实际使用频率）

#### 数据库
- `DynamoDBCrudPolicy` - DynamoDB完整操作
- `DynamoDBReadPolicy` - DynamoDB只读
- `DynamoDBStreamReadPolicy` - 读取DynamoDB流

#### 存储
- `S3CrudPolicy` - S3完整操作
- `S3ReadPolicy` - S3只读
- `S3WritePolicy` - S3只写

#### 消息队列
- `SQSSendMessagePolicy` - 发送SQS消息
- `SQSPollerPolicy` - 从SQS读取和删除消息
- `SNSPublishMessagePolicy` - 发布SNS消息

#### 事件
- `EventBridgePutEventsPolicy` - 发送EventBridge事件

#### 计算
- `LambdaInvokePolicy` - 调用其他Lambda
- `StepFunctionsExecutionPolicy` - 启动Step Functions

#### 安全
- `AWSSecretsManagerGetSecretValuePolicy` - 获取Secrets Manager密钥
- `SSMParameterReadPolicy` - 读取SSM参数

#### AI/ML（使用内联策略）
```yaml
Policies:
  - Version: '2012-10-17'
    Statement:
      # Comprehend
      - Effect: Allow
        Action:
          - comprehend:DetectSentiment
          - comprehend:DetectEntities
        Resource: '*'
      
      # Rekognition
      - Effect: Allow
        Action:
          - rekognition:DetectLabels
          - rekognition:DetectText
        Resource: '*'
      
      # Textract
      - Effect: Allow
        Action:
          - textract:AnalyzeDocument
          - textract:DetectDocumentText
        Resource: '*'
```

## 7. 完整示例

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Serverless REST API with monitoring

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Globals:
  Function:
    Runtime: python3.11
    Handler: index.handler
    Timeout: 30
    MemorySize: 512
    Tracing: Active
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        LOG_LEVEL: INFO
    Tags:
      Environment: !Ref Environment

Resources:
  # API
  MyApi:
    Type: AWS::Serverless::Api
    Properties:
      StageName: !Ref Environment
      TracingEnabled: true
      Cors:
        AllowOrigin: "'*'"
        AllowHeaders: "'*'"
        AllowMethods: "'*'"
      AccessLogSetting:
        DestinationArn: !GetAtt ApiLogGroup.Arn
        Format: '$context.requestId'
  
  ApiLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub /aws/apigateway/${MyApi}
      RetentionInDays: 30
  
  # Lambda Function
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: backend/api/
      Handler: app.handler
      Environment:
        Variables:
          TABLE_NAME: !Ref DataTable
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref DataTable
      Events:
        GetApi:
          Type: Api
          Properties:
            Path: /items
            Method: GET
            RestApiId: !Ref MyApi
  
  # DynamoDB Table
  DataTable:
    Type: AWS::DynamoDB::Table
    # ⚠️ 数据保护：防止误删除Stack时丢失数据
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      TableName: !Sub ${Environment}-data
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      SSESpecification:
        SSEEnabled: true
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
  
  # CloudWatch Alarm
  ApiErrorAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub ${Environment}-api-errors
      ComparisonOperator: GreaterThanThreshold
      EvaluationPeriods: 1
      MetricName: 5XXError
      Namespace: AWS/ApiGateway
      Period: 60
      Statistic: Sum
      Threshold: 5
      Dimensions:
        - Name: ApiName
          Value: !Ref MyApi
      AlarmActions:
        - !Ref AlarmTopic
  
  AlarmTopic:
    Type: AWS::SNS::Topic
    Properties:
      Subscription:
        - Protocol: email
          Endpoint: alerts@example.com

Outputs:
  ApiUrl:
    Value: !Sub "https://${MyApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
  TableName:
    Value: !Ref DataTable
```

### 最常用的策略模板（基于实际使用频率）

```yaml
Policies:
  # DynamoDB访问（最常用）
  - DynamoDBCrudPolicy:
      TableName: !Ref MyTable
  
  # S3访问
  - S3CrudPolicy:
      BucketName: !Ref MyBucket
  
  # SQS发送消息
  - SQSSendMessagePolicy:
      QueueName: !GetAtt MyQueue.QueueName
  
  # SNS发布
  - SNSPublishMessagePolicy:
      TopicName: !GetAtt MyTopic.TopicName
  
  # Step Functions执行
  - StepFunctionsExecutionPolicy:
      StateMachineName: !GetAtt MyStateMachine.Name
  
  # Lambda调用
  - LambdaInvokePolicy:
      FunctionName: !Ref AnotherFunction
  
  # Secrets Manager读取
  - AWSSecretsManagerGetSecretValuePolicy:
      SecretArn: !Ref MySecret
  
  # VPC内Lambda必需
  - VPCAccessPolicy: {}
  
  # X-Ray追踪（Global Tracing: Active时自动添加）
  - AWSXRayDaemonWriteAccess
```

### 策略决策树

```
需要访问AWS资源？
├─ 是 → 使用SAM Policy Template（推荐）
│   ├─ DynamoDB → DynamoDBCrudPolicy
│   ├─ S3 → S3CrudPolicy
│   ├─ SQS → SQSSendMessagePolicy
│   └─ 其他 → 查看上面列表
│
├─ 需要自定义权限？ → 内联IAM策略
│   ```yaml
│   Policies:
│     - Version: '2012-10-17'
│       Statement:
│         - Effect: Allow
│           Action: ['dynamodb:GetItem']
│           Resource: !GetAtt Table.Arn
│   ```
│
└─ 需要跨多个Lambda复用？ → 创建独立IAM Role
    ```yaml
    SharedRole:
      Type: AWS::IAM::Role
      Properties:
        AssumeRolePolicyDocument: ...
        ManagedPolicyArns:
          - arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
    
    MyFunction:
      Type: AWS::Serverless::Function
      Properties:
        Role: !GetAtt SharedRole.Arn
    ```
```

---
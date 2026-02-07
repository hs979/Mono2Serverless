# AWS SAM Reference & Patterns (Simplified)

This knowledge base provides essential AWS SAM templates, resource definitions, and policy patterns for the Serverless Migration project. This is a simplified version focusing on the most commonly used patterns.

## 1. Standard SAM Template Structure

### Header & Globals
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Serverless application infrastructure

Globals:
  Function:
    # Basic Configuration (Required)
    Runtime: python3.11  # Adjust based on actual code
    Handler: index.handler
    Timeout: 30  # seconds
    MemorySize: 512  # MB
    
    # Environment Variables (Common)
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        LOG_LEVEL: INFO
    
    # Monitoring & Tracing (Recommended)
    Tracing: Active  # Enable X-Ray tracing
    
    # Shared Layers (Optional)
    Layers:
      - !Ref CommonLayer
    
    # Tags (Recommended)
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
    # ========== Required Configuration ==========
    CodeUri: backend/lambdas/{lambda_name}/
    Handler: handler.lambda_handler
    Runtime: python3.11  # python3.11, nodejs20.x, etc.
    
    # ========== Common Configuration ==========
    MemorySize: 512  # 128-10240 MB (affects CPU and cost)
    Timeout: 30  # seconds (max 900)
    
    Description: "Function description"  # Optional but recommended
    
    # Environment Variables
    Environment:
      Variables:
        TABLE_NAME: !Ref TableName
        QUEUE_URL: !Ref QueueName
        BUCKET_NAME: !Ref BucketName
    
    # Shared Code Layers
    Layers:
      - !Ref CommonLayer
    
    # Permission Policies (choose one approach)
    Policies:
      # Approach 1: SAM Policy Templates (Recommended)
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
      - SQSSendMessagePolicy:
          QueueName: !GetAtt QueueName.QueueName
      
      # Approach 2: Inline Policy (Fine-grained control)
      - Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - s3:GetObject
            Resource: !Sub arn:aws:s3:::${BucketName}/*
          
          # AI/ML Services
          - Effect: Allow
            Action:
              - comprehend:DetectSentiment
              - rekognition:DetectLabels
            Resource: '*'
    
    # ========== Optional Configuration (Specific scenarios) ==========
    
    # Concurrency Limits (Prevent cost runaway)
    ReservedConcurrentExecutions: 100
    
    # Version Management (For blue-green deployments)
    AutoPublishAlias: live
    
    # Async Invocation Config (Error handling)
    EventInvokeConfig:
      MaximumRetryAttempts: 1
      DestinationConfig:
        OnFailure:
          Type: SQS
          Destination: !GetAtt DLQ.Arn
    
    # Event Triggers
    Events:
      # API Trigger
      ApiEvent:
        Type: Api
        Properties:
          Path: /api/resource
          Method: GET
          RestApiId: !Ref MyApi
      
      # SQS Trigger
      QueueEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt QueueName.Arn
          BatchSize: 10
      
      # S3 Trigger
      S3Event:
        Type: S3
        Properties:
          Bucket: !Ref BucketName
          Events: s3:ObjectCreated:*
      
      # Schedule Trigger
      ScheduleEvent:
        Type: Schedule
        Properties:
          Schedule: rate(5 minutes)
      
      # EventBridge Trigger
      EventBridgeEvent:
        Type: EventBridgeRule
        Properties:
          EventBusName: !Ref EventBus
          Pattern:
            source:
              - custom.app
      
      # DynamoDB Stream Trigger
      DynamoDBEvent:
        Type: DynamoDB
        Properties:
          Stream: !GetAtt MyTable.StreamArn
          StartingPosition: TRIM_HORIZON
          BatchSize: 100
      
      # SNS Trigger
      SNSEvent:
        Type: SNS
        Properties:
          Topic: !Ref MyTopic
```

### API Gateway Pattern (REST API)

**Recommended: Explicitly define API resource, let SAM auto-generate paths**

```yaml
MyApi:
  Type: AWS::Serverless::Api
  Properties:
    # Required
    StageName: !Ref Environment
    
    # CORS Configuration (Required for frontend apps)
    Cors:
      AllowMethods: "'*'"
      AllowHeaders: "'*'"
      AllowOrigin: "'*'"
    
    # Authentication & Authorization (Optional)
    Auth:
      DefaultAuthorizer: MyCognitoAuthorizer
      Authorizers:
        MyCognitoAuthorizer:
          UserPoolArn: !GetAtt UserPool.Arn
    
    # Access Logs (Recommended for production)
    AccessLogSetting:
      DestinationArn: !GetAtt ApiLogGroup.Arn
      Format: '$context.requestId $context.error.message'
    
    # Request Throttling (Optional)
    MethodSettings:
      - ResourcePath: "/*"
        HttpMethod: "*"
        ThrottlingBurstLimit: 100
        ThrottlingRateLimit: 50
    
    # X-Ray Tracing (Recommended)
    TracingEnabled: true

# API Log Group
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
  # ⚠️ Data Protection Policy (Strongly Recommended)
  # Prevents data loss when stack is deleted
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    # Required
    TableName: !Sub ${Environment}-{table-name}
    
    # Key Definitions (Required)
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
    
    # Billing Mode (Pay-per-request recommended)
    BillingMode: PAY_PER_REQUEST
    
    # Global Secondary Indexes (Optional)
    GlobalSecondaryIndexes:
      - IndexName: email-index
        KeySchema:
          - AttributeName: email
            KeyType: HASH
        Projection:
          ProjectionType: ALL
    
    # Streaming (Required for event-driven architecture)
    StreamSpecification:
      StreamViewType: NEW_AND_OLD_IMAGES
    
    # Server-side Encryption (Recommended)
    SSESpecification:
      SSEEnabled: true
    
    # Point-in-time Recovery (Recommended for production)
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    
    # Tags
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
    VisibilityTimeout: 300  # Should be greater than Lambda timeout
    MessageRetentionPeriod: 345600  # 4 days
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt {QueueName}DLQ.Arn
      maxReceiveCount: 3

{QueueName}DLQ:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub ${Environment}-{queue-name}-dlq
    MessageRetentionPeriod: 1209600  # 14 days
```

### SNS Topic Pattern

```yaml
{TopicName}:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub ${Environment}-{topic-name}
    DisplayName: "Topic Display Name"

# Lambda Subscription (Auto-created using Events)
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

**1. Scheduled Task**
```yaml
{RuleName}Scheduled:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub ${Environment}-{rule-name}-schedule
    ScheduleExpression: "rate(5 minutes)"  # or "cron(0 12 * * ? *)"
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

**2. Custom Events**
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
  # ⚠️ Data Protection Policy (Strongly Recommended)
  # Prevents data loss when stack is deleted
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    BucketName: !Sub ${Environment}-{bucket-name}
    
    # Security Configuration (Recommended)
    PublicAccessBlockConfiguration:
      BlockPublicAcls: true
      BlockPublicPolicy: true
      IgnorePublicAcls: true
      RestrictPublicBuckets: true
    
    # CORS Configuration (Required for frontend uploads)
    CorsConfiguration:
      CorsRules:
        - AllowedOrigins: ["https://example.com"]
          AllowedMethods: [GET, PUT, POST]
          AllowedHeaders: ["*"]
    
    # Versioning (Recommended, allows recovery of deleted files)
    VersioningConfiguration:
      Status: Enabled
    
    # Lifecycle Rules (Optional)
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
    
    # Required: Permission Policies
    Policies:
      - LambdaInvokePolicy:
          FunctionName: !Ref Function1
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
    
    # Optional: Event Triggers
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
  # ⚠️ Optional: Retain layer versions to avoid breaking dependent Lambdas
  DeletionPolicy: Retain
  Properties:
    LayerName: !Sub ${Environment}-common-dependencies
    Description: Shared dependencies
    ContentUri: layers/common/
    CompatibleRuntimes:
      - python3.11
      - python3.10
    RetentionPolicy: Retain  # Retain old versions (Lambda property)
```

### WebSocket API Pattern

```yaml
WebSocketApi:
  Type: AWS::ApiGatewayV2::Api
  Properties:
    Name: !Sub ${Environment}-websocket-api
    ProtocolType: WEBSOCKET
    RouteSelectionExpression: "$request.body.action"

# Connect Route
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

# Disconnect Route
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

# Deployment
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

# Lambda Permissions
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
# Lambda Error Alarm
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

# API Gateway Error Alarm
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

# DynamoDB Throttling Alarm
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
  # ⚠️ Data Protection Policy (Strongly Recommended)
  # Prevents data loss when stack is deleted
  DeletionPolicy: Retain
  UpdateReplacePolicy: Retain
  Properties:
    UserPoolName: !Sub ${Environment}-users
    
    # Auto Verification
    AutoVerifiedAttributes:
      - email
    
    # User Attributes
    Schema:
      - Name: email
        Required: true
        Mutable: false
    
    # Password Policy
    Policies:
      PasswordPolicy:
        MinimumLength: 8
        RequireUppercase: true
        RequireLowercase: true
        RequireNumbers: true
        RequireSymbols: false
    
    # MFA Configuration (Optional)
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

# Identity Pool (Federated Identities, Optional)
IdentityPool:
  Type: AWS::Cognito::IdentityPool
  # ⚠️ Data Protection Policy
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
  
  # Table Name
  TableName:
    Description: DynamoDB table name
    Value: !Ref MyTable
    Export:
      Name: !Sub ${AWS::StackName}-TableName
  
  # Queue URL
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

### Most Commonly Used Policy Templates (By actual usage frequency)

#### Database
- `DynamoDBCrudPolicy` - Full DynamoDB operations
- `DynamoDBReadPolicy` - DynamoDB read-only
- `DynamoDBStreamReadPolicy` - Read DynamoDB streams

#### Storage
- `S3CrudPolicy` - Full S3 operations
- `S3ReadPolicy` - S3 read-only
- `S3WritePolicy` - S3 write-only

#### Message Queues
- `SQSSendMessagePolicy` - Send SQS messages
- `SQSPollerPolicy` - Read and delete from SQS
- `SNSPublishMessagePolicy` - Publish SNS messages

#### Events
- `EventBridgePutEventsPolicy` - Send EventBridge events

#### Compute
- `LambdaInvokePolicy` - Invoke other Lambdas
- `StepFunctionsExecutionPolicy` - Start Step Functions

#### Security
- `AWSSecretsManagerGetSecretValuePolicy` - Get Secrets Manager secrets
- `SSMParameterReadPolicy` - Read SSM parameters

#### AI/ML (Use inline policies)
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

## 7. Complete Example

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
    # ⚠️ Data Protection: Prevents data loss on stack deletion
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

### Most Commonly Used Policy Templates (By actual usage frequency)

```yaml
Policies:
  # DynamoDB Access (Most Common)
  - DynamoDBCrudPolicy:
      TableName: !Ref MyTable
  
  # S3 Access
  - S3CrudPolicy:
      BucketName: !Ref MyBucket
  
  # SQS Send Messages
  - SQSSendMessagePolicy:
      QueueName: !GetAtt MyQueue.QueueName
  
  # SNS Publish
  - SNSPublishMessagePolicy:
      TopicName: !GetAtt MyTopic.TopicName
  
  # Step Functions Execution
  - StepFunctionsExecutionPolicy:
      StateMachineName: !GetAtt MyStateMachine.Name
  
  # Lambda Invocation
  - LambdaInvokePolicy:
      FunctionName: !Ref AnotherFunction
  
  # Secrets Manager Read
  - AWSSecretsManagerGetSecretValuePolicy:
      SecretArn: !Ref MySecret
  
  # VPC Access (Required for Lambda in VPC)
  - VPCAccessPolicy: {}
  
  # X-Ray Tracing (Automatically added when Global Tracing: Active)
  - AWSXRayDaemonWriteAccess
```

### Policy Decision Tree

```
Need to access AWS resources?
├─ Yes → Use SAM Policy Template (Recommended)
│   ├─ DynamoDB → DynamoDBCrudPolicy
│   ├─ S3 → S3CrudPolicy
│   ├─ SQS → SQSSendMessagePolicy
│   └─ Others → Check list above
│
├─ Need custom permissions? → Inline IAM Policy
│   ```yaml
│   Policies:
│     - Version: '2012-10-17'
│       Statement:
│         - Effect: Allow
│           Action: ['dynamodb:GetItem']
│           Resource: !GetAtt Table.Arn
│   ```
│
└─ Need to reuse across multiple Lambdas? → Create separate IAM Role
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

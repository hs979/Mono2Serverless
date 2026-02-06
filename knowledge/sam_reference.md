# AWS SAM Reference & Patterns

This knowledge base provides standard AWS SAM templates, resource definitions, and policy patterns for the Serverless Migration project.

## 1. Standard SAM Template Structure

### Header & Globals
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Serverless application infrastructure

Globals:
  Function:
    # Basic Configuration
    Runtime: python3.11  # Adjust based on actual code
    Handler: index.handler  # Default handler
    Timeout: 30  # seconds
    MemorySize: 512  # MB
    
    # Architecture (cost optimization)
    Architectures:
      - arm64  # Use ARM for 34% cost savings
    
    # Storage
    EphemeralStorage:
      Size: 1024  # MB (512-10240)
    
    # Environment Variables (inherited by all functions)
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
        LOG_LEVEL: INFO
    
    # Tracing & Monitoring
    Tracing: Active  # Enable X-Ray tracing
    
    # Logging
    LoggingConfig:
      LogFormat: JSON
      ApplicationLogLevel: INFO
      SystemLogLevel: INFO
    
    # Layers (common dependencies)
    Layers:
      - !Ref CommonLayer
    
    # Deployment
    AutoPublishAlias: live  # All functions get versioning
    
    # Async Configuration
    EventInvokeConfig:
      MaximumRetryAttempts: 1
      MaximumEventAgeInSeconds: 3600
    
    # Security
    ReservedConcurrentExecutions: 100  # Prevent runaway costs
    RecursiveLoop: Terminate  # Safety for recursive invocations
    
    # VPC Configuration (if needed)
    # VpcConfig:
    #   SecurityGroupIds:
    #     - !Ref LambdaSecurityGroup
    #   SubnetIds:
    #     - !Ref PrivateSubnet1
    #     - !Ref PrivateSubnet2
    
    # Tags
    Tags:
      Project: MyProject
      Environment: !Ref Environment
  
  # NOTE: Do NOT define Api globals if you're using an explicit AWS::Serverless::Api resource
  # Globals.Api settings do NOT apply to explicitly defined API resources
  # Instead, configure CORS and other settings directly in the explicit API resource (see MyApi below)
  
  # HttpApi Globals (apply to implicit HTTP APIs)
  HttpApi:
    # Auth:
    #   DefaultAuthorizer: OAuth2Authorizer
    #   Authorizers:
    #     OAuth2Authorizer:
    #       IdentitySource: $request.header.Authorization
    #       JwtConfiguration:
    #         issuer: https://auth.example.com
    #         audience:
    #           - my-app
    CorsConfiguration:
      AllowOrigins:
        - "https://example.com"
      AllowHeaders:
        - "content-type"
        - "authorization"
      AllowMethods:
        - GET
        - POST
        - PUT
        - DELETE
      MaxAge: 600
  
  # SimpleTable Globals
  SimpleTable:
    SSESpecification:
      SSEEnabled: true
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

### API Gateway Pattern (REST API)
**Recommended Strategy:** Define the API resource explicitly to configure StageName and Auth, but **let SAM generate the paths/definitions automatically** from Lambda Events. Avoid manually defining `DefinitionBody` unless you need complex OpenAPI features, as it requires manual permission management.

```yaml
MyApi:
  Type: AWS::Serverless::Api
  Properties:
    StageName: !Ref Environment
    # IMPORTANT: Configure CORS here for explicit APIs, NOT in Globals.Api
    # Globals.Api does NOT apply to explicitly defined AWS::Serverless::Api resources
    Cors:
      AllowMethods: "'*'"
      AllowHeaders: "'*'"
      AllowOrigin: "'*'"
    # Do NOT include DefinitionBody here unless you manually handle AWS::Lambda::Permission
    Auth:
      DefaultAuthorizer: MyCognitoAuthorizer # Optional
      Authorizers:
        MyCognitoAuthorizer:
          UserPoolArn: !GetAtt UserPool.Arn

# Corresponding Lambda trigger
# The path and method defined here will be AUTOMATICALLY added to the API above
Events:
  ApiEvent:
    Type: Api
    Properties:
      Path: /my-resource
      Method: POST
      RestApiId: !Ref MyApi  # Links this Lambda to the explicit API
```

### Lambda Function Pattern
```yaml
{LambdaName}Function:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: backend/lambdas/{lambda_name}/
    Handler: handler.lambda_handler  # From actual code
    Runtime: python3.11  # From file extension
    
    # Architecture (x86_64 or arm64)
    # arm64 (Graviton2) is up to 34% cheaper and 19% faster
    Architectures:
      - arm64  # or x86_64 (default)
    
    # Memory & Performance
    MemorySize: 512  # 128-10240 MB
    Timeout: 30  # seconds
    
    # Ephemeral Storage (512 MB - 10 GB)
    EphemeralStorage:
      Size: 1024  # MB, default is 512
    
    # Environment Variables
    Environment:
      Variables:
        # Add env vars for all AWS resources this Lambda uses
        TABLE_NAME: !Ref TableName
        QUEUE_URL: !Ref QueueName
        BUCKET_NAME: !Ref BucketName
    
    # Lambda Function URL (no API Gateway needed)
    FunctionUrlConfig:
      AuthType: AWS_IAM  # or NONE for public access
      Cors:
        AllowOrigins:
          - "https://example.com"
        AllowMethods:
          - GET
          - POST
        AllowHeaders:
          - "content-type"
        MaxAge: 300
      # InvokeMode: BUFFERED (default) or RESPONSE_STREAM
    
    # Deployment Strategy (Blue/Green or Canary)
    AutoPublishAlias: live  # Creates alias that points to latest version
    DeploymentPreference:
      Type: Canary10Percent5Minutes  # or Linear10PercentEvery1Minute, AllAtOnce
      Alarms:
        - !Ref FunctionErrorAlarm
      Hooks:
        PreTraffic: !Ref PreTrafficHookFunction
        PostTraffic: !Ref PostTrafficHookFunction
      # TriggerConfigurations:  # for CodeDeploy integrations
    
    # Async Invocation Configuration
    EventInvokeConfig:
      MaximumRetryAttempts: 1  # 0-2, default is 2
      MaximumEventAgeInSeconds: 3600  # 60-21600
      DestinationConfig:
        OnSuccess:
          Type: SQS
          Destination: !GetAtt SuccessQueue.Arn
        OnFailure:
          Type: SNS
          Destination: !Ref FailureTopic
    
    # Logging Configuration
    LoggingConfig:
      LogFormat: JSON  # Text or JSON
      ApplicationLogLevel: INFO  # TRACE, DEBUG, INFO, WARN, ERROR, FATAL
      SystemLogLevel: INFO
      LogGroup: !Ref CustomLogGroup
    
    # Prevent Recursive Loops
    RecursiveLoop: Terminate  # Terminate or Allow
    
    # Reserved Concurrent Executions (limit)
    ReservedConcurrentExecutions: 5
    
    # Provisioned Concurrency (keep warm)
    ProvisionedConcurrencyConfig:
      ProvisionedConcurrentExecutions: 5
    
    # SnapStart (for Java only - improves cold start)
    SnapStart:
      ApplyOn: PublishedVersions
    
    # Dead Letter Queue
    DeadLetterQueue:
      Type: SQS  # or SNS
      TargetArn: !GetAtt DLQ.Arn
    
    # Layers
    Layers:
      - !Ref CommonLayer
      - arn:aws:lambda:region:account:layer:layer-name:version
    
    # POLICY STRATEGY:
    # 1. Use Connectors (BEST - automatic IAM policies)
    # 2. Use SAM Policy Templates for standard AWS services
    # 3. Use Inline Policies for:
    #    - Services without SAM templates (Comprehend, Textract, Bedrock, etc.)
    #    - When SAM templates grant excessive permissions (e.g., only need s3:GetObject, not full CRUD)
    #    - Complex conditional policies
    Policies:
      # SAM Policy Templates (use when available)
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
      - SQSSendMessagePolicy:
          QueueName: !GetAtt QueueName.QueueName
      
      # Inline Policy for granular control or unsupported services
      - Version: '2012-10-17'
        Statement:
          # Read-only S3 access (narrower than S3CrudPolicy)
          - Effect: Allow
            Action:
              - s3:GetObject
            Resource: !Sub arn:aws:s3:::${BucketName}/*
          
          # AI/ML services without SAM templates
          - Effect: Allow
            Action:
              - comprehend:DetectSentiment
              - comprehend:DetectEntities
            Resource: '*'
          
          # X-Ray tracing (if not using Globals.Function.Tracing)
          - Effect: Allow
            Action: xray:PutTraceSegments
            Resource: '*'
    
    # OR use Connectors (Recommended)
  Connectors:
    TableConnection:
      Properties:
        Destination:
          Id: TableName
        Permissions:
          - Read
          - Write
    QueueConnection:
      Properties:
        Destination:
          Id: QueueName
        Permissions:
          - Write
    
  Properties:
    Events:
      # From blueprint entry_points
      ApiEvent1:
        Type: Api  # or HttpApi
        Properties:
          Path: /api/resource
          Method: GET
          RestApiId: !Ref MyApi  # Optional: if using explicit API resource
      
      # HTTP API Event
      HttpApiEvent:
        Type: HttpApi
        Properties:
          Path: /api/resource
          Method: POST
          ApiId: !Ref MyHttpApi
      
      # Add SQS trigger if Lambda processes queue
      QueueEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt QueueName.Arn
          BatchSize: 10
          MaximumBatchingWindowInSeconds: 5
          FunctionResponseTypes:
            - ReportBatchItemFailures  # Partial batch failure handling
      
      # Add S3 trigger if Lambda processes uploads
      S3Event:
        Type: S3
        Properties:
          Bucket: !Ref BucketName
          Events: s3:ObjectCreated:*
          Filter:
            S3Key:
              Rules:
                - Name: prefix
                  Value: uploads/
                - Name: suffix
                  Value: .jpg
      
      # Schedule Event
      ScheduleEvent:
        Type: Schedule
        Properties:
          Schedule: rate(5 minutes)  # or cron(0 12 * * ? *)
          Description: Run every 5 minutes
          Enabled: true
      
      # EventBridge Rule
      EventBridgeEvent:
        Type: EventBridgeRule
        Properties:
          Pattern:
            source:
              - aws.s3
            detail-type:
              - Object Created
      
      # DynamoDB Stream
      DynamoDBEvent:
        Type: DynamoDB
        Properties:
          Stream: !GetAtt MyTable.StreamArn
          StartingPosition: TRIM_HORIZON
          BatchSize: 100
          MaximumBatchingWindowInSeconds: 10
```

### DynamoDB Table Pattern
Strategy: Extract table schemas from ACTUAL SOURCE FILES first.

**Python creation pattern to look for:**
```python
dynamodb.create_table(
    TableName='UsersTable',
    KeySchema=[
        {'AttributeName': 'userId', 'KeyType': 'HASH'},
        {'AttributeName': 'createdAt', 'KeyType': 'RANGE'}
    ],
    AttributeDefinitions=[...],
    GlobalSecondaryIndexes=[...]
)
```

**JavaScript creation pattern to look for:**
```javascript
await dynamodb.createTable({
  TableName: 'users-table',
  KeySchema: [
    { AttributeName: 'userId', KeyType: 'HASH' }
  ],
  AttributeDefinitions: [...],
  GlobalSecondaryIndexes: [...]
});
```

**SAM Resource Output:**
```yaml
UsersTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub ${Environment}-users
    AttributeDefinitions:
      - AttributeName: userId
        AttributeType: S
      - AttributeName: email
        AttributeType: S
    KeySchema:
      - AttributeName: userId
        KeyType: HASH
    GlobalSecondaryIndexes:
      - IndexName: email-index
        KeySchema:
          - AttributeName: email
            KeyType: HASH
        Projection:
          ProjectionType: ALL
    BillingMode: PAY_PER_REQUEST
    StreamSpecification:
      StreamViewType: NEW_AND_OLD_IMAGES  # If event-driven patterns detected
```

### SQS Queue Pattern
```yaml
{QueueName}:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub ${Environment}-{queue-name}
    VisibilityTimeout: 300
    MessageRetentionPeriod: 345600
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt {QueueName}DLQ.Arn
      maxReceiveCount: 3

{QueueName}DLQ:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: !Sub ${Environment}-{queue-name}-dlq
```

### SNS Topic Pattern

**Recommended SAM Approach:** Use Lambda Events to auto-create subscription and permission.

```yaml
# Define the Topic
{TopicName}:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub ${Environment}-{topic-name}

# Subscribe Lambda via Events (SAM auto-creates permission)
{SubscriberFunction}:
  Type: AWS::Serverless::Function
  Properties:
    # ... function properties ...
    Events:
      SnsTrigger:
        Type: SNS
        Properties:
          Topic: !Ref {TopicName}
          FilterPolicy:  # Optional: filter messages
            eventType:
              - order.created
```

**Alternative (Legacy CloudFormation):** Manual subscription and permission.
```yaml
{TopicName}:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub ${Environment}-{topic-name}
    Subscription:
      - Endpoint: !GetAtt SubscriberFunction.Arn
        Protocol: lambda

{FunctionName}SnsPermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref SubscriberFunction
    Action: lambda:InvokeFunction
    Principal: sns.amazonaws.com
    SourceArn: !Ref {TopicName}
```

### EventBridge Rule Patterns (Detailed)

#### 1. Scheduled Rule (Cron/Rate)
```yaml
{RuleName}Scheduled:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub ${Environment}-{rule-name}-schedule
    Description: Trigger Lambda every 5 minutes
    ScheduleExpression: "rate(5 minutes)"  # or "cron(0 12 * * ? *)"
    State: ENABLED
    Targets:
      - Arn: !GetAtt TargetFunction.Arn
        Id: TargetFunctionV1
```

#### 2. S3 Event Rule (via CloudTrail) - Recommended for Complex Filtering
**Prerequisite:** Ensure a CloudTrail exists that logs Data Events for the S3 bucket.

```yaml
{RuleName}S3Event:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub ${Environment}-{rule-name}-s3-event
    Description: Trigger on S3 PutObject with suffix filtering
    State: ENABLED
    EventPattern:
      source:
        - aws.s3
      detail-type:
        - "AWS API Call via CloudTrail"
      detail:
        eventSource:
          - s3.amazonaws.com
        eventName:
          - PutObject
          - CompleteMultipartUpload
        requestParameters:
          bucketName:
            - !Ref BucketName
          key:
            # CRITICAL: Suffix/Prefix matching MUST be a list of objects
            # Incorrect: suffix: ".md"
            # Correct:   - suffix: ".md"
            - suffix: ".md"
            # OR for prefix:
            # - prefix: "uploads/"
    Targets:
      - Arn: !GetAtt TargetFunction.Arn
        Id: TargetFunctionV1

{FunctionName}EventPermission:
  Type: AWS::Lambda::Permission
  Properties:
    FunctionName: !Ref TargetFunction
    Action: lambda:InvokeFunction
    Principal: events.amazonaws.com
    SourceArn: !GetAtt {RuleName}S3Event.Arn
```

#### 3. Standard Pattern Matching Rules
Use when matching exact values or multiple possible values.

```yaml
{RuleName}Pattern:
  Type: AWS::Events::Rule
  Properties:
    EventPattern:
      source:
        - "my.custom.app"
      detail-type:
        - "OrderPlaced"
      detail:
        status: 
          - "created"   # Matches exact string
          - "pending"   # OR matches "pending"
        amount:
          - numeric: [">", 100]  # Numeric matching
```

### S3 Bucket Pattern
```yaml
{BucketName}:
  Type: AWS::S3::Bucket
  Properties:
    BucketName: !Sub ${Environment}-{bucket-name}
    PublicAccessBlockConfiguration:
      BlockPublicAcls: true
      BlockPublicPolicy: true
    CorsConfiguration:  # If frontend uploads
      CorsRules:
        - AllowedOrigins: ["*"]
          AllowedMethods: [GET, PUT, POST]
```

### Step Functions Pattern
```yaml
{WorkflowName}StateMachine:
  Type: AWS::Serverless::StateMachine
  Properties:
    DefinitionUri: backend/statemachines/{workflow}.asl.json
    DefinitionSubstitutions:
      Function1Arn: !GetAtt Function1.Arn
      TableName: !Ref TableName
    Policies:
      - LambdaInvokePolicy:
          FunctionName: !Ref Function1
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
```

### Lambda Layer Pattern
```yaml
CommonLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: common-utils
    ContentUri: backend/layers/common_utils/
    CompatibleRuntimes:
      - python3.11
```

### HTTP API Pattern (AWS::Serverless::HttpApi)
**Use Case:** When you need lower latency and cost compared to REST API. HTTP APIs are simpler and up to 71% cheaper.

```yaml
MyHttpApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    StageName: !Ref Environment
    # CORS Configuration
    CorsConfiguration:
      AllowOrigins:
        - "https://example.com"
        - "http://localhost:3000"
      AllowHeaders:
        - "content-type"
        - "authorization"
      AllowMethods:
        - GET
        - POST
        - PUT
        - DELETE
      MaxAge: 3600
      AllowCredentials: true
    
    # Authentication (optional)
    Auth:
      Authorizers:
        MyJWTAuthorizer:
          IdentitySource: $request.header.Authorization
          JwtConfiguration:
            issuer: https://cognito-idp.{region}.amazonaws.com/{userPoolId}
            audience:
              - !Ref UserPoolClient
      DefaultAuthorizer: MyJWTAuthorizer
    
    # Custom Domain (optional)
    Domain:
      DomainName: api.example.com
      CertificateArn: !Ref ApiCertificate
      Route53:
        HostedZoneId: !Ref HostedZone
    
    # Access Logging
    AccessLogSettings:
      DestinationArn: !GetAtt ApiLogGroup.Arn
      Format: '$context.requestId $context.error.message $context.error.messageString'

# Lambda with HTTP API Event
MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    # ... function properties ...
    Events:
      HttpApiEvent:
        Type: HttpApi
        Properties:
          Path: /users/{id}
          Method: GET
          ApiId: !Ref MyHttpApi  # Link to explicit HTTP API
          # Auth override (optional)
          Auth:
            Authorizer: NONE  # Make this endpoint public
```

### GraphQL API Pattern (AWS::Serverless::GraphQLApi)
**Use Case:** Build GraphQL APIs with AWS AppSync with simplified configuration.

```yaml
MyGraphQLApi:
  Type: AWS::Serverless::GraphQLApi
  Properties:
    Name: !Sub ${Environment}-my-graphql-api
    
    # GraphQL Schema (inline or URI)
    SchemaInline: |
      type Query {
        getUser(id: ID!): User
        listUsers: [User]
      }
      type Mutation {
        createUser(name: String!, email: String!): User
      }
      type User {
        id: ID!
        name: String!
        email: String!
      }
    # OR use SchemaUri: backend/schema.graphql
    
    # Authentication
    Auth:
      Type: AWS_IAM  # or AMAZON_COGNITO_USER_POOLS, API_KEY, OPENID_CONNECT
      # For Cognito:
      # UserPool:
      #   UserPoolId: !Ref UserPool
      #   AwsRegion: !Ref AWS::Region
      #   DefaultAction: ALLOW
    
    # Data Sources
    DataSources:
      DynamoDB:
        UsersTable:
          TableName: !Ref UsersTable
          TableArn: !GetAtt UsersTable.Arn
      Lambda:
        CreateUserFunction:
          FunctionArn: !GetAtt CreateUserFunction.Arn
    
    # Resolvers
    Functions:
      getUserFunction:
        Runtime:
          Name: APPSYNC_JS
          Version: 1.0.0
        DataSource: UsersTable
        CodeUri: backend/resolvers/getUser.js
    
    Resolvers:
      Query:
        getUser:
          Runtime:
            Name: APPSYNC_JS
            Version: 1.0.0
          Pipeline:
            - getUserFunction
      Mutation:
        createUser:
          Runtime:
            Name: APPSYNC_JS
            Version: 1.0.0
          DataSource: CreateUserFunction
    
    # Caching (optional)
    Cache:
      Type: T2_SMALL
      Ttl: 3600
    
    # Logging
    Logging:
      FieldLogLevel: ALL  # NONE, ERROR, ALL
      CloudWatchLogsRoleArn: !GetAtt GraphQLApiLogsRole.Arn
    
    # X-Ray Tracing
    XrayEnabled: true
    
    Tags:
      Environment: !Ref Environment

# IAM Role for GraphQL API Logging
GraphQLApiLogsRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: appsync.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWSAppSyncPushToCloudWatchLogs
```

### Connector Pattern (AWS::Serverless::Connector)
**Recommended Approach:** Use Connectors to automatically manage IAM permissions between resources. Connectors are AWS's recommended first choice for permission management.

**Embedded Connector (Recommended):**
```yaml
# Example 1: Lambda reads from DynamoDB
MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    # ... function properties ...
  Connectors:
    MyConn:
      Properties:
        Destination:
          Id: MyTable
        Permissions:
          - Read

# Example 2: Lambda writes to SQS and reads from S3
ProcessorFunction:
  Type: AWS::Serverless::Function
  Properties:
    # ... function properties ...
  Connectors:
    SQSConnection:
      Properties:
        Destination:
          Id: MyQueue
        Permissions:
          - Write
    S3Connection:
      Properties:
        Destination:
          Id: MyBucket
        Permissions:
          - Read

# Example 3: API Gateway invokes Lambda
MyApi:
  Type: AWS::Serverless::Api
  Properties:
    # ... API properties ...
  Connectors:
    ApiToFunction:
      Properties:
        Destination:
          Id: MyFunction
        Permissions:
          - Write  # API Gateway needs Write to invoke Lambda
```

**Standalone Connector:**
```yaml
# When you need to connect existing resources
MyConnector:
  Type: AWS::Serverless::Connector
  Properties:
    Source:
      Id: SourceFunction
    Destination:
      Id: TargetTable
    Permissions:
      - Read
      - Write
```

**Supported Permissions:**
- `Read` - Grants read/receive/get permissions
- `Write` - Grants write/send/invoke permissions

**Supported Resource Types:**
- Lambda Function
- API Gateway (REST & HTTP)
- Step Functions State Machine
- DynamoDB Table
- SQS Queue
- SNS Topic
- S3 Bucket
- EventBridge Event Bus
- AppSync GraphQL API
- And more...

**Benefits:**
- No need to write IAM policies manually
- Automatically scopes permissions to least privilege
- SAM handles all IAM role and policy creation
- Easier to understand resource relationships
- Reduces security misconfigurations

## 3. Output Definitions
```yaml
Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint
    # CRITICAL: Must reference the explicitly defined API resource name from Resource Patterns (e.g., MyApi)
    # DO NOT use ServerlessRestApi (SAM's implicit logical ID), or CloudFormation will report resource not found
    # Stage name (${Environment}) must match the StageName property in MyApi definition
    Value: !Sub "https://${MyApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
    Export:
      Name: !Sub ${AWS::StackName}-ApiUrl
  
  # Export all resource ARNs/names that frontend might need
  {TableName}Name:
    Value: !Ref {TableName}
  
  UserPoolId:
    Value: !Ref UserPool
    Condition: HasCognito
```

## 4. Cognito Template (Optional)
If blueprint.auth_architecture.strategy == "Cognito User Pools":

```yaml
AWSTemplateFormatVersion: '2010-09-09'

Resources:
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub ${Environment}-users
      AutoVerifiedAttributes:
        - email
      Schema:
        - Name: email
          Required: true
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
      MfaConfiguration: OPTIONAL  # From blueprint
  
  UserPoolClient:
    Type: AWS::Cognito::UserPoolClient
    Properties:
      UserPoolId: !Ref UserPool
      GenerateSecret: false
      ExplicitAuthFlows:
        - ALLOW_USER_PASSWORD_AUTH
        - ALLOW_REFRESH_TOKEN_AUTH

Outputs:
  UserPoolId:
    Value: !Ref UserPool
    Export:
      Name: !Sub ${AWS::StackName}-UserPoolId
  UserPoolClientId:
    Value: !Ref UserPoolClient
    Export:
      Name: !Sub ${AWS::StackName}-UserPoolClientId
```

## 5. Deployment Parameters File
`output/infrastructure/parameters.json`:
```json
{
  "Parameters": {
    "Environment": "dev"
  }
}
```

## 6. SAM Policy Templates Reference

### Available SAM Policy Templates
Common SAM policy templates to use for `Policies` property (89 total available, listing most commonly used):

#### Database & Storage
- `DynamoDBCrudPolicy`: Full CRUD on specific table
  ```yaml
  - DynamoDBCrudPolicy:
      TableName: !Ref MyTable
  ```
- `DynamoDBReadPolicy`: Read-only access to table
- `DynamoDBWritePolicy`: Write-only access to table
- `DynamoDBStreamReadPolicy`: Read from DynamoDB streams
- `DynamoDBBackupFullAccessPolicy`: Create/delete backups
- `DynamoDBReconfigurePolicy`: Update table configuration
- `S3CrudPolicy`: Full CRUD on bucket
  ```yaml
  - S3CrudPolicy:
      BucketName: !Ref MyBucket
  ```
- `S3ReadPolicy`: Read-only access to bucket
- `S3WritePolicy`: Write-only access to bucket
- `S3FullAccessPolicy`: Complete S3 operations including tagging
- `EFSWriteAccessPolicy`: Mount EFS with write access

#### Messaging & Events
- `SQSSendMessagePolicy`: Send messages to queue
  ```yaml
  - SQSSendMessagePolicy:
      QueueName: !GetAtt MyQueue.QueueName
  ```
- `SQSPollerPolicy`: Read/delete from queue
- `SNSPublishMessagePolicy`: Publish to SNS topic
- `SNSCrudPolicy`: Create, publish, subscribe to topics
- `EventBridgePutEventsPolicy`: Put events to EventBridge
  ```yaml
  - EventBridgePutEventsPolicy:
      EventBusName: default
  ```
- `KinesisCrudPolicy`: Full CRUD on Kinesis stream
- `KinesisStreamReadPolicy`: Read-only access to stream
- `FirehoseCrudPolicy`: Full CRUD on Firehose stream
- `FirehoseWritePolicy`: Write-only access to Firehose

#### Compute & Orchestration
- `LambdaInvokePolicy`: Invoke another Lambda
  ```yaml
  - LambdaInvokePolicy:
      FunctionName: !Ref TargetFunction
  ```
- `StepFunctionsExecutionPolicy`: Start Step Functions executions
  ```yaml
  - StepFunctionsExecutionPolicy:
      StateMachineName: !GetAtt MyStateMachine.Name
  ```
- `EcsRunTaskPolicy`: Run ECS tasks

#### Security & Secrets
- `AWSSecretsManagerGetSecretValuePolicy`: Get secret value
  ```yaml
  - AWSSecretsManagerGetSecretValuePolicy:
      SecretArn: !Ref MySecret
  ```
- `AWSSecretsManagerRotationPolicy`: Rotate secrets
- `SSMParameterReadPolicy`: Read SSM parameters
  ```yaml
  - SSMParameterReadPolicy:
      ParameterName: /myapp/config
  ```
- `SSMParameterWithSlashPrefixReadPolicy`: Read SSM with slash prefix
- `KMSDecryptPolicy`: Decrypt with KMS key
- `KMSEncryptPolicy`: Encrypt with KMS key

#### AI/ML Services
- `ComprehendBasicAccessPolicy`: Detect entities, sentiment, language
  ```yaml
  - ComprehendBasicAccessPolicy: {}
  ```
- `RekognitionDetectOnlyPolicy`: Detect faces, labels, text
- `RekognitionLabelsPolicy`: Detect object and moderation labels
- `RekognitionFacesPolicy`: Compare and detect faces
- `RekognitionFacesManagementPolicy`: Add/delete/search faces in collection
- `RekognitionReadPolicy`: List and search faces
- `RekognitionWriteOnlyAccessPolicy`: Create collection and index faces
- `TextractDetectAnalyzePolicy`: Detect and analyze documents
  ```yaml
  - TextractDetectAnalyzePolicy: {}
  ```
- `TextractGetResultPolicy`: Get detection/analysis results
- `TextractPolicy`: Full Textract access
- `PollyFullAccessPolicy`: Full Amazon Polly access
- `SageMakerCreateEndpointPolicy`: Create SageMaker endpoints
- `SageMakerCreateEndpointConfigPolicy`: Create endpoint configs

#### Analytics & Monitoring
- `AthenaQueryPolicy`: Execute Athena queries
  ```yaml
  - AthenaQueryPolicy:
      WorkGroupName: primary
  ```
- `CloudWatchPutMetricPolicy`: Send metrics to CloudWatch
  ```yaml
  - CloudWatchPutMetricPolicy: {}
  ```
- `CloudWatchDashboardPolicy`: Operate on CloudWatch dashboards
- `CloudWatchDescribeAlarmHistoryPolicy`: Describe alarm history
- `FilterLogEventsPolicy`: Filter CloudWatch Logs events
  ```yaml
  - FilterLogEventsPolicy:
      LogGroupName: /aws/lambda/myfunction
  ```

#### Code & CI/CD
- `CodeCommitCrudPolicy`: Full CRUD on CodeCommit repo
- `CodeCommitReadPolicy`: Read-only CodeCommit access
- `CodePipelineLambdaExecutionPolicy`: Report job status to CodePipeline
- `CodePipelineReadOnlyPolicy`: Read CodePipeline details

#### Network & DNS
- `Route53ChangeResourceRecordSetsPolicy`: Change Route53 records
  ```yaml
  - Route53ChangeResourceRecordSetsPolicy:
      HostedZoneId: Z1234567890ABC
  ```
- `VPCAccessPolicy`: Create/delete/describe network interfaces

#### Other Services
- `SESCrudPolicy`: Send email and verify identity
- `SESBulkTemplatedCrudPolicy_v2`: Send templated bulk emails
- `SESEmailTemplateCrudPolicy`: Manage SES templates
- `ServerlessRepoReadWriteAccessPolicy`: Create/list SAR applications
- `ElasticsearchHttpPostPolicy`: POST/PUT to OpenSearch
- `PinpointEndpointAccessPolicy`: Get/update Pinpoint endpoints
- `CostExplorerReadOnlyPolicy`: Read Cost Explorer data
- `CloudFormationDescribeStacksPolicy`: Describe CloudFormation stacks
- `EKSDescribePolicy`: Describe EKS clusters
- `OrganizationsListAccountsPolicy`: List AWS Organizations accounts

### When to Use Inline Policies

Use Inline IAM policies instead of (or in addition to) SAM templates when:

1. **SAM template grants excessive permissions**
   - Example: Only need `s3:GetObject`, but `S3CrudPolicy` grants full CRUD
   
2. **Service lacks SAM policy template**
   - AI/ML Services: Comprehend, Textract, Rekognition, Bedrock, SageMaker
   - Analytics: Athena, Glue, QuickSight
   - Other: AppSync, Pinpoint, Location Services

3. **Complex conditional logic required**
   - Resource-level conditions, IP restrictions, MFA requirements

### Common AI/ML Service Permissions (Inline Policy Examples)

```yaml
Policies:
  - Version: '2012-10-17'
    Statement:
      # Amazon Comprehend
      - Effect: Allow
        Action:
          - comprehend:DetectSentiment
          - comprehend:DetectEntities
          - comprehend:DetectKeyPhrases
        Resource: '*'
      
      # Amazon Textract
      - Effect: Allow
        Action:
          - textract:AnalyzeDocument
          - textract:DetectDocumentText
        Resource: '*'
      
      # Amazon Bedrock
      - Effect: Allow
        Action:
          - bedrock:InvokeModel
        Resource: !Sub arn:aws:bedrock:${AWS::Region}::foundation-model/*
      
      # Amazon Rekognition
      - Effect: Allow
        Action:
          - rekognition:DetectLabels
          - rekognition:DetectText
        Resource: '*'
```

## 7. Permission Management Decision Tree

**Choose your permission strategy based on this priority:**

### 1. Connectors (FIRST CHOICE - Recommended)
✅ **Use When:**
- Connecting any supported AWS resources (Lambda, API Gateway, DynamoDB, SQS, SNS, S3, EventBridge, Step Functions, etc.)
- You want automatic IAM policy generation
- You need least-privilege permissions without IAM expertise

```yaml
MyFunction:
  Type: AWS::Serverless::Function
  Properties:
    # ... properties ...
  Connectors:
    MyConn:
      Properties:
        Destination:
          Id: MyTable
        Permissions:
          - Read
          - Write
```

**Benefits:**
- Zero IAM policy writing
- Automatically scoped permissions
- Easy to understand resource relationships
- AWS managed and updated

### 2. SAM Policy Templates (SECOND CHOICE)
✅ **Use When:**
- Connectors don't support your use case
- You need standard AWS service permissions

```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: !Ref MyTable
  - S3ReadPolicy:
      BucketName: !Ref MyBucket
```

**When NOT to use:**
- You only need subset of permissions (e.g., only `s3:GetObject` not full CRUD)
- Service has no policy template (see AI/ML services below)

### 3. Inline IAM Policies (LAST RESORT)
✅ **Use When:**
- Service lacks both Connector support and Policy Template (AI/ML services)
- Need granular permissions (subset of what policy template grants)
- Complex conditions required (IP restrictions, MFA, resource tags)

```yaml
Policies:
  - Version: '2012-10-17'
    Statement:
      - Effect: Allow
        Action:
          - s3:GetObject  # Only read, not full CRUD
        Resource: !Sub arn:aws:s3:::${BucketName}/readonly/*
```

### 4. Services Requiring Inline Policies

**AI/ML Services** (no policy templates):
- Amazon Bedrock
- Amazon SageMaker (most operations)
- Amazon Kendra
- Amazon Forecast
- Amazon Personalize
- Amazon Translate
- Amazon Transcribe

**Other Services**:
- AWS Glue
- Amazon Athena (beyond basic query)
- AWS AppConfig
- Amazon Location Service
- AWS IoT Core
- Amazon Timestream

### Example: Complete Permission Strategy

```yaml
MyProcessingFunction:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: backend/processor/
    Handler: app.handler
    Runtime: python3.11
    
    # Strategy 1: Use Connectors (preferred)
  Connectors:
    DynamoDBConn:
      Properties:
        Destination:
          Id: ProcessedItemsTable
        Permissions:
          - Read
          - Write
    SQSConn:
      Properties:
        Destination:
          Id: ProcessingQueue
        Permissions:
          - Write
  
  Properties:
    # Strategy 2: Use Policy Templates
    Policies:
      # Secrets Manager (has template)
      - AWSSecretsManagerGetSecretValuePolicy:
          SecretArn: !Ref ApiKeySecret
      
      # S3 Read-only (more granular than S3CrudPolicy)
      - S3ReadPolicy:
          BucketName: !Ref InputBucket
      
      # Strategy 3: Inline for AI/ML services
      - Version: '2012-10-17'
        Statement:
          # Bedrock (no template available)
          - Effect: Allow
            Action:
              - bedrock:InvokeModel
            Resource: !Sub arn:aws:bedrock:${AWS::Region}::foundation-model/anthropic.claude-v2
          
          # Comprehend (has template, but using inline for specific actions)
          - Effect: Allow
            Action:
              - comprehend:DetectSentiment
              - comprehend:DetectPiiEntities
            Resource: '*'
```

## 8. SimpleTable vs DynamoDB Table

### When to Use SimpleTable
Use `AWS::Serverless::SimpleTable` for simple use cases:
- Single attribute primary key (partition key only)
- No sort key needed
- No GSI/LSI required
- Pay-per-request billing preferred

```yaml
SimpleUsersTable:
  Type: AWS::Serverless::SimpleTable
  Properties:
    TableName: !Sub ${Environment}-simple-users
    PrimaryKey:
      Name: userId
      Type: String
    ProvisionedThroughput:
      ReadCapacityUnits: 5
      WriteCapacityUnits: 5
    # If omitted, defaults to PAY_PER_REQUEST
    Tags:
      Environment: !Ref Environment
```

### When to Use DynamoDB Table
Use `AWS::DynamoDB::Table` for advanced use cases:
- Composite primary key (partition + sort key)
- Global Secondary Indexes (GSI)
- Local Secondary Indexes (LSI)
- Streams with custom configuration
- Advanced billing modes

```yaml
AdvancedUsersTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub ${Environment}-advanced-users
    AttributeDefinitions:
      - AttributeName: userId
        AttributeType: S
      - AttributeName: createdAt
        AttributeType: S
      - AttributeName: email
        AttributeType: S
    KeySchema:
      - AttributeName: userId
        KeyType: HASH
      - AttributeName: createdAt
        KeyType: RANGE  # Sort key
    GlobalSecondaryIndexes:
      - IndexName: email-index
        KeySchema:
          - AttributeName: email
            KeyType: HASH
        Projection:
          ProjectionType: ALL
    BillingMode: PAY_PER_REQUEST
    StreamSpecification:
      StreamViewType: NEW_AND_OLD_IMAGES
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    SSESpecification:
      SSEEnabled: true
      SSEType: KMS
      KMSMasterKeyId: !Ref TableEncryptionKey
    Tags:
      - Key: Environment
        Value: !Ref Environment
```

## 9. Complete Modern SAM Template Example

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Modern Serverless Application with Connectors

Globals:
  Function:
    Runtime: python3.11
    Architectures:
      - arm64  # 34% cost savings
    Timeout: 30
    MemorySize: 512
    Tracing: Active
    LoggingConfig:
      LogFormat: JSON
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment

Parameters:
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Resources:
  # HTTP API (cheaper than REST API)
  MyHttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: !Ref Environment
      CorsConfiguration:
        AllowOrigins:
          - "https://example.com"
        AllowMethods:
          - "*"
        AllowHeaders:
          - "*"

  # Lambda with Function URL
  ApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: backend/api/
      Handler: app.handler
      FunctionUrlConfig:
        AuthType: NONE  # Public access
        Cors:
          AllowOrigins:
            - "*"
      Events:
        HttpApiEvent:
          Type: HttpApi
          Properties:
            Path: /users/{id}
            Method: GET
            ApiId: !Ref MyHttpApi
    Connectors:
      TableConn:
        Properties:
          Destination:
            Id: UsersTable
          Permissions:
            - Read

  # DynamoDB Table
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${Environment}-users
      AttributeDefinitions:
        - AttributeName: userId
          AttributeType: S
      KeySchema:
        - AttributeName: userId
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

  # Processing Function with Connectors
  ProcessorFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: backend/processor/
      Handler: processor.handler
      Events:
        QueueEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt ProcessingQueue.Arn
            BatchSize: 10
    Connectors:
      # Read from input bucket
      InputBucketConn:
        Properties:
          Destination:
            Id: InputBucket
          Permissions:
            - Read
      # Write to output bucket
      OutputBucketConn:
        Properties:
          Destination:
            Id: OutputBucket
          Permissions:
            - Write
      # Update DynamoDB
      TableConn:
        Properties:
          Destination:
            Id: UsersTable
          Permissions:
            - Write
    Properties:
      Policies:
        # AI service (no connector support)
        - ComprehendBasicAccessPolicy: {}

  # SQS Queue
  ProcessingQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${Environment}-processing
      VisibilityTimeout: 180

  # S3 Buckets
  InputBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ${Environment}-input-${AWS::AccountId}

  OutputBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ${Environment}-output-${AWS::AccountId}

Outputs:
  HttpApiUrl:
    Description: HTTP API URL
    Value: !Sub "https://${MyHttpApi}.execute-api.${AWS::Region}.amazonaws.com/${Environment}"
  
  FunctionUrl:
    Description: Lambda Function URL
    Value: !GetAtt ApiFunctionUrl.FunctionUrl
```

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
        BUCKET_NAME: !Ref BucketName
    
    # Shared Code Layers
    Layers:
      - !Ref CommonLayer
    
    # Permission Policies (choose one approach)
    Policies:
      # Approach 1: SAM Policy Templates (Recommended)
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
      
      # Approach 2: Inline Policy (Fine-grained control)
      - Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - s3:GetObject
              - s3:PutObject
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
    
    # Username Configuration (email as username)
    UsernameAttributes:
      - email
    
    # Auto Verification
    AutoVerifiedAttributes:
      - email
    
    # ⚠️ Schema is ONLY for custom attributes
    # Standard attributes (email, phone_number, name, etc.) should NOT be defined here
    # Custom attributes example (all custom attributes are optional by default):
    # Schema:
    #   - Name: department
    #     AttributeDataType: String
    #     Mutable: true
    #   - Name: employee_id
    #     AttributeDataType: String
    #     Mutable: false
    
    # Password Policy
    Policies:
      PasswordPolicy:
        MinimumLength: 8
        RequireUppercase: true
        RequireLowercase: true
        RequireNumbers: true
        RequireSymbols: false

UserPoolClient:
  Type: AWS::Cognito::UserPoolClient
  Properties:
    UserPoolId: !Ref UserPool
    ClientName: !Sub ${Environment}-client
    GenerateSecret: false
    ExplicitAuthFlows:
      - ALLOW_USER_PASSWORD_AUTH
      - ALLOW_REFRESH_TOKEN_AUTH
```

### Cognito Triggers (Avoid Circular Dependencies)

**Recommended (SAM-native) pattern**: bind Cognito triggers from the Lambda side using `AWS::Serverless::Function` events.

Why:
- Avoids the circular dependency where API Gateway authorizers need the UserPool ARN, while the UserPool wants a trigger Lambda ARN.
- SAM automatically generates `AWS::Lambda::Permission` so Cognito can invoke the function (no missing invoke permission).

⚠️ Important:
- ❌ Do NOT set `UserPool.Properties.LambdaConfig` to reference a Lambda ARN when using a single template.
- ✅ Use SAM `Events: Cognito` instead.

```yaml
UserPool:
  Type: AWS::Cognito::UserPool
  Properties:
    UserPoolName: !Sub ${Environment}-users
    UsernameAttributes: [email]
    AutoVerifiedAttributes: [email]
    # ❌ Avoid LambdaConfig here to prevent circular dependency

PostConfirmationFunction:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: lambdas/PostConfirmationFunction/
    Handler: handler.lambda_handler
    Runtime: nodejs20.x
    Events:
      PostConfirmationTrigger:
        Type: Cognito
        Properties:
          UserPool: !Ref UserPool
          Trigger: PostConfirmation
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
  
  # Table Name
  TableName:
    Description: DynamoDB table name
    Value: !Ref MyTable
    Export:
      Name: !Sub ${AWS::StackName}-TableName
  
  # S3 Bucket Name
  BucketName:
    Description: S3 bucket name
    Value: !Ref MyBucket
    Export:
      Name: !Sub ${AWS::StackName}-BucketName
  
  # UserPool ID
  UserPoolId:
    Description: Cognito User Pool ID
    Value: !Ref UserPool
    Export:
      Name: !Sub ${AWS::StackName}-UserPoolId
```

## 6. SAM Policy Templates Reference

### Most Commonly Used Policy Templates

#### Database
- `DynamoDBCrudPolicy` - Full DynamoDB operations (GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan)
  ```yaml
  - DynamoDBCrudPolicy:
      TableName: !Ref MyTable
  ```
- `DynamoDBReadPolicy` - DynamoDB read-only operations (GetItem, Query, Scan)
  ```yaml
  - DynamoDBReadPolicy:
      TableName: !Ref MyTable
  ```

#### Storage
- `S3CrudPolicy` - Full S3 operations (GetObject, PutObject, DeleteObject, ListBucket)
  ```yaml
  - S3CrudPolicy:
      BucketName: !Ref MyBucket
  ```
- `S3ReadPolicy` - S3 read-only operations (GetObject, ListBucket)
  ```yaml
  - S3ReadPolicy:
      BucketName: !Ref MyBucket
  ```
- `S3WritePolicy` - S3 write operations (PutObject, DeleteObject)
  ```yaml
  - S3WritePolicy:
      BucketName: !Ref MyBucket
  ```

#### Compute
- `LambdaInvokePolicy` - Invoke other Lambda functions
  ```yaml
  - LambdaInvokePolicy:
      FunctionName: !Ref AnotherFunction
  ```

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
  
  # Lambda Invocation
  - LambdaInvokePolicy:
      FunctionName: !Ref AnotherFunction
  
  # Secrets Manager Read
  - AWSSecretsManagerGetSecretValuePolicy:
      SecretArn: !Ref MySecret
```

### Policy Decision Tree

```
Need to access AWS resources?
├─ Yes → Use SAM Policy Template (Recommended)
│   ├─ DynamoDB → DynamoDBCrudPolicy
│   ├─ S3 → S3CrudPolicy
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

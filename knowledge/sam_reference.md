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
    Runtime: python3.11  # Adjust based on actual code
    Timeout: 30
    MemorySize: 512
    Environment:
      Variables:
        ENVIRONMENT: !Ref Environment
    Tracing: Active  # Enable X-Ray
  Api:  # If using REST API
    Cors:
      AllowOrigin: "'*'"
      AllowHeaders: "'Content-Type,Authorization'"
      AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
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
    CodeUri: backend/lambdas/{lambda_name}/
    Handler: handler.lambda_handler  # From actual code
    Runtime: python3.11  # From file extension
    Environment:
      Variables:
        # Add env vars for all AWS resources this Lambda uses
        TABLE_NAME: !Ref TableName
        QUEUE_URL: !Ref QueueName
        BUCKET_NAME: !Ref BucketName
    Policies:
      # Use SAM policy templates for least privilege
      - DynamoDBCrudPolicy:
          TableName: !Ref TableName
      - SQSSendMessagePolicy:
          QueueName: !GetAtt QueueName.QueueName
      - S3CrudPolicy:
          BucketName: !Ref BucketName
    Events:
      # From blueprint entry_points
      ApiEvent1:
        Type: Api  # or HttpApi
        Properties:
          Path: /api/resource
          Method: GET
      # Add SQS trigger if Lambda processes queue
      QueueEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt QueueName.Arn
          BatchSize: 10
      # Add S3 trigger if Lambda processes uploads
      S3Event:
        Type: S3
        Properties:
          Bucket: !Ref BucketName
          Events: s3:ObjectCreated:*
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

## 3. Output Definitions
```yaml
Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint
    Value: !Sub "https://${ServerlessRestApi}.execute-api.${AWS::Region}.amazonaws.com/Prod"
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
Common SAM policy templates to use for `Policies` property:
- `DynamoDBCrudPolicy`: Full CRUD on specific table
- `DynamoDBReadPolicy`: Read-only access
- `SQSSendMessagePolicy`: Send messages to queue
- `SQSPollerPolicy`: Read/delete from queue
- `S3CrudPolicy`: Full CRUD on bucket
- `S3ReadPolicy`: Read-only access
- `SNSPublishMessagePolicy`: Publish to topic
- `LambdaInvokePolicy`: Invoke another Lambda
- `StepFunctionsExecutionPolicy`: Start executions
- `EventBridgePutEventsPolicy`: Put events to bus

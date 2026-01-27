"""AWS SAM Documentation Reference Tool

Provides quick access to AWS SAM/CloudFormation documentation and
common resource templates for agents.
"""

from typing import Dict


class SAMDocSearchTool:
    """Search and reference AWS SAM documentation.
    
    This tool helps SAM Engineer agent find correct syntax and best
    practices for AWS SAM resources.
    """

    def __init__(self) -> None:
        # Pre-loaded documentation references
        self.doc_links: Dict[str, str] = {
            # Core Compute
            "lambda": "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-function.html",
            "statemachine": "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-statemachine.html",
            "layer": "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-layerversion.html",
            
            # API & Integration
            "api": "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-api.html",
            "httpapi": "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-httpapi.html",
            "eventbridge": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-events-rule.html",
            
            # Messaging
            "sqs": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-sqs-queue.html",
            "sns": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-sns-topic.html",
            
            # Data Storage
            "dynamodb": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-dynamodb-table.html",
            "s3": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-s3-bucket.html",
            
            # Auth
            "cognito_userpool": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cognito-userpool.html",
            "cognito_client": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cognito-userpoolclient.html",
            
            # Frontend
            "amplify": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-amplify-app.html",
            "cloudfront": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudfront-distribution.html",
        }
        
        # Common resource templates
        self.templates: Dict[str, str] = {
            "lambda": """
  FunctionName:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: backend/lambdas/function_name/
      Handler: handler.lambda_handler
      Runtime: python3.11
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          TABLE_NAME: !Ref MyTable
          QUEUE_URL: !Ref MyQueue
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref MyTable
        - SQSSendMessagePolicy:
            QueueName: !GetAtt MyQueue.QueueName
      Events:
        ApiEvent:
          Type: Api
          Properties:
            Path: /resource
            Method: GET
""",
            "dynamodb": """
  TableName:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub ${Environment}-table-name
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST
      StreamSpecification:  # Enable DynamoDB Streams if needed
        StreamViewType: NEW_AND_OLD_IMAGES
      TimeToLiveSpecification:  # Enable TTL for auto-expiring data
        AttributeName: ttl
        Enabled: true
""",
            "sqs": """
  MyQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${Environment}-queue-name
      VisibilityTimeout: 300  # Match Lambda timeout
      MessageRetentionPeriod: 345600  # 4 days
      ReceiveMessageWaitTimeSeconds: 20  # Enable long polling
      RedrivePolicy:  # Dead letter queue for failed messages
        deadLetterTargetArn: !GetAtt MyDLQ.Arn
        maxReceiveCount: 3
  
  MyDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub ${Environment}-queue-name-dlq
      MessageRetentionPeriod: 1209600  # 14 days
""",
            "sns": """
  MyTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub ${Environment}-topic-name
      DisplayName: Topic Display Name
      Subscription:
        - Endpoint: !GetAtt MyFunction.Arn
          Protocol: lambda
  
  MyFunctionInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref MyFunction
      Action: lambda:InvokeFunction
      Principal: sns.amazonaws.com
      SourceArn: !Ref MyTopic
""",
            "eventbridge": """
  MyEventRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub ${Environment}-rule-name
      Description: "Triggers Lambda on schedule or event pattern"
      # Option 1: Schedule (cron/rate)
      ScheduleExpression: "rate(5 minutes)"
      # Option 2: Event pattern
      # EventPattern:
      #   source:
      #     - "aws.s3"
      #   detail-type:
      #     - "Object Created"
      State: ENABLED
      Targets:
        - Arn: !GetAtt MyFunction.Arn
          Id: MyFunctionTarget
  
  MyFunctionEventPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref MyFunction
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt MyEventRule.Arn
""",
            "s3": """
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub ${Environment}-bucket-name
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      CorsConfiguration:  # If needed for frontend uploads
        CorsRules:
          - AllowedOrigins:
              - "*"
            AllowedMethods:
              - GET
              - PUT
              - POST
            AllowedHeaders:
              - "*"
      NotificationConfiguration:  # Trigger Lambda on upload
        LambdaConfigurations:
          - Event: s3:ObjectCreated:*
            Function: !GetAtt MyFunction.Arn
  
  MyFunctionS3Permission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref MyFunction
      Action: lambda:InvokeFunction
      Principal: s3.amazonaws.com
      SourceArn: !GetAtt MyBucket.Arn
""",
            "cognito_userpool": """
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: !Sub ${Environment}-users
      AutoVerifiedAttributes:
        - email
      Schema:
        - Name: email
          Required: true
          Mutable: false
      Policies:
        PasswordPolicy:
          MinimumLength: 8
          RequireUppercase: true
          RequireLowercase: true
          RequireNumbers: true
      MfaConfiguration: OPTIONAL  # OFF | OPTIONAL | ON
      EnabledMfas:
        - SOFTWARE_TOKEN_MFA
""",
            "statemachine": """
  WorkflowStateMachine:
    Type: AWS::Serverless::StateMachine
    Properties:
      DefinitionUri: backend/statemachines/workflow.asl.json
      DefinitionSubstitutions:
        FunctionArn: !GetAtt MyFunction.Arn
        TableName: !Ref MyTable
      Policies:
        - LambdaInvokePolicy:
            FunctionName: !Ref MyFunction
        - DynamoDBCrudPolicy:
            TableName: !Ref MyTable
      Events:
        ApiEvent:
          Type: Api
          Properties:
            Path: /workflow
            Method: POST
""",
            "httpapi": """
  MyHttpApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      CorsConfiguration:
        AllowOrigins:
          - "*"
        AllowMethods:
          - GET
          - POST
          - PUT
          - DELETE
        AllowHeaders:
          - "*"
      Auth:
        Authorizers:
          MyCognitoAuthorizer:
            IdentitySource: $request.header.Authorization
            JwtConfiguration:
              Issuer: !Sub https://cognito-idp.${AWS::Region}.amazonaws.com/${UserPool}
              Audience:
                - !Ref UserPoolClient
        DefaultAuthorizer: MyCognitoAuthorizer
""",
        }

    def search(self, resource_type: str) -> str:
        """Search for documentation on a specific AWS resource type.
        
        Args:
            resource_type: Type of resource (lambda, dynamodb, cognito, etc.)
            
        Returns:
            Documentation link and example template
        """
        resource_type = resource_type.lower().strip()
        
        # Find matching documentation
        doc_link = self.doc_links.get(resource_type, "Not found")
        template = self.templates.get(resource_type, "No template available")
        
        response = f"""
=== AWS SAM Documentation for: {resource_type} ===

Documentation Link:
{doc_link}

Example Template:
{template}

Note: Adjust property values based on your specific requirements.
Always use !Ref for resource references and !Sub for string substitutions.
"""
        return response

    def get_best_practices(self) -> str:
        """Return AWS SAM best practices."""
        return """
=== AWS SAM Best Practices ===

1. Resource References:
   - Use !Ref to reference resource logical IDs
   - Use !GetAtt to get resource attributes (e.g., ARNs)
   - Never hardcode ARNs or resource names

2. Environment Variables:
   - Pass resource references via environment variables
   - Use !Ref: TABLE_NAME: !Ref MyTable
   - Avoid hardcoding values

3. IAM Policies:
   - Use SAM policy templates (DynamoDBCrudPolicy, S3CrudPolicy)
   - Grant least privilege permissions
   - Scope policies to specific resources

4. Function Configuration:
   - Use Globals section for common settings
   - Set appropriate timeout and memory
   - Enable tracing with AWS X-Ray

5. API Gateway:
   - Configure CORS in Globals.Api section
   - Use authorizers for protected endpoints
   - Define request/response models

6. DynamoDB:
   - Use PAY_PER_REQUEST for variable workloads
   - Define Global Secondary Indexes for query patterns
   - Enable point-in-time recovery for production

7. Deployment:
   - Use Parameters for environment-specific values
   - Create separate templates for complex resources (Cognito)
   - Validate with 'sam validate' before deployment

8. Outputs:
   - Export important values (API URLs, table names)
   - Use descriptive output names
   - Include all values needed by frontend
"""

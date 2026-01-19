# AWS SAM Patterns for MAG

This document provides reference patterns for the Architect and Infra
Agents when planning and generating AWS SAM templates.

## DynamoDB Table

```yaml
Resources:
  OrdersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: order_id
          AttributeType: S
      KeySchema:
        - AttributeName: order_id
          KeyType: HASH
```

## Serverless Function with API Gateway Event

```yaml
Resources:
  CartFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.11
      Handler: handlers/cart.lambda_handler
      CodeUri: ./output/src
      Environment:
        Variables:
          TABLE_NAME: OrdersTable
      Events:
        CartPost:
          Type: Api
          Properties:
            Path: /cart
            Method: post
```

## Cognito User Pool (for authentication)

```yaml
Resources:
  UserPool:
    Type: AWS::Cognito::UserPool
    Properties:
      UserPoolName: mag-demo-user-pool
```

These examples are provided so that the Architect can plan appropriate
resources in the JSON blueprint and the Infra Agent can map them to
concrete SAM resources.


# Basic Serverless Architecture for Monolith Migration

This document provides a streamlined, practical approach to migrating monolithic applications to AWS Serverless architecture. 

---

## A Practical Architecture Pattern

```
Client → API Gateway (REST API) → Lambda Functions → DynamoDB / S3
                ↓
        Cognito User Pool (if auth exists in monolith)
                ↓
        CloudWatch (monitoring)
```

---

## Required Components

### 1. API Gateway (REST API)
- **Purpose**: HTTP entry point replacing monolith's web server
- **Configuration**:
  - One API Gateway route per monolith endpoint
  - Keep the same HTTP paths and methods
  - CORS enabled for external clients
  - Cognito Authorizer (if auth exists in monolith)

### 2. Lambda Functions
- **Purpose**: Execute business logic in a serverless environment
- **Design**: Map monolith endpoints to Lambda functions based on application complexity (Single vs Multi-domain)
- **Principle**: Single-responsibility
- **Handler Pattern**:
```python
def lambda_handler(event, context):
    # Extract parameters from API Gateway event
    path_params = event.get('pathParameters', {})
    query_params = event.get('queryStringParameters', {})
    body = json.loads(event.get('body', '{}'))
    
    # Execute business logic (preserved from monolith)
    result = process_business_logic(...)
    
    # Return API Gateway response
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(result)
    }
```

### 3. DynamoDB (if used in monolith)
- **Migration Strategy**: Direct table structure migration
  - Keep table names, partition keys, sort keys unchanged
  - Preserve indexes (GSI/LSI) if they exist
  - Use `PAY_PER_REQUEST` billing mode for simplicity
- **User Table**: Delete authentication fields (Cognito handles auth), keep only profile data as `UserProfiles`

### 4. S3 (if file operations exist in monolith)
- **Use Cases**:
  - File uploads from users
  - Generated files (PDFs, reports, images)
  - Static assets

**IMPORTANT**: Only add S3 if the monolith has explicit file handling code.

### 5. Cognito User Pool (if auth exists in monolith)
- **Purpose**: Replace JWT-based or session-based authentication
- **Configuration**: User attributes (email, name), password policy
- **Auth Endpoints**: DELETE `/register`, `/login`, `/logout`, `/refresh-token` - clients call Cognito API directly
- **Token Validation**: API Gateway uses Cognito Authorizer (no Lambda validation code)
- **Post-Registration**: Use Post-Confirmation Trigger Lambda for business initialization logic

### 6. CloudWatch (always required)
- **Log Groups**: One per Lambda function (retention: 7-30 days)
- **Alarms**: Monitor critical metrics
  - Lambda error rate > 1%
  - API Gateway 4XX/5XX rate
  - DynamoDB throttled requests

---

## Migration Rules

### Rule 1: Preserve All Business Logic
- Copy business logic from monolith exactly
- Only change infrastructure layer:
  - HTTP routing → API Gateway events
  - Database calls → boto3 DynamoDB SDK
  - Auth middleware → Cognito Authorizer

### Rule 2: Delete Infrastructure Code
These files should NOT become Lambda functions:
- `init_dynamodb.py`, `create_tables.py`, `setup_db.py`
- Database migration scripts
- Server startup scripts

**Reason**: SAM template defines infrastructure (tables, indexes, etc.)

**How to handle**:
- Extract table schemas from these files(you can see these in analysis_report.json)
- Define tables in SAM template's `AWS::DynamoDB::Table` resources
- Add initial data via SAM template's `DynamoDB` custom resources or deployment scripts

### Rule 3: Delete User Authentication Table
- Identify the table storing user credentials (email, password hash)
- Do NOT migrate this table to serverless
- Do NOT create Lambda functions that write to this table

**Exception**: If the user table also contains profile data:
- Split into two parts:
  - Credentials → Cognito User Pool
  - Profile data → DynamoDB `UserProfiles` table

### Rule 4: Do Not Add Missing Features
- If monolith has NO authentication → Do NOT add Cognito
- If monolith has NO database → Do NOT add DynamoDB
- If monolith has NO file storage → Do NOT add S3

**Principle**: Migrate what exists, do not enhance

---

## Blueprint JSON Structure

The architecture blueprint should contain these sections:

```json
{
  "metadata": {
    "application_name": "MyApp",
    "architecture_pattern": "Basic Serverless Architecture",
    "has_authentication": true,
    "has_database": true,
    "has_file_storage": false
  },
  "lambda_functions": [
    {
      "name": "user-service",
      "runtime": "python3.11",
      "handler": "handler.lambda_handler",
      "source_files": ["app/routes/users.py", "app/services/user_service.py"],
      "entry_points": ["/users", "/users/{id}"],
      "environment_variables": {
        "USER_PROFILES_TABLE": "${UserProfilesTable}"
      }
    }
  ],
  "dynamodb_tables": [
    {
      "logical_name": "UserProfiles",
      "purpose": "Store user profile data (NOT credentials)",
      "schema_source_files": ["app/models/user.py"]
    },
    {
      "logical_name": "Orders",
      "purpose": "Store order data",
      "schema_source_files": ["app/models/order.py"]
    }
  ],
  "s3_buckets": [],
  "cognito": {
    "enabled": true,
    "user_pool_attributes": ["email", "name"],
    "password_policy": {
      "min_length": 8,
      "require_symbols": true
    },
    "triggers": {
      "post_confirmation": {
        "enabled": true,
        "purpose": "Create user profile in UserProfiles table"
      }
    }
  },
  "api_gateway": {
    "type": "REST",
    "cors": {
      "allow_origins": ["*"],
      "allow_methods": ["GET", "POST", "PUT", "DELETE"]
    },
    "authorizer": "Cognito"
  },
  "dropped_functions": [
    {
      "name": "/register",
      "reason": "Replaced by Cognito User Pool registration"
    },
    {
      "name": "/login",
      "reason": "Replaced by Cognito User Pool authentication"
    },
    {
      "name": "init_dynamodb.py",
      "reason": "Table creation handled by SAM template"
    },
    {
      "name": "Users table (credentials)",
      "reason": "User authentication moved to Cognito"
    }
  ]
}
```

## Common Mistakes to Avoid

### ❌ Mistake 1: Keeping User Credentials Table
**Wrong**:
```yaml
UsersTable:  # Contains email, password_hash, salt
  Type: AWS::DynamoDB::Table
  # ...
```

**Correct**:
```yaml
UserProfilesTable:  # Contains bio, preferences, avatar_url
  Type: AWS::DynamoDB::Table
  # ...
```

### ❌ Mistake 2: Creating Auth Lambda Functions
**Wrong**:
```yaml
LoginFunction:
  Type: AWS::Serverless::Function
  # Validates credentials, returns JWT
```

**Correct**:
```
# No Lambda function needed
# Client calls Cognito API directly:
# - cognito-idp.InitiateAuth()
```

### ❌ Mistake 3: Creating Infrastructure Lambda
**Wrong**:
```yaml
InitDynamoDBFunction:
  Type: AWS::Serverless::Function
  Events:
    Api:
      Type: Api
      Path: /admin/init-db
```

**Correct**:
```yaml
# Use CloudFormation custom resource
# Or use DynamoDB table initialization in SAM template
```

### ❌ Mistake 4: Adding Features Not in Monolith
**Wrong**: Monolith has no auth → Added Cognito anyway
**Correct**: Monolith has no auth → No Cognito in serverless version

## Summary

**Key Rules**:
1. Delete user credentials table (replaced by Cognito)
2. Delete infrastructure scripts (replaced by SAM template)
3. Delete auth endpoints (handled by Cognito)
4. Preserve all business logic exactly
5. Do not add features that don't exist in monolith

**Success Criteria**:
- All monolith API endpoints work in serverless
- Data is correctly stored and retrieved
- Authentication works (if it existed in monolith)
- Business logic produces same results as monolith

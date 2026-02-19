# Todo Serverless Application

## Overview

This is a serverless migration of a monolithic Todo application to AWS Lambda, API Gateway, DynamoDB, and Cognito. The application preserves all todo functionality while moving authentication to AWS Cognito.

## Project Structure

```
output/
├── lambdas/
│   ├── GetItemsFunction/
│   │   ├── handler.js
│   │   └── package.json
│   ├── GetItemByIdFunction/
│   │   ├── handler.js
│   │   └── package.json
│   ├── CreateItemFunction/
│   │   ├── handler.js
│   │   └── package.json
│   ├── UpdateItemFunction/
│   │   ├── handler.js
│   │   └── package.json
│   ├── MarkItemDoneFunction/
│   │   ├── handler.js
│   │   └── package.json
│   ├── DeleteItemFunction/
│   │   ├── handler.js
│   │   └── package.json
│   └── PostConfirmationFunction/
│       ├── handler.js
│       └── package.json
├── layers/
│   └── dynamodb-utils/
│       └── nodejs/
│           ├── dynamodb-utils.js
│           └── package.json
└── README.md
```

## Prerequisites

1. **AWS CLI** installed and configured with appropriate credentials
2. **SAM CLI** (Serverless Application Model) installed
3. **Node.js 18.x** (runtime for Lambda functions)
4. **Git** for version control

## Quick Start

1. **Clone the repository** (if applicable)
2. **Navigate to the project root**
3. **Build the application**:
   ```bash
   sam build
   ```
4. **Deploy the application**:
   ```bash
   sam deploy --guided
   ```
   Follow the interactive prompts to provide:
   - Stack name
   - AWS Region
   - Environment (dev, staging, prod)
   - Confirm changes

## Deployment Steps

### 1. Build the Application

```bash
sam build
```

This command will:
- Install dependencies for each Lambda function
- Package the application code
- Prepare the deployment artifacts

### 2. Deploy with SAM

```bash
sam deploy --guided
```

During guided deployment, SAM will create:
- 7 Lambda functions (6 for todos, 1 for Cognito trigger)
- 2 DynamoDB tables (UserProfiles, Todos)
- API Gateway with REST API
- Cognito User Pool with post-confirmation trigger
- IAM roles and policies

### 3. Environment Variables

Lambda functions use the following environment variables:

| Function | Environment Variables | Purpose |
|----------|----------------------|---------|
| GetItemsFunction | `TODOS_TABLE` | Name of the Todos DynamoDB table |
| GetItemByIdFunction | `TODOS_TABLE` | Name of the Todos DynamoDB table |
| CreateItemFunction | `TODOS_TABLE`, `USER_PROFILES_TABLE` | Todo and user profile tables |
| UpdateItemFunction | `TODOS_TABLE`, `USER_PROFILES_TABLE` | Todo and user profile tables |
| MarkItemDoneFunction | `TODOS_TABLE`, `USER_PROFILES_TABLE` | Todo and user profile tables |
| DeleteItemFunction | `TODOS_TABLE`, `USER_PROFILES_TABLE` | Todo and user profile tables |
| PostConfirmationFunction | `USER_PROFILES_TABLE` | User profile table |

### 4. API Endpoints

All endpoints require Cognito authentication via the `Authorization` header with a Bearer token.

| Method | Path | Lambda Function | Description |
|--------|------|-----------------|-------------|
| GET | `/item` | GetItemsFunction | Get all todo items for the authenticated user |
| GET | `/item/{id}` | GetItemByIdFunction | Get a specific todo item by ID |
| POST | `/item` | CreateItemFunction | Create a new todo item |
| PUT | `/item/{id}` | UpdateItemFunction | Update an existing todo item |
| POST | `/item/{id}/done` | MarkItemDoneFunction | Mark a todo item as completed |
| DELETE | `/item/{id}` | DeleteItemFunction | Delete a todo item |

### 5. Testing with Sample Requests

#### Prerequisites for Testing:
1. Create a user in Cognito User Pool
2. Authenticate to get an ID token

#### Sample cURL Commands:

```bash
# Get all todo items
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/item \
  -H "Authorization: Bearer {id-token}"

# Create a new todo item
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/item \
  -H "Authorization: Bearer {id-token}" \
  -H "Content-Type: application/json" \
  -d '{"item": "Buy groceries", "completed": false}'

# Update a todo item
curl -X PUT https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/item/{todoId} \
  -H "Authorization: Bearer {id-token}" \
  -H "Content-Type: application/json" \
  -d '{"item": "Buy groceries and cook dinner", "completed": true}'

# Mark item as done
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/item/{todoId}/done \
  -H "Authorization: Bearer {id-token}"

# Delete a todo item
curl -X DELETE https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/item/{todoId} \
  -H "Authorization: Bearer {id-token}"
```

## Frontend Integration Guide

### Authentication (Replaced Endpoints)

The following monolith endpoints have been replaced by AWS Cognito:

#### 1. Registration
**Old endpoint:** `POST /register`  
**New implementation:** Use AWS Amplify Auth.signUp()

```javascript
import { Auth } from 'aws-amplify';

async function registerUser(email, password, name) {
  try {
    const result = await Auth.signUp({
      username: email,
      password,
      attributes: {
        email,
        name
      }
    });
    console.log('Registration successful:', result);
    return result;
  } catch (error) {
    console.error('Registration failed:', error);
    throw error;
  }
}
```

#### 2. Login
**Old endpoint:** `POST /login`  
**New implementation:** Use AWS Amplify Auth.signIn()

```javascript
import { Auth } from 'aws-amplify';

async function loginUser(email, password) {
  try {
    const user = await Auth.signIn(email, password);
    console.log('Login successful:', user);
    return user;
  } catch (error) {
    console.error('Login failed:', error);
    throw error;
  }
}
```

#### 3. Token Management
**Old implementation:** Custom JWT generation/validation  
**New implementation:** Cognito automatically generates and validates JWT tokens

```javascript
// Get current authenticated user
const user = await Auth.currentAuthenticatedUser();

// Get current session with tokens
const session = await Auth.currentSession();
const idToken = session.getIdToken().getJwtToken();
const accessToken = session.getAccessToken().getJwtToken();

// Use token in API requests
fetch('/api/endpoint', {
  headers: {
    'Authorization': `Bearer ${idToken}`
  }
});
```

### API Calls

All API calls to todo endpoints require the Cognito ID token in the Authorization header:

```javascript
import { Auth } from 'aws-amplify';

async function getTodoItems() {
  try {
    const session = await Auth.currentSession();
    const idToken = session.getIdToken().getJwtToken();
    
    const response = await fetch('https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/item', {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${idToken}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch todo items:', error);
    throw error;
  }
}
```

## Dropped Components

The following components from the monolith have been dropped and replaced:

### 1. Authentication Endpoints
- `POST /register` → Replaced by Cognito User Pool
- `POST /login` → Replaced by Cognito User Pool

### 2. Authentication Middleware
- `authenticateToken` middleware → Replaced by API Gateway Cognito Authorizer
- `verifyToken` function → Token validation handled by API Gateway
- `generateToken` function → Token generation handled by Cognito

### 3. Database Schema
- **Users table** (with email, password_hash) → Replaced by:
  - Cognito User Pool (credentials)
  - UserProfiles table (profile data only)
- **bcryptjs password hashing** → Handled by Cognito with secure hashing

### 4. Initialization Script
- `init-db.js` → Table creation handled by SAM template CloudFormation resources

## Database Architecture

### UserProfiles Table
- **Partition Key:** `userId` (Cognito Sub UUID)
- **Attributes:** `email`, `name`, `createdAt`
- **Purpose:** Store user profile data only (credentials handled by Cognito)

### Todos Table
- **Partition Key:** `userId` (Cognito Sub UUID)
- **Sort Key:** `todoId` (UUID)
- **Attributes:** `item`, `completed`, `creation_date`, `lastupdate_date`
- **Purpose:** Store todo items with user ownership

## Monitoring and Logging

- **CloudWatch Logs:** Each Lambda function logs to its own log group
- **X-Ray Tracing:** Enabled for end-to-end tracing
- **API Gateway Access Logs:** Enabled for API monitoring
- **CloudWatch Metrics:** Automatic monitoring of Lambda invocations, errors, and duration

## Troubleshooting

### Common Issues:

1. **"User: ... is not authorized to perform: dynamodb:..."**
   - Ensure IAM roles have appropriate DynamoDB permissions
   - Check if the table names in environment variables are correct

2. **"Missing Authentication Token"**
   - Verify the Authorization header is present and contains a valid Cognito ID token
   - Check if the API Gateway route is configured with Cognito authorizer

3. **Cognito trigger failures**
   - Check PostConfirmationFunction logs in CloudWatch
   - Verify USER_PROFILES_TABLE environment variable is set
   - Ensure the Lambda has permissions to write to DynamoDB

4. **CORS errors**
   - Verify API Gateway CORS configuration
   - Check if frontend origin is allowed

## Support

For issues with:
- **Application code:** Refer to this README and Lambda function logs
- **Infrastructure:** The SAM Engineer will handle template.yaml and CloudFormation resources
- **Authentication:** Refer to AWS Cognito documentation and frontend integration guide

## Notes

- This application uses the "Infrastructure over Code" principle for authentication
- All userId fields are String type (Cognito Sub UUID)
- The SAM Engineer will create all infrastructure files (template.yaml, etc.)
- No infrastructure files are included in this output - they will be generated separately
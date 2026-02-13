# TodoApp Serverless Application

This is a serverless migration of a monolithic Todo application to AWS Lambda and API Gateway with Cognito authentication.

## Project Structure

```
output/
├── lambdas/
│   └── todo/                    # Domain: todo
│       ├── get-items/          # GET /item
│       │   ├── handler.js
│       │   └── package.json
│       ├── get-item-by-id/     # GET /item/{id}
│       │   ├── handler.js
│       │   └── package.json
│       ├── create-item/        # POST /item
│       │   ├── handler.js
│       │   └── package.json
│       ├── update-item/        # PUT /item/{id}
│       │   ├── handler.js
│       │   └── package.json
│       ├── mark-item-done/     # POST /item/{id}/done
│       │   ├── handler.js
│       │   └── package.json
│       └── delete-item/        # DELETE /item/{id}
│           ├── handler.js
│           └── package.json
├── layers/
│   └── common-utils/           # Shared utilities layer
│       └── nodejs/
│           ├── common-utils/
│           │   └── db.js       # DynamoDB client wrapper
│           └── package.json
└── README.md                   # This file
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- SAM CLI installed
- Node.js 18.x (for local testing)

## Quick Start

1. **Clone the repository** (if applicable)
2. **Build the application**
   ```bash
   sam build
   ```
3. **Deploy with guided configuration**
   ```bash
   sam deploy --guided
   ```
   Follow the prompts to set stack name, AWS region, and environment.

## Deployment Steps

1. **Build the SAM application**
   ```bash
   sam build
   ```

2. **Deploy to AWS**
   ```bash
   sam deploy --guided
   ```
   - Stack Name: `todo-app` (or choose your own)
   - AWS Region: e.g., `us-east-1`
   - Environment: `dev`, `staging`, or `prod`
   - Confirm changes and allow SAM to create IAM roles.

3. **Note the outputs** after deployment, especially:
   - `ApiGatewayUrl`: The base URL of your REST API
   - `UserPoolId`: Cognito User Pool ID for frontend integration
   - `UserPoolClientId`: Cognito App Client ID for frontend

## Environment Variables

Each Lambda function uses the following environment variables:

- `TODO_TABLE`: DynamoDB table name for Todo items (automatically set by SAM template)

## API Endpoints

All endpoints require Cognito authentication via API Gateway Authorizer.

| Method | Path | Lambda Function | Description |
|--------|------|-----------------|-------------|
| GET | /item | get-items | Retrieve all todo items for the authenticated user |
| GET | /item/{id} | get-item-by-id | Retrieve a specific todo item by ID |
| POST | /item | create-item | Create a new todo item |
| PUT | /item/{id} | update-item | Update an existing todo item |
| POST | /item/{id}/done | mark-item-done | Mark a todo item as completed |
| DELETE | /item/{id} | delete-item | Delete a todo item |

### Authentication

- Authentication is handled by Cognito User Pool.
- API Gateway uses a Cognito Authorizer to validate JWT tokens.
- The Lambda functions receive the authenticated user's claims in `event.requestContext.authorizer.claims`.
- The user identifier is extracted from `cognito:username` claim (or `sub` as fallback).

## Testing with Sample Requests

### Prerequisites for Testing

1. Create a user in the Cognito User Pool (via AWS Console or Amplify).
2. Obtain an ID token after login.

### Example cURL Commands

Replace:
- `{API_URL}` with your deployed API Gateway URL
- `{ID_TOKEN}` with a valid Cognito ID token
- `{TODO_ID}` with an existing todo item ID

#### Get all items
```bash
curl -X GET "{API_URL}/item" \
  -H "Authorization: Bearer {ID_TOKEN}"
```

#### Get specific item
```bash
curl -X GET "{API_URL}/item/{TODO_ID}" \
  -H "Authorization: Bearer {ID_TOKEN}"
```

#### Create item
```bash
curl -X POST "{API_URL}/item" \
  -H "Authorization: Bearer {ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"item": "Buy groceries", "completed": false}'
```

#### Update item
```bash
curl -X PUT "{API_URL}/item/{TODO_ID}" \
  -H "Authorization: Bearer {ID_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"item": "Buy groceries and cook dinner", "completed": true}'
```

#### Mark item as done
```bash
curl -X POST "{API_URL}/item/{TODO_ID}/done" \
  -H "Authorization: Bearer {ID_TOKEN}"
```

#### Delete item
```bash
curl -X DELETE "{API_URL}/item/{TODO_ID}" \
  -H "Authorization: Bearer {ID_TOKEN}"
```

## Frontend Integration

### Authentication Flow

1. **User Registration**: Use AWS Amplify Auth.signUp()
   ```javascript
   import { Auth } from 'aws-amplify';
   await Auth.signUp({
     username: 'user@example.com',
     password: 'Password123',
     attributes: {
       email: 'user@example.com',
       preferred_username: 'user123'
     }
   });
   ```

2. **User Login**: Use AWS Amplify Auth.signIn()
   ```javascript
   import { Auth } from 'aws-amplify';
   await Auth.signIn('user@example.com', 'Password123');
   ```

3. **Get Current Session**: Retrieve the ID token for API calls
   ```javascript
   import { Auth } from 'aws-amplify';
   const session = await Auth.currentSession();
   const idToken = session.getIdToken().getJwtToken();
   ```

### API Calls from Frontend

```javascript
// Example using fetch with Amplify authentication
import { Auth } from 'aws-amplify';

async function getTodoItems() {
  const session = await Auth.currentSession();
  const idToken = session.getIdToken().getJwtToken();
  
  const response = await fetch(`${API_URL}/item`, {
    headers: {
      'Authorization': `Bearer ${idToken}`
    }
  });
  
  return await response.json();
}
```

## Dropped Endpoints

The following monolith endpoints have been replaced by AWS managed services:

| Endpoint | Replacement | Reason |
|----------|-------------|--------|
| POST /register | Cognito User Pool | User registration handled by Cognito via Amplify Auth.signUp() |
| POST /login | Cognito User Pool | User authentication handled by Cognito via Amplify Auth.signIn() |
| authenticateToken middleware | API Gateway Cognito Authorizer | Token validation moved to API Gateway layer |
| JWT utilities (generateToken, verifyToken) | Cognito JWT tokens | Token generation/validation handled by Cognito |
| Users table | Cognito User Pool | User storage moved to Cognito; no separate users table needed |
| init-db.js script | CloudFormation resources | Table creation handled by SAM template |

## Shared Layer

The `common-utils` layer provides a shared DynamoDB DocumentClient and helper functions. Lambda functions can use this layer to avoid duplicating database configuration code.

## Monitoring and Logging

- Lambda functions output logs to CloudWatch Logs.
- API Gateway access logs are enabled.
- Use AWS X-Ray for distributed tracing (enabled in SAM template).

## Cleanup

To delete the application and all associated resources:

```bash
sam delete
```

## Support

For issues, refer to AWS SAM documentation or CloudFormation stack events in the AWS Console.

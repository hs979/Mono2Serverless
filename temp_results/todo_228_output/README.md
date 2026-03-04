# TodoMonolith Serverless Application

This is a serverless migration of the TodoMonolith application, using AWS Lambda, API Gateway, DynamoDB, and Amazon Cognito.

## Project Structure

```
output/
├── layers/
│   └── base-node-utils/
│       ├── nodejs/
│       │   └── node_modules/
│       │       └── internalClient/
│       │           └── index.js
│       └── package.json
├── lambdas/
│   └── todo/
│       ├── todo-get-items/
│       │   ├── handler.js
│       │   └── package.json
│       ├── todo-get-item-by-id/
│       │   ├── handler.js
│       │   └── package.json
│       ├── todo-create-item/
│       │   ├── handler.js
│       │   └── package.json
│       ├── todo-update-item/
│       │   ├── handler.js
│       │   └── package.json
│       ├── todo-mark-item-done/
│       │   ├── handler.js
│       │   └── package.json
│       └── todo-delete-item/
│           ├── handler.js
│           └── package.json
└── README.md
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- SAM CLI installed (version 1.85.0 or later)
- Node.js 18.x (for local testing)

## Quick Start

1. **Clone the repository**

2. **Build the application**
   ```bash
   sam build
   ```

3. **Deploy the application**
   ```bash
   sam deploy --guided
   ```
   During the guided deployment, you'll be prompted for:
   - Stack name
   - AWS Region
   - Environment (dev, staging, prod)
   - Confirm changes before deploy
   - Allow SAM CLI to create IAM roles

## Deployment Steps

1. The SAM template (to be created by sam_engineer) will deploy:
   - 6 Lambda functions (one per todo endpoint)
   - API Gateway REST API with Cognito authorizer
   - DynamoDB Todo table
   - Cognito User Pool
   - Lambda layer with shared utilities

2. Environment variables are configured in the SAM template:
   - `TODO_TABLE`: DynamoDB table name for todo items
   - `AWS_REGION`: AWS region (automatically set)

3. The Lambda functions are attached to the `base-node-utils` layer which provides:
   - AWS SDK v2
   - UUID library
   - `invokeLambda` utility for inter-Lambda communication

## API Endpoints

All endpoints require Cognito authentication. Include the Cognito JWT token in the `Authorization` header as `Bearer <token>`.

### GET /item
Retrieve all todo items for the authenticated user.

**Query Parameters (optional):**
- `limit`: Number of items to return (default: 10)
- `exclusiveStartKey`: Pagination token (JSON encoded)

**Response:**
```json
{
  "Items": [
    {
      "userId": "cognito-sub-uuid",
      "id": "todo-id",
      "item": "Todo content",
      "completed": false,
      "creation_date": "2023-01-01T00:00:00.000Z",
      "lastupdate_date": "2023-01-01T00:00:00.000Z"
    }
  ],
  "Count": 1,
  "LastEvaluatedKey": null
}
```

### GET /item/{id}
Retrieve a specific todo item by ID.

**Path Parameters:**
- `id`: Todo item ID

**Response:**
```json
{
  "userId": "cognito-sub-uuid",
  "id": "todo-id",
  "item": "Todo content",
  "completed": false,
  "creation_date": "2023-01-01T00:00:00.000Z",
  "lastupdate_date": "2023-01-01T00:00:00.000Z"
}
```

### POST /item
Create a new todo item.

**Request Body:**
```json
{
  "item": "New todo item",
  "completed": false
}
```

**Response:**
```json
{
  "message": "Todo item created successfully",
  "item": {
    "userId": "cognito-sub-uuid",
    "id": "generated-uuid",
    "item": "New todo item",
    "completed": false,
    "creation_date": "2023-01-01T00:00:00.000Z",
    "lastupdate_date": "2023-01-01T00:00:00.000Z"
  }
}
```

### PUT /item/{id}
Update an existing todo item.

**Path Parameters:**
- `id`: Todo item ID

**Request Body:**
```json
{
  "item": "Updated todo item",
  "completed": true
}
```

**Response:**
```json
{
  "message": "Todo item updated successfully",
  "Attributes": {
    "userId": "cognito-sub-uuid",
    "id": "todo-id",
    "item": "Updated todo item",
    "completed": true,
    "creation_date": "2023-01-01T00:00:00.000Z",
    "lastupdate_date": "2023-01-02T00:00:00.000Z"
  }
}
```

### POST /item/{id}/done
Mark a todo item as completed.

**Path Parameters:**
- `id`: Todo item ID

**Response:**
```json
{
  "message": "Todo item marked as completed",
  "Attributes": {
    "userId": "cognito-sub-uuid",
    "id": "todo-id",
    "item": "Todo content",
    "completed": true,
    "creation_date": "2023-01-01T00:00:00.000Z",
    "lastupdate_date": "2023-01-02T00:00:00.000Z"
  }
}
```

### DELETE /item/{id}
Delete a todo item.

**Path Parameters:**
- `id`: Todo item ID

**Response:**
```json
{
  "message": "Todo item deleted successfully"
}
```

## Testing

### Local Testing with SAM

1. **Invoke a function locally:**
   ```bash
   sam local invoke TodoGetItemsFunction --event events/get-items.json
   ```

2. **Start local API Gateway:**
   ```bash
   sam local start-api
   ```
   Then test with curl:
   ```bash
   curl -X GET http://localhost:3000/item \
     -H "Authorization: Bearer <cognito-token>"
   ```

### Sample Events

Create test event files in the `events/` directory:

**get-items.json:**
```json
{
  "httpMethod": "GET",
  "path": "/item",
  "queryStringParameters": {
    "limit": "5"
  },
  "requestContext": {
    "authorizer": {
      "claims": {
        "sub": "cognito-sub-uuid-example"
      }
    }
  }
}
```

## Frontend Integration

### Authentication

**Replaced endpoints:**
- `POST /register` → Use AWS Amplify `Auth.signUp()`
- `POST /login` → Use AWS Amplify `Auth.signIn()`

**Example:**
```javascript
import { Auth } from 'aws-amplify';

// Register
await Auth.signUp({
  username: 'user@example.com',
  password: 'Password123!',
  attributes: {
    email: 'user@example.com',
    name: 'John Doe'
  }
});

// Login
await Auth.signIn('user@example.com', 'Password123!');

// Get current session
const session = await Auth.currentSession();
const token = session.getIdToken().getJwtToken();
```

### API Calls

Include the Cognito JWT token in the Authorization header:
```javascript
const response = await fetch('https://api-id.execute-api.region.amazonaws.com/dev/item', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
```

## Dropped Components

The following monolith components were replaced by AWS managed services:

| Component | Replacement | Reason |
|-----------|-------------|--------|
| `POST /register` | Cognito User Pool | User registration handled by Cognito |
| `POST /login` | Cognito User Pool | Authentication handled by Cognito |
| `authenticateToken` middleware | API Gateway Cognito Authorizer | Token validation at API Gateway layer |
| `verifyToken` function | API Gateway Cognito Authorizer | Token validation at API Gateway layer |
| `generateToken` function | Cognito User Pool | Tokens generated by Cognito |
| `init-db.js` script | CloudFormation resources | Table creation handled by SAM template |
| Users table | Cognito User Pool | User credentials stored in Cognito |
| `bcryptjs` dependency | Cognito User Pool | Password hashing handled by Cognito |
| `jsonwebtoken` dependency | Cognito & API Gateway | JWT handling moved to AWS services |

## Notes

- All `userId` fields are now Cognito Sub UUIDs (string type)
- The Todo table uses composite primary key: `userId` (HASH) and `id` (RANGE)
- CORS is enabled for all origins (`*`)
- API Gateway automatically validates Cognito JWT tokens
- No business logic is needed for post-confirmation triggers
- The `invokeLambda` utility in the layer is available for future inter-Lambda communication

## Troubleshooting

- **Check CloudWatch Logs:** Each Lambda function has its own log group
- **API Gateway Logs:** Access logs are enabled for the API stage
- **Cognito User Pool:** Users can be managed in the AWS Console
- **DynamoDB:** Use the console to inspect table items and metrics

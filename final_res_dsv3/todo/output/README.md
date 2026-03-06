# TodoApp Serverless Application

This is a serverless version of the TodoApp, migrated from a monolithic Express.js application to AWS Lambda functions with API Gateway and DynamoDB.

## Project Structure

```
output/
├── lambdas/
│   └── todo/
│       ├── todo-get-items/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── todo-get-item-by-id/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── todo-create-item/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── todo-update-item/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── todo-mark-item-done/
│       │   ├── handler.py
│       │   └── requirements.txt
│       └── todo-delete-item/
│           ├── handler.py
│           └── requirements.txt
├── layers/
│   └── shared/
│       ├── python/
│       │   └── shared_utils.py
│       └── requirements.txt
└── README.md
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- SAM CLI installed
- Python 3.11 (for local testing)
- Node.js (for SAM CLI)

## Quick Start

1. **Clone the repository** (if applicable)
2. **Navigate to the project directory**
3. **Build the application**
   ```bash
   sam build
   ```
4. **Deploy the application**
   ```bash
   sam deploy --guided
   ```
   Follow the prompts to provide stack name, AWS region, and confirm IAM role creation.

## Deployment Steps

### 1. Build the SAM application
```bash
sam build
```

### 2. Deploy with guided configuration
```bash
sam deploy --guided
```

During guided deployment, you'll be asked for:
- **Stack Name**: Name for your CloudFormation stack (e.g., `todoapp-serverless`)
- **AWS Region**: Region to deploy to (e.g., `us-east-1`)
- **Confirm changes before deploy**: Yes/No
- **Allow SAM CLI IAM role creation**: Yes (SAM will create necessary IAM roles)
- **Save arguments to configuration file**: Yes (saves settings to `samconfig.toml`)

### 3. After deployment

SAM will output the API Gateway endpoint URL. Note this URL for frontend integration.

## Environment Variables

Each Lambda function uses the following environment variables:

- `TODO_TABLE`: DynamoDB table name (automatically set by SAM template)

These are configured in the SAM template and do not need manual setup.

## API Endpoints

All endpoints require Cognito authentication. Include the ID token in the `Authorization` header as `Bearer <token>`.

### GET /item
Retrieve all todo items for the authenticated user.

**Response:**
```json
{
  "Items": [
    {
      "cognito-username": "user123",
      "id": "uuid",
      "item": "Buy groceries",
      "completed": false,
      "creation_date": "2023-10-01T12:00:00Z",
      "lastupdate_date": "2023-10-01T12:00:00Z"
    }
  ],
  "Count": 1
}
```

### GET /item/{id}
Retrieve a specific todo item by ID.

**Path Parameters:**
- `id`: Todo item ID

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
    "cognito-username": "user123",
    "id": "uuid",
    "item": "New todo item",
    "completed": false,
    "creation_date": "2023-10-01T12:00:00Z",
    "lastupdate_date": "2023-10-01T12:00:00Z"
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

### POST /item/{id}/done
Mark a todo item as completed.

**Path Parameters:**
- `id`: Todo item ID

### DELETE /item/{id}
Delete a todo item.

**Path Parameters:**
- `id": Todo item ID

## Testing with CURL

### Prerequisites for testing:
1. Deploy the application and note the API endpoint
2. Create a user in Cognito User Pool
3. Authenticate and obtain an ID token

### Example: Get all todo items
```bash
curl -X GET \
  https://<api-id>.execute-api.<region>.amazonaws.com/Prod/item \
  -H 'Authorization: Bearer <cognito-id-token>'
```

### Example: Create a todo item
```bash
curl -X POST \
  https://<api-id>.execute-api.<region>.amazonaws.com/Prod/item \
  -H 'Authorization: Bearer <cognito-id-token>' \
  -H 'Content-Type: application/json' \
  -d '{"item": "Test todo", "completed": false}'
```

## Authentication

Authentication is handled by Amazon Cognito:

1. **User Registration/Sign-in**: Use Cognito hosted UI or Amplify libraries
2. **Token Validation**: API Gateway validates JWT tokens automatically
3. **User Identity**: Lambda functions receive the authenticated user's username via `event.requestContext.authorizer.claims`

**Dropped Endpoints:**
- `POST /register` - Replaced by Cognito User Pool registration
- `POST /login` - Replaced by Cognito User Pool authentication

## Frontend Integration

### Using Amplify JavaScript Library

```javascript
import { Amplify, API } from 'aws-amplify';
import awsconfig from './aws-exports';

Amplify.configure(awsconfig);

// Get todo items
async function getTodos() {
  try {
    const response = await API.get('TodoApi', '/item');
    return response.Items;
  } catch (error) {
    console.error('Error fetching todos:', error);
  }
}

// Create todo item
async function createTodo(item) {
  try {
    const response = await API.post('TodoApi', '/item', {
      body: { item, completed: false }
    });
    return response;
  } catch (error) {
    console.error('Error creating todo:', error);
  }
}
```

### Using Fetch API

```javascript
const API_ENDPOINT = 'https://<api-id>.execute-api.<region>.amazonaws.com/Prod';
const ID_TOKEN = 'cognito-id-token';

async function getTodos() {
  const response = await fetch(`${API_ENDPOINT}/item`, {
    headers: {
      'Authorization': `Bearer ${ID_TOKEN}`
    }
  });
  return await response.json();
}
```

## Shared Layer

The shared layer (`layers/shared`) contains common utilities:

- `shared_utils.py`: Helper functions for response formatting, user ID extraction, DynamoDB client initialization, and input validation
- Used by all Lambda functions to reduce code duplication

## Error Handling

All Lambda functions return appropriate HTTP status codes:

- `200`: Success
- `400`: Bad request (invalid input)
- `401`: Unauthorized (missing or invalid token)
- `404`: Resource not found
- `500`: Internal server error

## Monitoring and Logging

- **CloudWatch Logs**: Each Lambda function logs to CloudWatch
- **CloudWatch Metrics**: Monitor invocation count, duration, errors
- **X-Ray Tracing**: Enable for distributed tracing

## Cleanup

To delete the application and all resources:

```bash
sam delete
```

## Notes

- The SAM template (not included here) will be generated by the SAM Engineer
- DynamoDB table is automatically created with partition key `cognito-username` and sort key `id`
- CORS is configured to allow requests from any origin (`*`)
- All business logic from the original monolith is preserved

# Todo Application - Serverless Deployment Guide

This document provides instructions for deploying the Todo Application as a serverless architecture on AWS.

## Project Structure

```
output/
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

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured with credentials
3. **AWS SAM CLI** installed (for local testing and deployment)
4. **Node.js 18.x** (matching Lambda runtime)
5. **Git** for version control

## Quick Start

1. **Clone the repository** (if applicable)
2. **Navigate to the project directory**
3. **Build the application**
   ```bash
   sam build
   ```
4. **Deploy with guided configuration**
   ```bash
   sam deploy --guided
   ```
   Follow the prompts to provide:
   - Stack name (e.g., `todo-app`)
   - AWS Region
   - Environment (dev, staging, prod)
   - Confirm changes before deployment
   - Allow SAM CLI to create IAM roles

## Deployment Steps

### 1. Build the Application

```bash
sam build
```

This command processes the SAM template (to be created by the SAM engineer), downloads dependencies, and prepares the deployment package.

### 2. Deploy to AWS

```bash
sam deploy --guided
```

For subsequent deployments without prompts:
```bash
sam deploy
```

### 3. Monitor Deployment

Check the CloudFormation stack in the AWS Console for deployment status.

## Environment Variables

Each Lambda function requires the following environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `TODOS_TABLE` | DynamoDB table name for todo items | `TodosTable-ABC123` |

These will be automatically set by the SAM template.

## API Endpoints

Once deployed, the API Gateway will provide a base URL (e.g., `https://abc123.execute-api.region.amazonaws.com/Prod`).

All endpoints require Cognito authentication via the `Authorization` header with a valid JWT token.

### Available Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/item` | Get all todo items for the authenticated user |
| GET | `/item/{id}` | Get a specific todo item by ID |
| POST | `/item` | Create a new todo item |
| PUT | `/item/{id}` | Update an existing todo item |
| POST | `/item/{id}/done` | Mark a todo item as completed |
| DELETE | `/item/{id}` | Delete a todo item |

### Authentication

Authentication is handled by Amazon Cognito via API Gateway Authorizer. The frontend should:

1. Use AWS Amplify or Cognito SDK to authenticate users
2. Obtain JWT tokens (ID token or access token)
3. Include the token in the `Authorization` header as `Bearer <token>`

## Testing

### Sample cURL Commands

Replace `{API_URL}` with your deployed API URL and `{COGNITO_TOKEN}` with a valid JWT token.

#### Get All Items
```bash
curl -X GET \
  "{API_URL}/item" \
  -H "Authorization: Bearer {COGNITO_TOKEN}"
```

#### Create Item
```bash
curl -X POST \
  "{API_URL}/item" \
  -H "Authorization: Bearer {COGNITO_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"item": "Buy groceries", "completed": false}'
```

#### Update Item
```bash
curl -X PUT \
  "{API_URL}/item/{item-id}" \
  -H "Authorization: Bearer {COGNITO_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"item": "Buy groceries and cook dinner", "completed": true}'
```

#### Mark Item as Done
```bash
curl -X POST \
  "{API_URL}/item/{item-id}/done" \
  -H "Authorization: Bearer {COGNITO_TOKEN}"
```

#### Delete Item
```bash
curl -X DELETE \
  "{API_URL}/item/{item-id}" \
  -H "Authorization: Bearer {COGNITO_TOKEN}"
```

## Frontend Integration

### Authentication Flow

1. **User Registration/Sign-in**: Use AWS Amplify Auth or Cognito Hosted UI
2. **Token Acquisition**: After authentication, obtain JWT tokens
3. **API Calls**: Include token in `Authorization` header

### Example Frontend Code (JavaScript)

```javascript
// Using fetch API
const apiUrl = 'https://your-api-id.execute-api.region.amazonaws.com/Prod';
const token = await Auth.currentSession().getIdToken().getJwtToken(); // AWS Amplify

// Get all items
const response = await fetch(`${apiUrl}/item`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log(data.Items);
```

## Dropped Endpoints

The following endpoints from the original monolith have been replaced by AWS managed services:

| Endpoint | Replacement |
|----------|-------------|
| `POST /register` | Cognito User Pool registration (frontend calls Cognito SDK) |
| `POST /login` | Cognito User Pool authentication (frontend calls Cognito SDK) |

All JWT token generation and validation is now handled by Cognito and API Gateway.

## Troubleshooting

### Common Issues

1. **403 Forbidden**: Check if the Cognito token is valid and not expired
2. **500 Internal Server Error**: Check CloudWatch Logs for Lambda function errors
3. **Missing Environment Variables**: Verify SAM template sets `TODOS_TABLE` correctly

### Logs

Each Lambda function logs to CloudWatch Logs. Use the AWS Console or CLI to view logs:

```bash
aws logs tail /aws/lambda/{function-name} --follow
```

## Cleanup

To delete all deployed resources:

```bash
sam delete
```

This will delete the CloudFormation stack and all associated resources.

## Support

For issues with the application code, contact the development team. For AWS infrastructure issues, refer to AWS documentation or contact AWS Support.

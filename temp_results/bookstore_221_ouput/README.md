# Bookstore Serverless Application

This is a serverless migration of the Bookstore monolith application to AWS Lambda and API Gateway.

## Project Structure

```
output/
├── layers/
│   └── base-node-utils/
│       ├── nodejs/
│       │   └── internalClient/
│       │       └── index.js
│       └── package.json
├── lambdas/
│   ├── bestsellers/
│   │   ├── bestsellers-get/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   ├── books/
│   │   ├── books-get-all/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── books-get-by-id/
│   │       ├── handler.js
│   │       └── package.json
│   ├── cart/
│   │   ├── cart-get-all/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   ├── cart-get-by-book/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   ├── cart-create/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   ├── cart-update/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── cart-delete/
│   │       ├── handler.js
│   │       └── package.json
│   ├── orders/
│   │   ├── orders-get-all/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── orders-create/
│   │       ├── handler.js
│   │       └── package.json
│   ├── recommendations/
│   │   ├── recommendations-get-all/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── recommendations-get-by-book/
│   │       ├── handler.js
│   │       └── package.json
│   ├── search/
│   │   └── search-get/
│   │       ├── handler.js
│   │       └── package.json
│   └── internal/
│       ├── bestsellers-update/
│       │   ├── handler.js
│       │   └── package.json
│       ├── search-sync-index/
│       │   ├── handler.js
│       │   └── package.json
│       ├── search-sync-delete/
│       │   ├── handler.js
│       │   └── package.json
│       └── search-sync-bulk/
│           ├── handler.js
│           └── package.json
└── README.md
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS SAM CLI installed
- Node.js 18.x (for local testing)
- Docker (for SAM local testing)

## Quick Start

1. **Build the application**
   ```bash
   sam build
   ```

2. **Deploy the application**
   ```bash
   sam deploy --guided
   ```
   Follow the prompts to provide stack name, AWS region, and parameter overrides.

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
- Stack Name: e.g., "bookstore-serverless"
- AWS Region: e.g., us-east-1
- Parameter overrides:
  - Environment: dev/staging/prod
  - RedisEnabled: true/false
  - NeptuneEnabled: true/false
  - ElasticsearchEnabled: true/false

### 3. Post-deployment configuration
After deployment, note the API Gateway endpoint URL from the outputs. You'll need to:
1. Update the `INTERNAL_API_BASE_URL` environment variable for internal Lambda calls
2. Configure Cognito User Pool if not already set up

## Environment Variables

Each Lambda function requires specific environment variables:

### Common Variables
- `BOOKS_TABLE`: DynamoDB table name for books
- `CART_TABLE`: DynamoDB table name for cart
- `ORDERS_TABLE`: DynamoDB table name for orders
- `INTERNAL_API_BASE_URL`: Base URL for internal API calls (set to API Gateway URL)

### Service-Specific Variables
- **Redis-enabled functions** (bestsellers-get, bestsellers-update, orders-create):
  - `REDIS_ENABLED`: true/false
  - `REDIS_HOST`: Redis endpoint
  - `REDIS_PORT`: Redis port
  - `REDIS_PASSWORD`: Redis password (optional)

- **Neptune-enabled functions** (recommendations-get-all, recommendations-get-by-book):
  - `NEPTUNE_ENABLED`: true/false
  - `NEPTUNE_ENDPOINT`: Neptune endpoint
  - `NEPTUNE_PORT`: Neptune port (default: 8182)

- **Elasticsearch-enabled functions** (search-get, search-sync-*):
  - `ES_ENABLED`: true/false
  - `ES_ENDPOINT`: Elasticsearch endpoint
  - `ES_INDEX`: Elasticsearch index name (default: lambda-index)

## API Endpoints

All public endpoints are protected by Cognito Authorizer (except where noted).

### Public Endpoints (No Authentication Required)
- `GET /bestsellers` - Get top 20 bestseller book IDs
- `GET /books` - List all books or filter by category
- `GET /books/{id}` - Get book details by ID
- `GET /recommendations` - Get book recommendations
- `GET /recommendations/{bookId}` - Get friends who purchased a book
- `GET /search?q={query}` - Search books

### Protected Endpoints (Require Cognito Authentication)
- `GET /cart` - Get user's cart items
- `GET /cart/{bookId}` - Get specific cart item
- `POST /cart` - Add item to cart
- `PUT /cart` - Update cart item quantity
- `DELETE /cart` - Remove item from cart
- `GET /orders` - Get user's orders
- `POST /orders` - Create new order (checkout)

### Internal Endpoints (Not exposed via API Gateway)
- `POST /internal/bestsellers/update` - Update bestseller rankings
- `POST /internal/search-sync/index` - Index book in Elasticsearch
- `POST /internal/search-sync/delete` - Delete book from Elasticsearch
- `POST /internal/search-sync/bulk` - Bulk index books

## Testing

### Test with curl

1. **Get authentication token** (using AWS Amplify or Cognito directly)
2. **Make authenticated requests**:

```bash
# Get books (no auth required)
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/books

# Get cart (requires auth)
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart \
  -H "Authorization: Bearer {id-token}"

# Create order
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/orders \
  -H "Authorization: Bearer {id-token}" \
  -H "Content-Type: application/json" \
  -d '{"books": [{"bookId": "book1", "price": 29.99, "quantity": 1}]}'
```

### Test with SAM Local

```bash
# Start local API Gateway
sam local start-api

# Test endpoint
curl http://127.0.0.1:3000/books
```

## Frontend Integration

### Authentication
Authentication endpoints (`/register`, `/login`, `/refresh`, `/me`) have been replaced with Amazon Cognito. Frontend should use AWS Amplify for authentication:

```javascript
import { Auth } from 'aws-amplify';

// Sign up
await Auth.signUp({
  username: email,
  password: password,
  attributes: {
    email: email,
    name: name
  }
});

// Sign in
await Auth.signIn(username, password);

// Get current user
const user = await Auth.currentAuthenticatedUser();
const token = user.signInUserSession.idToken.jwtToken;

// Use token in API requests
fetch('/api/endpoint', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

### API Calls
All API calls should include the Cognito ID token in the Authorization header:
```javascript
const response = await fetch('https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart', {
  headers: {
    'Authorization': `Bearer ${idToken}`,
    'Content-Type': 'application/json'
  }
});
```

## Dropped Endpoints

The following monolith endpoints have been replaced by AWS services:

| Endpoint | Replacement | Frontend Integration |
|----------|-------------|---------------------|
| POST /register | Cognito User Pool | `Auth.signUp()` |
| POST /login | Cognito User Pool | `Auth.signIn()` |
| POST /refresh | Cognito automatic token refresh | Automatic in Amplify |
| GET /me | Cognito User Pool | `Auth.currentAuthenticatedUser()` |

## Database Schema

### DynamoDB Tables
1. **Books Table**
   - Partition key: `id` (String)
   - Attributes: name, author, category, price, inventory, etc.
   - GSI: category-index (category)

2. **Cart Table**
   - Partition key: `customerId` (String) - Cognito User ID
   - Sort key: `bookId` (String)
   - Attributes: quantity, price

3. **Orders Table**
   - Partition key: `customerId` (String) - Cognito User ID
   - Sort key: `orderId` (String)
   - Attributes: orderDate, books (list)

## Monitoring and Logging

- All Lambda functions log to CloudWatch Logs
- X-Ray tracing is recommended for debugging
- API Gateway access logs are enabled
- Use CloudWatch Metrics and Dashboards for monitoring

## Troubleshooting

### Common Issues

1. **Missing environment variables**: Ensure all required environment variables are set in the SAM template
2. **CORS errors**: API Gateway is configured with CORS, but ensure frontend uses correct origin
3. **Authentication errors**: Verify Cognito User Pool is properly configured and tokens are valid
4. **Database connection errors**: Check DynamoDB table names and IAM permissions

### Debugging Lambda Functions

1. Check CloudWatch Logs for each Lambda function
2. Use SAM local for local debugging
3. Enable X-Ray tracing for distributed tracing

## Security Notes

- All user data is scoped by `customerId` (Cognito User ID)
- API Gateway validates JWT tokens before invoking Lambda functions
- DynamoDB tables use IAM policies for fine-grained access control
- Environment variables for sensitive data (passwords, endpoints)
- Consider using AWS Secrets Manager for production credentials

## Support

For issues with the serverless application, refer to:
- AWS SAM documentation
- AWS Lambda documentation
- Amazon API Gateway documentation
- Amazon Cognito documentation

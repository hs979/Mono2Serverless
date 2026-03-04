# Bookstore Serverless Application

This is a serverless migration of a monolithic bookstore application to AWS Lambda. The application uses AWS Lambda, API Gateway, DynamoDB, Cognito, and other AWS services.

## Project Structure

```
output/
├── layers/
│   └── base-node-utils/
│       ├── nodejs/
│       │   └── node_modules/
│       │       ├── internalClient/
│       │       │   └── index.js
│       │       ├── dynamodbHelper/
│       │       │   └── index.js
│       │       ├── responseHelper/
│       │       │   └── index.js
│       │       └── userHelper/
│       │           └── index.js
│       └── package.json
├── lambdas/
│   ├── bestsellers/
│   │   ├── bestsellers-get/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   ├── bestsellers-update/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── bestsellers-scheduled-update/
│   │       ├── handler.js
│   │       └── package.json
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
│   │   ├── cart-get-by-bookid/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   ├── cart-add-item/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   ├── cart-update-item/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── cart-delete-item/
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
│   │   └── recommendations-get-by-bookid/
│   │       ├── handler.js
│   │       └── package.json
│   ├── search/
│   │   └── search-get/
│   │       ├── handler.js
│   │       └── package.json
│   └── user/
│       └── user-post-confirmation/
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

1. **Clone the repository**
2. **Build the application**
   ```bash
   sam build
   ```
3. **Deploy the application**
   ```bash
   sam deploy --guided
   ```
   Follow the prompts to provide stack name, AWS region, and other parameters.

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
- **Stack Name**: Name for your CloudFormation stack (e.g., `bookstore-serverless`)
- **AWS Region**: AWS region to deploy to
- **Parameter overrides**: You can accept defaults or provide custom values

### 3. Post-deployment configuration

After deployment, note the following outputs from CloudFormation:
- **API Gateway endpoint URL**
- **Cognito User Pool ID**
- **Cognito App Client ID**

## Environment Variables

Each Lambda function has specific environment variables. Key variables include:

### Database Tables
- `BOOKS_TABLE`: DynamoDB table for books
- `CART_TABLE`: DynamoDB table for shopping cart
- `ORDERS_TABLE`: DynamoDB table for orders
- `USER_PROFILES_TABLE`: DynamoDB table for user profiles

### External Services
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_ENABLED`: Redis configuration for bestsellers
- `NEPTUNE_ENDPOINT`, `NEPTUNE_ENABLED`: Neptune graph database for recommendations
- `ELASTICSEARCH_ENDPOINT`, `ELASTICSEARCH_ENABLED`: Elasticsearch for search
- `BESTSELLERS_UPDATE_FUNCTION_NAME`: Name of the internal bestsellers-update Lambda

## API Endpoints

All API endpoints are protected by Cognito Authorizer (except possibly public endpoints). Include the Cognito ID token in the `Authorization` header as `Bearer <token>`.

### Books
- `GET /books` - List all books (optional query param: `category`)
- `GET /books/{id}` - Get book by ID

### Cart
- `GET /cart` - Get all cart items for current user
- `GET /cart/{bookId}` - Get specific cart item
- `POST /cart` - Add item to cart (body: `{bookId, quantity, price}`)
- `PUT /cart` - Update cart item quantity (body: `{bookId, quantity}`)
- `DELETE /cart` - Remove item from cart (body: `{bookId}`)

### Orders
- `GET /orders` - Get all orders for current user
- `POST /orders` - Create new order (body: `{books: [{bookId, price, quantity}, ...]}`)

### Bestsellers
- `GET /bestsellers` - Get top 20 bestsellers

### Recommendations
- `GET /recommendations` - Get personalized book recommendations
- `GET /recommendations/{bookId}` - Get friends who purchased a specific book

### Search
- `GET /search?q={query}` - Search books by keyword

## Testing

### Using cURL

1. **Get authentication token** (using AWS Amplify or Cognito directly)
2. **Make authenticated requests**:
   ```bash
   curl -X GET https://<api-gateway-url>/books \
        -H "Authorization: Bearer <cognito-id-token>"
   ```

### Sample Requests

**Get all books:**
```bash
curl -X GET https://<api-gateway-url>/books \
     -H "Authorization: Bearer <token>"
```

**Add item to cart:**
```bash
curl -X POST https://<api-gateway-url>/cart \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"bookId": "book123", "quantity": 2, "price": 29.99}'
```

**Create order:**
```bash
curl -X POST https://<api-gateway-url>/orders \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"books": [{"bookId": "book123", "quantity": 1, "price": 29.99}]}'
```

## Frontend Integration

### Authentication

Traditional authentication endpoints (`/register`, `/login`, `/refresh`, `/me`) have been replaced with Amazon Cognito. Frontend should use AWS Amplify or Cognito SDK:

```javascript
// Using AWS Amplify
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
await Auth.signIn(email, password);

// Get current user
const user = await Auth.currentAuthenticatedUser();
const token = user.signInUserSession.idToken.jwtToken;
```

### API Calls

Include the Cognito ID token in the Authorization header:
```javascript
const response = await fetch('https://<api-gateway-url>/cart', {
    headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    }
});
```

## Dropped Endpoints

The following endpoints from the monolith have been replaced by Cognito:
- `POST /register` → Use Cognito User Pool sign-up
- `POST /login` → Use Cognito User Pool sign-in
- `POST /refresh` → Use Cognito automatic token refresh
- `GET /me` → Use Cognito User Pool `currentAuthenticatedUser`

## Lambda Layers

The application uses a shared Lambda layer `base-node-utils` that includes:
- AWS SDK v2
- Shared utilities:
  - `internalClient`: For inter-Lambda invocation
  - `dynamodbHelper`: DynamoDB operations wrapper
  - `responseHelper`: Standard API response formatting
  - `userHelper`: User ID extraction from events

## Monitoring and Logging

- All Lambda functions log to CloudWatch Logs
- Use AWS X-Ray for distributed tracing
- Monitor DynamoDB metrics for table performance

## Cleanup

To delete the entire stack and all resources:
```bash
aws cloudformation delete-stack --stack-name <stack-name>
```

## Notes

- The SAM template (template.yaml) is generated by the `sam_engineer` agent
- Infrastructure-as-code files are not included in this output
- Ensure proper IAM permissions are configured for Lambda functions to access DynamoDB, invoke other Lambdas, etc.
- Consider enabling VPC for Lambdas that need to access Redis, Neptune, or Elasticsearch in a VPC

# Shopping Cart Serverless Application

This is a serverless migration of the shopping cart monolith application to AWS Lambda and API Gateway.

## Project Structure

```
output/
├── lambdas/
│   ├── products/
│   │   ├── product-get-all/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   └── product-get-by-id/
│   │       ├── handler.py
│   │       └── requirements.txt
│   └── cart/
│       ├── cart-list/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── cart-add/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── cart-update/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── cart-migrate/
│       │   ├── handler.py
│       │   └── requirements.txt
│       ├── cart-checkout/
│       │   ├── handler.py
│       │   └── requirements.txt
│       └── cart-get-total/
│           ├── handler.py
│           └── requirements.txt
└── README.md
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **SAM CLI** installed
4. **Python 3.11** (for local testing)
5. **Node.js** (if using SAM CLI)

## Quick Start

### 1. Build the application

```bash
sam build
```

### 2. Deploy with guided configuration

```bash
sam deploy --guided
```

Follow the prompts to configure:
- Stack name
- AWS Region
- Confirm changes
- Save configuration to `samconfig.toml`

### 3. After deployment

Note the API Gateway endpoint URL from the output. It will look like:
```
https://{api-id}.execute-api.{region}.amazonaws.com/{stage}
```

## Environment Variables

Each Lambda function requires the following environment variable:
- `DYNAMODB_TABLE_NAME`: The DynamoDB table name (will be provided by SAM template)

## API Endpoints

### Public Endpoints (No Authentication Required)

1. **GET /product** - Get all products
   - Lambda: `product-get-all`

2. **GET /product/{product_id}** - Get product by ID
   - Lambda: `product-get-by-id`

3. **GET /cart** - Get cart contents (anonymous or authenticated)
   - Lambda: `cart-list`
   - For anonymous users: Include `x-cart-id` header or one will be generated

4. **POST /cart** - Add item to cart (anonymous or authenticated)
   - Lambda: `cart-add`
   - Request body: `{"productId": "123", "quantity": 1}`
   - For anonymous users: Include `x-cart-id` header

5. **PUT /cart/{product_id}** - Update cart item quantity
   - Lambda: `cart-update`
   - Request body: `{"quantity": 2}`
   - For anonymous users: Include `x-cart-id` header

6. **GET /cart/{product_id}/total** - Get total quantity of product across all carts
   - Lambda: `cart-get-total`

### Authenticated Endpoints (Require Cognito Token)

7. **POST /cart/migrate** - Migrate anonymous cart to authenticated user
   - Lambda: `cart-migrate`
   - Requires: `x-cart-id` header with anonymous cart ID
   - Requires: Cognito Authorization header

8. **POST /cart/checkout** - Checkout and clear cart
   - Lambda: `cart-checkout`
   - Requires: Cognito Authorization header

## Authentication

Authentication is handled by Amazon Cognito and API Gateway Authorizer:

1. **Frontend Integration**:
   - Use AWS Amplify or Cognito SDK for user registration/login
   - Get JWT tokens from Cognito
   - Include token in `Authorization` header as `Bearer <token>`

2. **Anonymous Users**:
   - Use `x-cart-id` header to maintain cart session
   - Cart ID is returned in response headers for anonymous operations

## Testing

### Test with curl

#### Get all products:
```bash
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/product
```

#### Add item to cart (anonymous):
```bash
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart \
  -H "Content-Type: application/json" \
  -H "x-cart-id: anonymous-cart-123" \
  -d '{"productId": "prod123", "quantity": 2}'
```

#### Get cart contents:
```bash
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart \
  -H "x-cart-id: anonymous-cart-123"
```

#### Authenticated request (with Cognito token):
```bash
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart \
  -H "Authorization: Bearer {cognito-jwt-token}"
```

## Frontend Integration Guide

### 1. User Authentication

Use AWS Amplify for easiest integration:

```javascript
import { Amplify, Auth } from 'aws-amplify';

Amplify.configure({
  Auth: {
    region: 'us-east-1',
    userPoolId: '{your-user-pool-id}',
    userPoolWebClientId: '{your-app-client-id}',
  }
});

// Sign up
await Auth.signUp({
  username: 'user@example.com',
  password: 'Password123!',
  attributes: {
    email: 'user@example.com',
    name: 'John Doe'
  }
});

// Sign in
const user = await Auth.signIn('user@example.com', 'Password123!');
const token = user.signInUserSession.idToken.jwtToken;

// Use token in API requests
fetch('/cart', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

### 2. Anonymous Cart Management

For users who haven't logged in:

```javascript
// Generate or retrieve cart ID
let cartId = localStorage.getItem('cartId');
if (!cartId) {
  cartId = generateUUID(); // Use a UUID generator
  localStorage.setItem('cartId', cartId);
}

// Include cart ID in all cart requests
fetch('/cart', {
  headers: {
    'x-cart-id': cartId
  }
});

// When user logs in, migrate the cart
fetch('/cart/migrate', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'x-cart-id': cartId
  }
});
```

### 3. Error Handling

All endpoints return standard HTTP status codes:
- `200`: Success
- `400`: Bad request (missing parameters, invalid data)
- `401`: Unauthorized (missing or invalid token for protected endpoints)
- `404`: Resource not found
- `500`: Internal server error

## Dropped Endpoints

The following endpoints from the monolith have been replaced by AWS managed services:

- `POST /auth/register` - Replaced by Cognito User Pool registration
- `POST /auth/login` - Replaced by Cognito User Pool authentication
- All authentication middleware - Replaced by API Gateway Cognito Authorizer
- User table operations - Managed by Cognito

## Monitoring and Logging

- **CloudWatch Logs**: Each Lambda function logs to CloudWatch
- **CloudWatch Metrics**: Monitor invocation counts, durations, errors
- **X-Ray**: Enable for distributed tracing

## Security Notes

1. **CORS**: Configured to allow requests from any origin (`*`). Adjust for production.
2. **API Keys**: Consider adding API keys for rate limiting in production.
3. **Cognito**: Configure appropriate user pool policies and MFA settings.
4. **DynamoDB**: Use fine-grained IAM policies for least privilege access.

## Troubleshooting

### Common Issues

1. **Missing x-cart-id header**: Anonymous cart operations require this header.
2. **Invalid token**: Ensure Cognito token is valid and not expired.
3. **CORS errors**: Verify the frontend origin is allowed in API Gateway.
4. **DynamoDB permissions**: Check Lambda execution role has proper DynamoDB permissions.

### Logs

Check CloudWatch logs for each Lambda function:
```bash
aws logs tail /aws/lambda/{function-name} --follow
```

## Support

For issues with the SAM template or infrastructure, contact the SAM Engineer.
For application code issues, review the Lambda handler implementations.

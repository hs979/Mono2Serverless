# Shopping Cart Serverless Application

## Overview

This is a serverless migration of a shopping cart monolith application to AWS Lambda. The application provides RESTful APIs for product browsing and cart management, with authentication handled by Amazon Cognito.

## Project Structure

```
output/
├── layers/
│   └── base-python-utils/
│       ├── python/
│       │   └── internal_client.py
│       └── requirements.txt
├── lambdas/
│   ├── products-list/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── products-get/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-list/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-add/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-update/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-migrate/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-checkout/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-total/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-delete-items/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── product-aggregate-update/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── cart-cleanup-expired/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── cognito-post-confirmation/
│       ├── handler.py
│       └── requirements.txt
└── README.md
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **AWS SAM CLI** installed
4. **Python 3.11** (for local testing)
5. **Node.js** (for AWS SDK if needed)

## Quick Start

```bash
# Build the application
sam build

# Deploy with guided configuration
sam deploy --guided
```

## Deployment Steps

1. **Build the application**:
   ```bash
   sam build
   ```

2. **Deploy to AWS**:
   ```bash
   sam deploy --guided
   ```
   During guided deployment, you'll be prompted for:
   - Stack name
   - AWS Region
   - Parameter overrides
   - Confirmation of IAM role creation

3. **Configure Cognito User Pool**:
   - After deployment, note the Cognito User Pool ID from outputs
   - Configure app client settings
   - Set up domain for hosted UI

4. **Update Frontend Configuration**:
   Update your frontend application to use the deployed API Gateway endpoint and Cognito User Pool.

## Environment Variables

Each Lambda function uses environment variables configured in the SAM template:

### Common Variables
- `DYNAMODB_TABLE_NAME`: The main DynamoDB table name
- `AWS_REGION`: AWS region (default: us-east-1)

### Function-Specific Variables
- `PRODUCT_AGGREGATE_UPDATE_FUNCTION_NAME`: Used by cart-add and cart-update functions
- `CART_DELETE_FUNCTION_NAME`: Used by cart-checkout and cart-migrate functions

## API Endpoints

### Public Endpoints (No Authentication Required)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/product` | Get all products |
| GET | `/product/{product_id}` | Get product details |
| GET | `/cart` | Get cart contents (anonymous or authenticated) |
| POST | `/cart` | Add product to cart |
| PUT | `/cart/{product_id}` | Update cart item quantity |
| GET | `/cart/{product_id}/total` | Get total quantity of product across all carts |

### Authenticated Endpoints (Cognito Required)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/cart/migrate` | Migrate anonymous cart to authenticated user |
| POST | `/cart/checkout` | Checkout cart (clears cart) |

### Authentication Flow

1. Frontend uses AWS Amplify or Cognito SDK for user registration/login
2. API Gateway validates JWT tokens using Cognito Authorizer
3. Authenticated requests include user ID in `event.requestContext.authorizer.claims.sub`
4. Anonymous users use `X-Cart-ID` header for cart persistence

## Testing

### Sample cURL Requests

#### Get All Products
```bash
curl -X GET https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/product
```

#### Add to Cart (Anonymous)
```bash
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart \
  -H "Content-Type: application/json" \
  -d '{"productId": "prod123", "quantity": 2}'
```

#### Add to Cart (Authenticated)
```bash
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {cognito-jwt-token}" \
  -d '{"productId": "prod123", "quantity": 2}'
```

#### Migrate Cart
```bash
curl -X POST https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/cart/migrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {cognito-jwt-token}" \
  -H "X-Cart-ID: {cart-id-from-previous-response}"
```

## Frontend Integration

### Authentication

Replace the old authentication endpoints with AWS Cognito:

```javascript
// Old approach (removed)
// POST /auth/register
// POST /auth/login

// New approach using AWS Amplify
import { Auth } from 'aws-amplify';

// User registration
await Auth.signUp({
  username: 'user@example.com',
  password: 'Password123!',
  attributes: {
    email: 'user@example.com',
    preferred_username: 'user@example.com'
  }
});

// User login
await Auth.signIn('user@example.com', 'Password123!');

// Get current session
const session = await Auth.currentSession();
const jwtToken = session.getIdToken().getJwtToken();
```

### API Calls

```javascript
// Example API call with authentication
const apiUrl = 'https://{api-id}.execute-api.{region}.amazonaws.com/{stage}';
const jwtToken = await getJwtTokenFromCognito();

const response = await fetch(`${apiUrl}/cart`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json'
  }
});

// For anonymous cart operations, use X-Cart-ID header
const cartId = localStorage.getItem('cartId') || generateCartId();
const response = await fetch(`${apiUrl}/cart`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Cart-ID': cartId
  },
  body: JSON.stringify({
    productId: 'prod123',
    quantity: 1
  })
});

// Save cart ID from response headers
const newCartId = response.headers.get('X-Cart-ID');
if (newCartId) {
  localStorage.setItem('cartId', newCartId);
}
```

## Dropped Endpoints

The following monolith endpoints have been replaced by AWS Cognito:

| Endpoint | Replacement | Reason |
|----------|-------------|--------|
| POST `/auth/register` | Cognito User Pool | User registration handled by AWS Cognito |
| POST `/auth/login` | Cognito User Pool | User authentication handled by AWS Cognito |
| All auth middleware | API Gateway Cognito Authorizer | Token validation at API Gateway layer |
| Password hashing functions | Cognito User Pool | Password management handled by AWS Cognito |
| JWT token generation | Cognito User Pool | JWT generation handled by AWS Cognito |

## Internal Functions

The following internal Lambda functions are invoked via AWS SDK (not directly accessible via API):

1. **cart-delete-items**: Deletes all items for a user/cart
2. **product-aggregate-update**: Updates product total quantity counters
3. **cart-cleanup-expired**: Cleans up expired cart items (fallback for TTL)
4. **cognito-post-confirmation**: Creates user profile after Cognito registration

## Monitoring and Logging

- All Lambda functions have CloudWatch Logs enabled
- API Gateway access logging can be configured
- X-Ray tracing is recommended for performance monitoring
- Use CloudWatch Alarms for error rate monitoring

## Security Considerations

1. **Cognito User Pool**: Configure password policies, MFA, and advanced security features
2. **API Gateway**: Enable CORS appropriately for your frontend domains
3. **DynamoDB**: Use IAM roles with least privilege principle
4. **Environment Variables**: Store sensitive values in AWS Systems Manager Parameter Store
5. **VPC**: Consider placing Lambdas in VPC for enhanced security

## Troubleshooting

### Common Issues

1. **CORS errors**: Ensure API Gateway CORS configuration matches your frontend origin
2. **Authentication errors**: Verify Cognito User Pool configuration and JWT token validity
3. **DynamoDB permissions**: Check IAM roles for proper DynamoDB access
4. **Lambda timeouts**: Adjust timeout settings for functions with heavy processing

### Logs

Check CloudWatch Logs for each Lambda function:
- `/aws/lambda/{stack-name}-{function-name}`
- API Gateway logs: `/aws/apigateway/{api-name}`

## Cleanup

To remove all deployed resources:

```bash
sam delete
```

**Warning**: This will delete the DynamoDB table and all data unless DeletionPolicy is set to Retain.

## Support

For issues or questions, refer to:
1. AWS SAM documentation
2. AWS Lambda documentation
3. Amazon Cognito documentation
4. DynamoDB documentation

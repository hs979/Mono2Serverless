# Shopping Cart Serverless Application

This is a serverless migration of a shopping cart monolith application to AWS Lambda, API Gateway, DynamoDB, and Cognito.

## Project Structure

```
output/
├── layers/
│   └── base-python-utils/
│       ├── python/
│       │   └── requirements.txt  # boto3 dependency
│       └── requirements.txt      # Layer dependency manifest
├── lambdas/
│   ├── products/
│   │   ├── get-all/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   └── get-by-id/
│   │       ├── handler.py
│   │       └── requirements.txt
│   ├── cart/
│   │   ├── get-items/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── add-item/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── update-item/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── migrate/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── checkout/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   └── get-total/
│   │       ├── handler.py
│   │       └── requirements.txt
│   └── cognito/
│       └── post-confirmation/
│           ├── handler.py
│           └── requirements.txt
└── README.md
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **SAM CLI** (Serverless Application Model) installed
4. **Python 3.11** (for local testing)
5. **Node.js** (if using AWS Amplify for frontend)

## Quick Start

### 1. Build the application

```bash
sam build
```

### 2. Deploy with guided configuration

```bash
sam deploy --guided
```

During guided deployment, you'll be prompted for:
- Stack name (e.g., `shopping-cart-serverless`)
- AWS Region
- Parameter overrides (environment, table name, etc.)
- Confirmation of IAM role creation

### 3. After deployment

Note the API Gateway endpoint URL from the output. It will look like:
```
https://xxxxxxxxxx.execute-api.region.amazonaws.com/Prod
```

## Deployment Steps

### 1. Clone and navigate to the project

```bash
git clone <repository-url>
cd output
```

### 2. Build the SAM application

```bash
sam build
```

### 3. Deploy to AWS

```bash
sam deploy --guided
```

### 4. Configure frontend (if applicable)

Update your frontend application to:
1. Use the deployed API Gateway endpoint
2. Integrate with Cognito User Pool for authentication
3. Include `X-Cart-Id` header for anonymous cart operations

## Environment Variables

Each Lambda function uses the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | `shopping-cart-monolith` |
| `AWS_REGION` | AWS region | `us-east-1` |

These are configured in the SAM template (to be created by sam_engineer).

## API Endpoints

### Product Management

| Method | Path | Description | Authentication |
|--------|------|-------------|----------------|
| GET | `/product` | Get all products | None |
| GET | `/product/{product_id}` | Get product details | None |

### Cart Operations

| Method | Path | Description | Authentication |
|--------|------|-------------|----------------|
| GET | `/cart` | Get cart contents | Optional (anonymous or authenticated) |
| POST | `/cart` | Add item to cart | Optional (anonymous or authenticated) |
| PUT | `/cart/{product_id}` | Update cart item quantity | Optional (anonymous or authenticated) |
| POST | `/cart/migrate` | Migrate anonymous cart to user account | Required (Cognito) |
| POST | `/cart/checkout` | Checkout and clear cart | Required (Cognito) |
| GET | `/cart/{product_id}/total` | Get total quantity across all carts | None |

### Authentication

Authentication is handled by **Amazon Cognito User Pool** with API Gateway Authorizer.
- User registration and login are managed by Cognito
- Frontend uses AWS Amplify Auth library
- API Gateway validates JWT tokens automatically

## Testing Instructions

### 1. Test without authentication (anonymous cart)

```bash
# Get all products
curl -X GET https://<api-id>.execute-api.<region>.amazonaws.com/Prod/product

# Get product by ID
curl -X GET https://<api-id>.execute-api.<region>.amazonaws.com/Prod/product/123

# Get cart (anonymous) - note the X-Cart-Id header in response
curl -X GET https://<api-id>.execute-api.<region>.amazonaws.com/Prod/cart \
  -H "Content-Type: application/json"

# Add item to cart (anonymous)
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/Prod/cart \
  -H "Content-Type: application/json" \
  -H "X-Cart-Id: <cart-id-from-previous-response>" \
  -d '{"productId": "123", "quantity": 2}'
```

### 2. Test with authentication

First, obtain a Cognito JWT token using AWS Amplify or Cognito API:

```javascript
// Frontend example using AWS Amplify
import { Auth } from 'aws-amplify';

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
```

Then use the token in API requests:

```bash
# Get cart (authenticated)
curl -X GET https://<api-id>.execute-api.<region>.amazonaws.com/Prod/cart \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <cognito-jwt-token>"

# Migrate anonymous cart to authenticated user
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/Prod/cart/migrate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <cognito-jwt-token>" \
  -H "X-Cart-Id: <anonymous-cart-id>"

# Checkout cart
curl -X POST https://<api-id>.execute-api.<region>.amazonaws.com/Prod/cart/checkout \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <cognito-jwt-token>"
```

## Frontend Integration

### Authentication Flow

1. **User Registration**: Use AWS Amplify `Auth.signUp()`
2. **User Login**: Use AWS Amplify `Auth.signIn()`
3. **Token Usage**: Include `Authorization: Bearer <token>` header in API requests

### Cart ID Management

For anonymous users:
- Generate a UUID for cart ID on first visit
- Store in browser localStorage
- Include as `X-Cart-Id` header in all cart requests
- When user logs in, migrate anonymous cart using `/cart/migrate` endpoint

### Example Frontend Code

```javascript
import { Auth } from 'aws-amplify';

// Get or generate cart ID for anonymous users
function getCartId() {
  let cartId = localStorage.getItem('cartId');
  if (!cartId) {
    cartId = uuidv4(); // Generate UUID
    localStorage.setItem('cartId', cartId);
  }
  return cartId;
}

// Make authenticated API request
async function makeRequest(method, path, data = null) {
  const url = `https://<api-id>.execute-api.<region>.amazonaws.com/Prod${path}`;
  const headers = {
    'Content-Type': 'application/json'
  };
  
  // Add authentication token if available
  try {
    const session = await Auth.currentSession();
    const token = session.getIdToken().getJwtToken();
    headers['Authorization'] = `Bearer ${token}`;
  } catch (error) {
    // User not authenticated, use cart ID for anonymous operations
    headers['X-Cart-Id'] = getCartId();
  }
  
  const config = {
    method,
    headers,
    body: data ? JSON.stringify(data) : undefined
  };
  
  const response = await fetch(url, config);
  return response.json();
}

// Example: Get cart items
const cartItems = await makeRequest('GET', '/cart');

// Example: Add to cart
await makeRequest('POST', '/cart', {
  productId: '123',
  quantity: 1
});
```

## Dropped Endpoints

The following monolith endpoints have been replaced by AWS managed services:

| Endpoint | Replacement | Reason |
|----------|-------------|--------|
| POST `/auth/register` | Cognito User Pool | User registration handled by Cognito |
| POST `/auth/login` | Cognito User Pool | User authentication handled by Cognito |
| `login_required` middleware | API Gateway Cognito Authorizer | Token validation at API Gateway layer |
| `verifyToken` decorator | API Gateway Cognito Authorizer | JWT validation handled by Cognito |
| `init_dynamodb.py` script | SAM Template CloudFormation | Table creation via infrastructure-as-code |
| Password hash storage | Cognito User Pool | Password management handled by Cognito |

## Architecture Notes

### Single-Table Design

The DynamoDB table uses a single-table design with composite keys:
- **Users**: `pk='USER#{cognito_sub}', sk='PROFILE'`
- **Cart Items**: `pk='user#{userId}'` or `pk='cart#{cartId}', sk='product#{productId}'`
- **Products**: `pk='PRODUCT#{productId}', sk='DETAIL'`
- **Product Aggregates**: `pk='PRODUCT#{productId}', sk='TOTAL'`

### Lambda Layers

- **base-python-utils**: Contains `boto3` for all Lambda functions
- Reduces deployment package size
- Ensures consistent AWS SDK version

### Cognito Integration

- User Pool with email/name attributes
- Post-confirmation trigger to create user profiles
- API Gateway Cognito Authorizer for token validation
- Frontend integration via AWS Amplify

### CORS Configuration

API Gateway is configured with CORS enabled:
- Allow-Origin: `*`
- Allow-Methods: `GET, POST, PUT, DELETE, OPTIONS`
- Allow-Headers: `Content-Type, Authorization, X-Amz-Date, X-Api-Key, X-Amz-Security-Token, X-Cart-Id`

## Troubleshooting

### Common Issues

1. **CORS errors**: Ensure frontend includes correct headers
2. **Authentication errors**: Verify Cognito token is valid and not expired
3. **DynamoDB errors**: Check IAM permissions and table name
4. **Cart ID issues**: Ensure `X-Cart-Id` header is included for anonymous operations

### Logs and Monitoring

- Check CloudWatch Logs for each Lambda function
- Use AWS X-Ray for tracing (enabled in SAM template)
- Monitor API Gateway metrics in CloudWatch

## Security Considerations

1. **Least Privilege IAM Roles**: Lambda functions have minimal permissions
2. **Environment Variables**: Sensitive configuration via parameters
3. **Cognito Security**: Password policies, MFA options configurable
4. **API Gateway Throttling**: Configure usage plans if needed
5. **DynamoDB Encryption**: Enable at-rest encryption

## Cost Optimization

1. **Lambda Configuration**: Appropriate memory and timeout settings
2. **DynamoDB Capacity**: Auto-scaling or on-demand capacity mode
3. **API Gateway Caching**: Enable caching for frequently accessed endpoints
4. **CloudWatch Logs Retention**: Set appropriate retention periods

## Support

For issues with:
- **Application code**: Refer to this README and code comments
- **Infrastructure**: SAM template (to be created by sam_engineer)
- **AWS services**: Consult AWS documentation

## Next Steps

The sam_engineer will create the SAM template (`template.yaml`) with:
- Lambda function definitions
- API Gateway configuration
- DynamoDB table schema
- Cognito User Pool setup
- IAM roles and policies
- Environment variables

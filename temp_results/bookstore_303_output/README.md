# Bookstore Serverless Application

## Overview

This is a serverless migration of a Bookstore application to AWS Lambda and API Gateway. The application provides RESTful APIs for managing books, shopping cart, orders, bestsellers, recommendations, and search functionality.

## Project Structure

```
output/
├── lambdas/
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
│   │   ├── cart-get-item/
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
│   ├── bestsellers/
│   │   └── bestsellers-get/
│   │       ├── handler.js
│   │       └── package.json
│   ├── recommendations/
│   │   ├── recommendations-get-all/
│   │   │   ├── handler.js
│   │   │   └── package.json
│   │   └── recommendations-get-by-book/
│   │       ├── handler.js
│   │       └── package.json
│   └── search/
│       └── search-books/
│           ├── handler.js
│           └── package.json
└── README.md
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **AWS SAM CLI** installed
4. **Node.js 18.x** (for local testing)
5. **Docker** (for SAM local testing)

## Quick Start

### 1. Build the application

```bash
sam build
```

### 2. Deploy the application

```bash
sam deploy --guided
```

Follow the interactive prompts to:
- Set stack name
- Select AWS region
- Confirm IAM role creation
- Set parameter overrides if needed

### 3. Get API Gateway endpoint

After deployment, SAM will output the API Gateway endpoint URL. Use this as the base URL for all API calls.

## Environment Variables

Each Lambda function requires specific environment variables:

### Books Functions
- `BOOKS_TABLE`: DynamoDB table name for books

### Cart Functions
- `CART_TABLE`: DynamoDB table name for cart items

### Orders Functions
- `ORDERS_TABLE`: DynamoDB table name for orders
- `CART_TABLE`: DynamoDB table name for cart items
- `BOOKS_TABLE`: DynamoDB table name for books (for validation)
- `REDIS_ENDPOINT`: Redis endpoint for bestseller updates (host:port)

### Bestsellers Function
- `REDIS_ENDPOINT`: Redis endpoint (host:port)

### Recommendations Functions
- `NEPTUNE_ENDPOINT`: Neptune graph database endpoint

### Search Function
- `ELASTICSEARCH_ENDPOINT`: Elasticsearch endpoint
- `BOOKS_TABLE`: DynamoDB table name for books (fallback)

## API Endpoints

All endpoints require Cognito authentication unless noted otherwise.

### Books
- `GET /books` - List all books or filter by category (query param: `?category=programming`)
- `GET /books/{id}` - Get book details by ID

### Cart
- `GET /cart` - Get all items in user's cart
- `GET /cart/{bookId}` - Get specific cart item
- `POST /cart` - Add item to cart
  ```json
  {
    "bookId": "book-001",
    "quantity": 2,
    "price": 99.00
  }
  ```
- `PUT /cart` - Update cart item quantity
  ```json
  {
    "bookId": "book-001",
    "quantity": 3
  }
  ```
- `DELETE /cart` - Remove item from cart
  ```json
  {
    "bookId": "book-001"
  }
  ```

### Orders
- `GET /orders` - Get all user's orders
- `POST /orders` - Create new order (checkout)
  ```json
  {
    "books": [
      {
        "bookId": "book-001",
        "price": 99.00,
        "quantity": 2
      }
    ]
  }
  ```

### Bestsellers
- `GET /bestsellers` - Get top 20 bestsellers (public endpoint)

### Recommendations
- `GET /recommendations` - Get personalized book recommendations
- `GET /recommendations/{bookId}` - Get friends who purchased a specific book

### Search
- `GET /search?q=javascript` - Search books by keyword (public endpoint)

## Authentication

Authentication is handled by Amazon Cognito. The API Gateway uses a Cognito Authorizer to validate JWT tokens.

### Frontend Integration

1. **User Registration/Login**: Use AWS Amplify or Cognito SDK directly
2. **API Calls**: Include the JWT token in the Authorization header:
   ```
   Authorization: Bearer <id_token>
   ```

### Dropped Authentication Endpoints

The following endpoints from the monolith have been replaced by Cognito:
- `POST /register` - Use Cognito User Pool sign-up
- `POST /login` - Use Cognito User Pool authentication
- `POST /refresh` - Use Cognito token refresh
- `GET /me` - User info available in JWT token claims

## Testing

### Local Testing with SAM

```bash
# Start local API Gateway
sam local start-api

# Test endpoints
curl -X GET "http://localhost:3000/books"
```

### Testing with Authentication

For endpoints requiring authentication, you need to:
1. Get a valid JWT token from Cognito
2. Include it in the Authorization header

Example with curl:
```bash
curl -X GET "https://<api-gateway-url>/cart" \
  -H "Authorization: Bearer <id_token>" \
  -H "Content-Type: application/json"
```

### Sample Test Data

You can use the following sample book IDs for testing:
- `book-001`: JavaScript Advanced Programming
- `book-002`: Node.js Development Guide
- `book-003`: Computer Systems: A Programmer's Perspective
- `book-004`: Clean Code
- `book-005`: Design Patterns

## External Services Configuration

The application integrates with several external services:

### 1. DynamoDB Tables
Three tables are required:
- Books table with `id` as partition key and `category-index` GSI
- Cart table with composite key (`customerId`, `bookId`)
- Orders table with composite key (`customerId`, `orderId`)

### 2. Redis
Required for bestseller functionality. Configure Redis endpoint as `host:port`.

### 3. Amazon Neptune
Required for recommendations. Configure Neptune endpoint.

### 4. Elasticsearch
Required for search functionality. Configure Elasticsearch endpoint.

## Monitoring and Logging

- **CloudWatch Logs**: Each Lambda function logs to CloudWatch
- **CloudWatch Metrics**: Monitor invocation counts, durations, errors
- **X-Ray Tracing**: Enable for distributed tracing

## Troubleshooting

### Common Issues

1. **Missing IAM Permissions**: Ensure Lambda functions have appropriate DynamoDB permissions
2. **CORS Errors**: API Gateway is configured with CORS. Check frontend origin
3. **Authentication Errors**: Verify Cognito User Pool configuration and token validity
4. **External Service Connectivity**: Check VPC configuration for Redis, Neptune, Elasticsearch

### Logs

Check CloudWatch logs for each Lambda function:
```bash
aws logs tail /aws/lambda/<function-name> --follow
```

## Cleanup

To delete all resources created by this application:

```bash
sam delete
```

## Security Notes

1. **Environment Variables**: Sensitive values should use AWS Systems Manager Parameter Store or Secrets Manager
2. **IAM Roles**: Follow principle of least privilege
3. **API Gateway**: Use custom domain with HTTPS
4. **Cognito**: Configure appropriate password policies and MFA

## Support

For issues or questions, refer to:
1. AWS SAM documentation
2. AWS Lambda documentation
3. API Gateway documentation
4. DynamoDB documentation

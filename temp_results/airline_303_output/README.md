# Airline Booking Serverless Application

This is a serverless implementation of an airline booking system, migrated from a monolithic Flask application to AWS Lambda functions with API Gateway and DynamoDB.

## Architecture Overview

- **API Gateway**: REST API with Cognito Authorizer for authentication
- **Lambda Functions**: 16 Python functions implementing business logic
- **DynamoDB Tables**: Flight, Booking, and Loyalty tables with appropriate schemas
- **Cognito User Pool**: Managed authentication and authorization
- **Shared Layer**: Common utilities and dependencies

## Project Structure

```
output/
├── layers/
│   └── shared/
│       ├── python/
│       │   └── shared_utils.py
│       └── requirements.txt
├── lambdas/
│   ├── flights/
│   │   ├── flights-search/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── flights-get/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── flights-reserve-seat/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   └── flights-release-seat/
│   │       ├── handler.py
│   │       └── requirements.txt
│   ├── bookings/
│   │   ├── bookings-create/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── bookings-get/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── bookings-confirm/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── bookings-cancel/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── bookings-reserve/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   └── bookings-notify/
│   │       ├── handler.py
│   │       └── requirements.txt
│   ├── customers/
│   │   └── customers-bookings-get/
│   │       ├── handler.py
│   │       └── requirements.txt
│   ├── payments/
│   │   ├── payments-collect/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   ├── payments-refund/
│   │   │   ├── handler.py
│   │   │   └── requirements.txt
│   │   └── payments-get/
│   │       ├── handler.py
│   │       └── requirements.txt
│   └── loyalty/
│       ├── loyalty-get/
│       │   ├── handler.py
│       │   └── requirements.txt
│       └── loyalty-add-points/
│           ├── handler.py
│           └── requirements.txt
└── README.md
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **SAM CLI** installed (for deployment)
4. **Python 3.11** (matching Lambda runtime)
5. **Node.js** (for SAM CLI, if needed)

## Deployment Steps

### 1. Build the Application

```bash
cd output
sam build
```

### 2. Deploy with SAM

```bash
sam deploy --guided
```

During guided deployment, you'll be prompted for:
- Stack name (e.g., airline-booking)
- AWS Region
- Parameter overrides (environment variables)
- Confirmation of IAM role creation

### 3. Environment Variables Configuration

Key environment variables needed:

- **STAGE**: Environment stage (dev, staging, prod)
- **STRIPE_SECRET_KEY**: Stripe API secret key for payment processing (optional, simulation mode available)
- **AWS_REGION**: AWS region for DynamoDB tables

### 4. Post-Deployment Setup

After deployment, note the following outputs from CloudFormation:

1. **API Gateway URL**: Base URL for all endpoints
2. **Cognito User Pool ID**: For user authentication
3. **Cognito App Client ID**: For frontend integration
4. **DynamoDB Table Names**: Flight, Booking, Loyalty tables

## API Endpoints

### Flight Management

- `GET /flights/search` - Search flights by departure/arrival codes and date
- `GET /flights/{flight_id}` - Get flight details
- `POST /flights/{flight_id}/reserve` - Reserve a seat on a flight
- `POST /flights/{flight_id}/release` - Release a reserved seat

### Booking Management

- `POST /bookings` - Create a new booking (requires authentication)
- `GET /bookings/{booking_id}` - Get booking details (owner or admin only)
- `POST /bookings/{booking_id}/confirm` - Confirm a booking (owner or admin only)
- `POST /bookings/{booking_id}/cancel` - Cancel a booking (owner or admin only)
- `GET /customers/{customer_id}/bookings` - Get all bookings for a customer (owner or admin only)

### Payment Processing

- `POST /payments/collect` - Collect payment for a booking
- `POST /payments/refund` - Refund a payment
- `GET /payments/{charge_id}` - Get payment details

### Loyalty Program

- `GET /loyalty/{customer_id}` - Get customer loyalty points and tier (owner or admin only)
- `POST /loyalty/{customer_id}/points` - Add loyalty points (admin only)

## Authentication

All endpoints except the following require Cognito authentication:
- `GET /flights/search`
- `GET /flights/{flight_id}`
- `POST /payments/collect`
- `POST /payments/refund`
- `GET /payments/{charge_id}`

### Cognito Integration

1. User registration and login are handled by Cognito User Pool
2. Frontend should integrate with Cognito for authentication
3. API Gateway validates JWT tokens automatically
4. User ID is extracted from token claims (`sub` field)

## Testing

### Sample cURL Commands

#### Search Flights (No Authentication)
```bash
curl -X GET "https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/flights/search?departureCode=LAX&arrivalCode=SFO&departureDate=2025-11-10"
```

#### Create Booking (With Authentication)
```bash
curl -X POST "https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/bookings" \
  -H "Authorization: Bearer {cognito-id-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "outboundFlightId": "FL001",
    "chargeId": "tok_visa"
  }'
```

#### Get Booking Details
```bash
curl -X GET "https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/bookings/{booking_id}" \
  -H "Authorization: Bearer {cognito-id-token}"
```

## Error Handling

All endpoints return standardized error responses:

- `400 Bad Request`: Invalid input or business logic error
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Unexpected server error

## Monitoring and Logging

- **CloudWatch Logs**: Each Lambda function logs to CloudWatch
- **CloudWatch Metrics**: API Gateway and Lambda metrics available
- **X-Ray Tracing**: Enable for distributed tracing

## Security Considerations

1. **IAM Roles**: Least privilege principles applied to Lambda functions
2. **Environment Variables**: Sensitive data stored in environment variables
3. **API Gateway Throttling**: Configure rate limiting for DDoS protection
4. **Cognito Policies**: Password policies and MFA configured
5. **DynamoDB Encryption**: Enable at-rest encryption for sensitive data

## Cost Optimization

1. **Lambda Memory**: Adjust memory settings based on function requirements
2. **DynamoDB Capacity**: Use on-demand or provisioned capacity appropriately
3. **API Gateway Caching**: Enable caching for frequently accessed endpoints
4. **CloudWatch Retention**: Set appropriate log retention periods

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: Ensure shared layer is properly attached to Lambda functions
2. **Permission Errors**: Check IAM roles and policies
3. **CORS Errors**: Verify CORS headers in responses
4. **Cold Starts**: Consider provisioned concurrency for critical functions

### Debugging

1. Check CloudWatch Logs for each Lambda function
2. Enable X-Ray tracing for request flow analysis
3. Test endpoints with Postman or cURL

## Frontend Integration

### Authentication Flow

1. User signs up/signs in via Cognito Hosted UI or custom UI
2. Receive JWT tokens (id_token, access_token, refresh_token)
3. Include id_token in Authorization header for API calls
4. Handle token refresh when tokens expire

### Sample Frontend Code (JavaScript)

```javascript
// Using Amazon Cognito Identity SDK
import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';

const poolData = {
  UserPoolId: 'us-east-1_XXXXXXXXX', // From CloudFormation outputs
  ClientId: 'XXXXXXXXXXXXXXXXXXXXXX' // From CloudFormation outputs
};

const userPool = new CognitoUserPool(poolData);

// Login
const authenticationDetails = new AuthenticationDetails({
  Username: 'user@example.com',
  Password: 'password123'
});

const cognitoUser = new CognitoUser({
  Username: 'user@example.com',
  Pool: userPool
});

cognitoUser.authenticateUser(authenticationDetails, {
  onSuccess: (result) => {
    const idToken = result.getIdToken().getJwtToken();
    // Use idToken in API requests
    fetch('/bookings', {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });
  },
  onFailure: (err) => {
    console.error('Authentication failed:', err);
  }
});
```

## Support

For issues or questions:

1. Check CloudFormation stack events
2. Review Lambda function logs in CloudWatch
3. Consult AWS documentation for specific services
4. Contact your AWS solutions architect

---

**Note**: This application is ready for deployment. The SAM engineer will create the necessary infrastructure templates (template.yaml) based on this code structure.
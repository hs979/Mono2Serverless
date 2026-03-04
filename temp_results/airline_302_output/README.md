# Airline Booking Serverless Application

## Overview

This is a serverless migration of the Airline Booking monolithic application to AWS Lambda. The application provides flight search, booking, payment processing, loyalty management, and user authentication functionality.

## Architecture

- **API Gateway**: REST API endpoints with Cognito authorizer
- **Lambda Functions**: 18 Python 3.11 functions for business logic
- **DynamoDB**: 4 tables (Flight, Booking, Loyalty, UserProfiles)
- **Cognito**: User authentication and post-confirmation trigger
- **S3**: File storage (if needed)
- **Lambda Layers**: Shared utilities and dependencies

## Project Structure

```
output/
├── layers/
│   └── base-python-utils/
│       ├── python/
│       │   └── internal_client.py
│       └── requirements.txt
├── lambdas/
│   ├── flights-search/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── flights-get/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── flights-reserve-seat/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── flights-release-seat/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── bookings-create/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── bookings-get/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── bookings-confirm/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── bookings-cancel/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── bookings-get-by-customer/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── payments-collect/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── payments-refund/
│   │   ├── handler.py
│   │   └── requirements.txt
│   ├── payments-get/
│   │   ├── handler.py
│   │   └── requirements.txt
│   └── loyalty-get/
│       ├── handler.py
│       └── requirements.txt
└── README.md
```

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **SAM CLI** installed (`pip install aws-sam-cli`)
4. **Python 3.11** (for local testing)
5. **Node.js** (optional, for SAM CLI)

## Quick Start

### 1. Build the application

```bash
sam build
```

### 2. Deploy with guided configuration

```bash
sam deploy --guided
```

During deployment, you'll be prompted for:
- Stack name
- AWS Region
- Parameter overrides
- Confirmation of IAM role creation

### 3. Post-deployment setup

After deployment, you need to:

1. **Configure Cognito User Pool**: Update the frontend with the User Pool ID and Client ID
2. **Set up Stripe** (optional): Add `STRIPE_SECRET_KEY` to Lambda environment variables for real payments
3. **Initialize DynamoDB tables**: Run the table creation scripts

## Environment Variables

Each Lambda function has specific environment variables. Key variables include:

### Common Variables
- `FLIGHT_TABLE`: DynamoDB table for flights
- `BOOKING_TABLE`: DynamoDB table for bookings
- `LOYALTY_TABLE`: DynamoDB table for loyalty points
- `USER_PROFILES_TABLE`: DynamoDB table for user profiles

### Function-Specific Variables
- `NOTIFY_BOOKING_FUNCTION_NAME`: Lambda function name for notifications (used by bookings-create, bookings-confirm, bookings-cancel)
- `PROCESS_BOOKING_LOYALTY_FUNCTION_NAME`: Lambda function name for loyalty processing (used by bookings-create)
- `STRIPE_SECRET_KEY`: Stripe API key for payment processing (used by payments-* functions)

## API Endpoints

### Public Endpoints (No Authentication)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/flights/search` | Search flights by departure/arrival codes and date |
| GET | `/flights/{flight_id}` | Get flight details |
| POST | `/flights/{flight_id}/reserve` | Reserve a flight seat |
| POST | `/flights/{flight_id}/release` | Release a flight seat |
| POST | `/payments/collect` | Collect payment |
| POST | `/payments/refund` | Refund payment |
| GET | `/payments/{charge_id}` | Get payment details |
| GET | `/api` | API information endpoint |

### Protected Endpoints (Cognito Authentication Required)

| Method | Path | Description | Authorization |
|--------|------|-------------|---------------|
| POST | `/bookings` | Create a new booking | Any authenticated user |
| GET | `/bookings/{booking_id}` | Get booking details | Booking owner or admin |
| POST | `/bookings/{booking_id}/confirm` | Confirm booking | Booking owner or admin |
| POST | `/bookings/{booking_id}/cancel` | Cancel booking | Booking owner or admin |
| GET | `/customers/{customer_id}/bookings` | Get customer bookings | Customer or admin |
| GET | `/loyalty/{customer_id}` | Get loyalty information | Customer or admin |
| POST | `/loyalty/{customer_id}/points` | Add loyalty points | Admin only |

### Internal Functions (Lambda-to-Lambda)

1. **notify-booking**: Sends booking notifications (async)
2. **process-booking-loyalty**: Processes loyalty points from bookings (async)
3. **cognito-post-confirmation**: Cognito trigger for user profile creation

### Dropped Endpoints

The following auth endpoints from the monolith are handled by Cognito:
- `POST /auth/register` → Cognito Sign Up
- `POST /auth/login` → Cognito Sign In
- `GET /auth/me` → Cognito User Info
- `GET /auth/users` → Cognito List Users (Admin)

Frontend integration: Use AWS Amplify or Cognito SDK for authentication.

## Testing

### Sample API Requests

#### Search Flights
```bash
curl -X GET "https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/flights/search?departureCode=LAX&arrivalCode=SFO&departureDate=2025-11-10"
```

#### Create Booking (with Cognito token)
```bash
curl -X POST "https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/bookings" \
  -H "Authorization: Bearer {cognito-id-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "outboundFlightId": "FL001",
    "chargeId": "tok_visa"
  }'
```

#### Get Booking
```bash
curl -X GET "https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/bookings/{booking_id}" \
  -H "Authorization: Bearer {cognito-id-token}"
```

## Frontend Integration

### Authentication Flow

1. **User Registration**: Use Cognito's `signUp` API
2. **User Login**: Use Cognito's `signIn` API
3. **Token Management**: Store tokens securely (HTTP-only cookies recommended)
4. **API Calls**: Include `Authorization: Bearer {id-token}` header

### Sample Frontend Code (JavaScript)

```javascript
// Using AWS Amplify
import { Auth } from 'aws-amplify';

// Sign up
await Auth.signUp({
  username: 'user@example.com',
  password: 'Password123!',
  attributes: {
    email: 'user@example.com'
  }
});

// Sign in
const user = await Auth.signIn('user@example.com', 'Password123!');
const token = user.signInUserSession.idToken.jwtToken;

// API call with token
const response = await fetch('https://{api-id}.execute-api.{region}.amazonaws.com/{stage}/bookings', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    outboundFlightId: 'FL001',
    chargeId: 'tok_visa'
  })
});
```

## Shared Layer

The `base-python-utils` layer provides:

1. **`invoke_lambda`**: Utility for Lambda-to-Lambda invocation
2. **DynamoDB helpers**: Type conversion utilities
3. **Response helpers**: Standardized API Gateway responses
4. **Error handling**: Consistent error response formatting
5. **Authentication helpers**: User ID extraction from Cognito claims

## Security Considerations

1. **Cognito Authorizer**: All protected endpoints use Cognito for authentication
2. **IAM Roles**: Least privilege permissions for Lambda functions
3. **Environment Variables**: Sensitive data stored in Lambda environment (not code)
4. **API Gateway**: CORS configured, HTTPS enforced
5. **DynamoDB**: Fine-grained IAM policies for table access

## Monitoring and Logging

- **CloudWatch Logs**: All Lambda functions log to CloudWatch
- **CloudWatch Metrics**: API Gateway and Lambda metrics
- **X-Ray Tracing**: Enable for distributed tracing
- **CloudWatch Alarms**: Set up for error rates and latency

## Troubleshooting

### Common Issues

1. **CORS errors**: Ensure frontend domain is in CORS configuration
2. **Authentication errors**: Verify Cognito token is valid and not expired
3. **DynamoDB errors**: Check IAM permissions and table names
4. **Lambda timeouts**: Increase timeout for complex operations (bookings-create)

### Log Analysis

```bash
# View Lambda logs
sam logs -n FlightsSearchFunction --stack-name airline-booking-stack

# Tail logs in real-time
sam logs -n FlightsSearchFunction --stack-name airline-booking-stack --tail
```

## Development

### Adding New Functions

1. Create handler in `lambdas/{function-name}/handler.py`
2. Add dependencies to `requirements.txt` if not in layer
3. Update SAM template (to be done by sam_engineer)
4. Deploy with `sam deploy`

### Local Testing

```bash
# Test Lambda locally
sam local invoke FlightsSearchFunction --event events/search-event.json

# Start local API Gateway
sam local start-api
```

## Deployment Notes

- **Staging**: Use different stack names for dev/staging/prod
- **Rollbacks**: SAM supports rollback on failure
- **Updates**: Deploy changes with `sam deploy`
- **Deletion**: Remove stack with `sam delete`

## Support

For issues with:
- **Application code**: Review CloudWatch logs
- **Infrastructure**: Check CloudFormation stack events
- **Authentication**: Verify Cognito configuration
- **Database**: Check DynamoDB table status and IAM permissions

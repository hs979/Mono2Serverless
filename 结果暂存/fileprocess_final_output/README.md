# File Processing Serverless Application

A serverless application that converts markdown files to HTML and performs sentiment analysis using AWS Lambda, API Gateway, DynamoDB, and S3.

## Architecture Overview

This application follows a simple REST API pattern with three main Lambda functions:

1. **ConvertToHTML Function** - Converts markdown content to HTML and stores it in S3
2. **AnalyzeSentiment Function** - Analyzes text sentiment using AWS Comprehend
3. **SaveSentiment Function** - Saves/retrieves sentiment analysis results from DynamoDB

### Architecture Diagram

```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   API Gateway   │────▶│  ConvertToHTML      │────▶│  S3 Output       │
│   (REST API)    │     │  Lambda Function    │     │  Bucket          │
└─────────────────┘     └─────────────────────┘     └──────────────────┘
        │                         │
        │                         │
        ▼                         ▼
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Client        │────▶│  AnalyzeSentiment   │────▶│  DynamoDB        │
│   Applications  │     │  Lambda Function    │     │  Table           │
└─────────────────┘     └─────────────────────┘     └──────────────────┘
        │                         │
        │                         │
        ▼                         ▼
┌─────────────────┐     ┌─────────────────────┐
│   S3 Input      │     │  SaveSentiment      │
│   Bucket        │     │  Lambda Function    │
└─────────────────┘     └─────────────────────┘
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- SAM CLI installed (`pip install aws-sam-cli`)
- Python 3.9
- Docker (for local testing)

## Project Structure

```
output/
├── README.md                          # This file
├── template.yaml                      # SAM template
├── lambdas/
│   ├── FileProcessing-ConvertToHTML/
│   │   ├── handler.py                 # Convert markdown to HTML
│   │   └── requirements.txt           # Python dependencies
│   ├── FileProcessing-AnalyzeSentiment/
│   │   ├── handler.py                 # Analyze text sentiment
│   │   └── requirements.txt           # Python dependencies
│   └── FileProcessing-SaveSentiment/
│       ├── handler.py                 # Save/retrieve sentiment results
│       └── requirements.txt           # Python dependencies
├── layers/
│   └── FileProcessing-CommonLayer/
│       └── python/
│           └── requirements.txt       # Shared dependencies
└── samconfig.toml                     # SAM deployment configuration
```

## Quick Start

### 1. Build the application

```bash
cd output
sam build
```

### 2. Deploy to AWS

```bash
sam deploy --guided
```

During guided deployment, you'll be prompted for:
- Stack name (e.g., `file-processing-dev`)
- AWS Region
- Environment (dev, staging, prod)
- Email for CloudWatch alerts

### 3. Test the API

After deployment, SAM will output the API Gateway URL. Use it to test:

```bash
# Convert markdown to HTML
curl -X POST \
  https://<api-id>.execute-api.<region>.amazonaws.com/dev/files \
  -H 'Content-Type: text/markdown' \
  -d '# Hello World

This is a **markdown** file.' \
  -G --data-urlencode 'filename=test.md'

# Analyze sentiment
curl -X POST \
  https://<api-id>.execute-api.<region>.amazonaws.com/dev/files/test.txt/sentiment \
  -H 'Content-Type: text/plain' \
  -d 'I absolutely love this product! It has changed my life for the better.'

# Retrieve sentiment results
curl -X GET \
  https://<api-id>.execute-api.<region>.amazonaws.com/dev/sentiment/test.txt
```

## API Endpoints

### POST /files
Converts markdown content to HTML and stores it in S3.

**Request:**
```
Content-Type: text/markdown
Body: Markdown content
Query Parameters: filename (optional)
```

**Response:**
```json
{
  "html_file": "s3://bucket/html/20240101_120000_test.html",
  "filename": "test.html",
  "s3_key": "html/20240101_120000_test.html",
  "bucket": "dev-file-processing-output-bucket",
  "message": "Conversion successful",
  "timestamp": "20240101_120000"
}
```

### POST /files/{filename}/sentiment
Analyzes sentiment of text content.

**Request:**
```
Content-Type: text/plain
Body: Text content to analyze
```

**Response:**
```json
{
  "sentiment": "POSITIVE",
  "sentiment_scores": {
    "Positive": 0.95,
    "Negative": 0.02,
    "Neutral": 0.03,
    "Mixed": 0.00
  },
  "filename": "test.txt",
  "message": "Sentiment analysis successful"
}
```

### GET /sentiment/{filename}
Retrieves sentiment analysis results from DynamoDB.

**Response:**
```json
{
  "filename": "test.txt",
  "last_modified": "2023-01-01T00:00:00",
  "overall_sentiment": "POSITIVE",
  "scores": {
    "positive": "0.95",
    "negative": "0.02",
    "neutral": "0.03",
    "mixed": "0.00"
  },
  "message": "Sentiment results retrieved successfully"
}
```

## Environment Variables

### Lambda Functions

| Function | Environment Variables | Description |
|----------|---------------------|-------------|
| ConvertToHTML | `OUTPUT_BUCKET` | S3 bucket for HTML output |
| SaveSentiment | `SENTIMENT_TABLE` | DynamoDB table name |
| All Functions | `AWS_REGION` | AWS region (auto-set) |
| All Functions | `LOG_LEVEL` | Logging level (INFO) |

### Deployment Parameters

| Parameter | Default | Allowed Values | Description |
|-----------|---------|----------------|-------------|
| Environment | dev | dev, staging, prod | Deployment environment |

## Local Development

### 1. Test Lambda functions locally

```bash
# Build and test ConvertToHTML function
sam local invoke ConvertToHTMLFunction -e events/convert-event.json

# Start local API Gateway
sam local start-api
```

### 2. Create test events

Create `events/convert-event.json`:
```json
{
  "body": "# Test Markdown\n\nThis is a test.",
  "headers": {
    "content-type": "text/markdown"
  },
  "queryStringParameters": {
    "filename": "test.md"
  },
  "isBase64Encoded": false
}
```

## Monitoring and Logging

### CloudWatch Logs
Each Lambda function has its own log group:
- `/aws/lambda/{env}-FileProcessing-ConvertToHTML`
- `/aws/lambda/{env}-FileProcessing-AnalyzeSentiment`
- `/aws/lambda/{env}-FileProcessing-SaveSentiment`
- `/aws/apigateway/{env}-FileProcessing-API`

### CloudWatch Alarms
Two alarms are configured:
1. **High Error Rate** - Triggers when error count exceeds 5 in 10 minutes
2. **High Latency** - Triggers when average duration exceeds 10 seconds

Alarms send notifications to the SNS topic `{env}-FileProcessing-Alerts`.

### X-Ray Tracing
X-Ray tracing is enabled with 5% sampling rate for performance monitoring.

## Security

- **S3 Buckets**: Block all public access, enabled versioning
- **DynamoDB**: Server-side encryption enabled, point-in-time recovery
- **API Gateway**: CORS configured, request throttling enabled
- **Lambda**: Execution roles follow principle of least privilege

## Cost Optimization

- **DynamoDB**: PAY_PER_REQUEST billing mode
- **S3**: Lifecycle policies (30 days for input, 90 days for output)
- **Lambda**: 256MB memory, 30-second timeout
- **API Gateway**: Throttling limits (1000 requests/second)

## Troubleshooting

### Common Issues

1. **DynamoDB Table Not Found**
   - Ensure the table is created (CloudFormation creates it)
   - Check `SENTIMENT_TABLE` environment variable

2. **S3 Access Denied**
   - Verify Lambda execution role has S3 write permissions
   - Check bucket names and policies

3. **AWS Comprehend Access Denied**
   - Ensure Lambda execution role has `comprehend:DetectSentiment` permission

4. **API Gateway CORS Errors**
   - Verify CORS headers in Lambda responses
   - Check API Gateway CORS configuration

### Log Analysis

Check CloudWatch Logs for:
- Lambda function errors and stack traces
- API Gateway access logs
- X-Ray traces for performance issues

## Deployment Configuration

### SAM Configuration (samconfig.toml)

Create `samconfig.toml` for automated deployments:

```toml
version = 0.1
[default]
[default.deploy]
[default.deploy.parameters]
stack_name = "file-processing-dev"
s3_bucket = "aws-sam-cli-managed-default-samclisourcebucket-xxxxxxxxxxxx"
s3_prefix = "file-processing"
region = "us-east-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = "Environment=dev"
```

## License

MIT License

## Support

For issues and feature requests, please create an issue in the repository.

# File Processing Serverless Application

This is a serverless application for processing files: converting markdown to HTML, analyzing sentiment, and storing results in DynamoDB.

## Architecture

- **AWS Lambda Functions**:
  - `ConvertToHtmlLambda`: Converts markdown content to HTML
  - `AnalyzeSentimentLambda`: Analyzes sentiment of text using Amazon Comprehend
  - `SaveSentimentLambda`: Saves sentiment analysis results to DynamoDB
- **AWS Step Functions**: Orchestrates the processing workflow
- **Amazon API Gateway**: REST API endpoints for direct invocation
- **Amazon DynamoDB**: Stores sentiment results with a Global Secondary Index
- **AWS Lambda Layer**: Shared dependencies (boto3, markdown)
- **Amazon S3**: Source bucket for file uploads (triggers Step Functions)

## Deployment

This is a **backend-only** deployment. No frontend components are included.

### Prerequisites

- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.12

### Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd output
   ```

2. **Build the application**
   ```bash
   sam build
   ```

3. **Deploy to AWS**
   ```bash
   sam deploy --guided
   ```
   During guided deployment, you'll be prompted for:
   - Stack name
   - AWS Region
   - Environment (dev or prod)
   - Confirm changes before deploy
   - Allow SAM CLI IAM role creation

4. **After deployment**, note the outputs:
   - `ApiEndpoint`: API Gateway URL
   - `SentimentTableName`: DynamoDB table name
   - `SourceBucketName`: S3 bucket for uploading files
   - `FileProcessingWorkflowArn`: Step Functions state machine ARN

## Usage

### API Endpoints

- `POST /process` - Convert markdown to HTML
  ```json
  {
    "content": "# Hello World\nThis is **markdown**.",
    "filename": "example.md"
  }
  ```

- `POST /analyze` - Analyze sentiment of text
  ```json
  {
    "content": "I love this product! It's amazing.",
    "filename": "review.txt"
  }
  ```

### File Processing via S3

1. Upload a markdown file (.md) to the S3 bucket created during deployment.
2. The S3 event triggers the Step Functions workflow.
3. The workflow:
   - Converts markdown to HTML
   - Analyzes sentiment of the HTML content
   - Saves results to DynamoDB

### Querying Results

Use AWS CLI or SDK to query the DynamoDB table:
```bash
aws dynamodb scan --table-name <table-name>
```

## Local Testing

### Test Lambda Functions

```bash
# ConvertToHtmlLambda
sam local invoke ConvertToHtmlLambda -e events/convert-event.json

# AnalyzeSentimentLambda
sam local invoke AnalyzeSentimentLambda -e events/analyze-event.json

# SaveSentimentLambda
sam local invoke SaveSentimentLambda -e events/save-event.json
```

Create sample event files in `events/` directory.

### Test API Gateway Locally

```bash
sam local start-api
```

Then send requests to `http://localhost:3000/process` and `http://localhost:3000/analyze`.

## Cleanup

To delete the deployed stack:
```bash
sam delete
```

## Security

- IAM roles are automatically created with least-privilege permissions.
- Environment variables are used for configuration.
- Consider enabling encryption at rest for DynamoDB and S3.

## Monitoring

- CloudWatch Logs for each Lambda function
- Step Functions execution history
- API Gateway access logs
- DynamoDB metrics

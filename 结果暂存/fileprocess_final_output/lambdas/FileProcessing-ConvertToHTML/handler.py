import os
import json
import boto3
import markdown
import tempfile
from datetime import datetime
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for converting markdown files to HTML format
    
    Expected event format (API Gateway REST API):
    {
        "body": "base64 encoded markdown content",
        "headers": {
            "content-type": "text/markdown"
        },
        "queryStringParameters": {
            "filename": "example.md"
        }
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "html_file": "s3://bucket/path/to/file.html",
            "filename": "example.html",
            "message": "Conversion successful"
        }
    }
    """
    try:
        logger.info("Starting markdown to HTML conversion")
        
        # Get environment variables
        output_bucket = os.environ.get('OUTPUT_BUCKET')
        if not output_bucket:
            raise ValueError("OUTPUT_BUCKET environment variable not set")
        
        # Parse the event
        if 'body' not in event:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No file content provided'})
            }
        
        # Get filename from query parameters or generate one
        filename = 'converted.html'
        if event.get('queryStringParameters') and event['queryStringParameters'].get('filename'):
            input_filename = event['queryStringParameters']['filename']
            if input_filename.endswith('.md') or input_filename.endswith('.markdown'):
                filename = os.path.splitext(input_filename)[0] + '.html'
            else:
                filename = input_filename + '.html'
        
        # Decode base64 if needed
        body = event['body']
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')
        
        # Convert markdown to HTML
        html_content = markdown.markdown(body)
        
        # Upload to S3
        s3_client = boto3.client('s3')
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"html/{timestamp}_{filename}"
        
        s3_client.put_object(
            Bucket=output_bucket,
            Key=s3_key,
            Body=html_content.encode('utf-8'),
            ContentType='text/html',
            Metadata={
                'original-content-type': event.get('headers', {}).get('content-type', 'unknown'),
                'conversion-timestamp': timestamp
            }
        )
        
        s3_url = f"s3://{output_bucket}/{s3_key}"
        
        logger.info(f"Successfully converted markdown to HTML: {s3_url}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'html_file': s3_url,
                'filename': filename,
                's3_key': s3_key,
                'bucket': output_bucket,
                'message': 'Conversion successful',
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        logger.error(f"Error converting markdown to HTML: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to convert markdown to HTML',
                'message': str(e)
            })
        }

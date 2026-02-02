import json
import os
import boto3

def lambda_handler(event, context):
    """
    Analyzes sentiment of text content
    """
    try:
        # Determine input source
        if 'body' in event:
            # API Gateway trigger
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            text = body.get('content', '')
            filename = body.get('filename', 'unknown.txt')
        elif 'Records' in event:
            # SQS or other record-based trigger
            # For simplicity, assume text is in the record
            record = event['Records'][0]
            if 'body' in record:
                text = record['body']
                filename = record.get('filename', 'unknown.txt')
            else:
                text = json.dumps(record)
                filename = 'record.json'
        else:
            # Direct invocation or Step Functions
            text = event.get('content', '')
            filename = event.get('filename', 'unknown.txt')
        
        # Truncate text if too long for Comprehend (5000 bytes)
        if len(text.encode('utf-8')) > 5000:
            while len(text.encode('utf-8')) > 5000:
                text = text[:-100]
        
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        comprehend_client = boto3.client('comprehend', region_name=aws_region)
        
        response = comprehend_client.detect_sentiment(
            Text=text,
            LanguageCode='en'
        )
        
        overall_sentiment = response['Sentiment']
        sentiment_score = response['SentimentScore']
        
        result = {
            'filename': filename,
            'Sentiment': overall_sentiment,
            'SentimentScore': sentiment_score,
            'text_preview': text[:100] + '...' if len(text) > 100 else text
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(result),
            'headers': {
                'Content-Type': 'application/json'
            }
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)}),
            'headers': {
                'Content-Type': 'application/json'
            }
        }

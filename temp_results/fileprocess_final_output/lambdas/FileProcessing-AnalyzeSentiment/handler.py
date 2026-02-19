import os
import json
import boto3
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for analyzing sentiment of text content
    
    Expected event format (API Gateway REST API):
    {
        "body": "text content to analyze",
        "headers": {
            "content-type": "text/plain"
        },
        "queryStringParameters": {
            "filename": "example.txt"
        }
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "sentiment": "POSITIVE/NEGATIVE/NEUTRAL/MIXED",
            "sentiment_scores": {
                "Positive": 0.0,
                "Negative": 0.0,
                "Neutral": 0.0,
                "Mixed": 0.0
            },
            "filename": "example.txt",
            "message": "Sentiment analysis successful"
        }
    }
    """
    try:
        logger.info("Starting sentiment analysis")
        
        # Parse the event
        if 'body' not in event:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No text content provided'})
            }
        
        # Get filename from query parameters or use default
        filename = 'unknown.txt'
        if event.get('queryStringParameters') and event['queryStringParameters'].get('filename'):
            filename = event['queryStringParameters']['filename']
        
        # Get text content
        text = event['body']
        if event.get('isBase64Encoded', False):
            import base64
            text = base64.b64decode(text).decode('utf-8')
        
        # Check text length (AWS Comprehend has limits)
        if len(text.encode('utf-8')) > 5000:
            logger.warning(f"Text too long ({len(text.encode('utf-8'))} bytes), truncating to first 5000 bytes")
            while len(text.encode('utf-8')) > 5000:
                text = text[:-100]
        
        # Initialize AWS Comprehend client
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        comprehend_client = boto3.client('comprehend', region_name=aws_region)
        
        # Perform sentiment analysis
        response = comprehend_client.detect_sentiment(
            Text=text,
            LanguageCode='en'
        )
        
        overall_sentiment = response['Sentiment']
        sentiment_score = response['SentimentScore']
        
        sentiment_data = {
            'Sentiment': overall_sentiment,
            'SentimentScore': sentiment_score
        }
        
        logger.info(f"Sentiment analysis completed for {filename}: {overall_sentiment}")
        logger.info(f"Sentiment scores: Positive={sentiment_score['Positive']:.3f}, "
                   f"Negative={sentiment_score['Negative']:.3f}, "
                   f"Neutral={sentiment_score['Neutral']:.3f}, "
                   f"Mixed={sentiment_score['Mixed']:.3f}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'sentiment': overall_sentiment,
                'sentiment_scores': sentiment_score,
                'filename': filename,
                'message': 'Sentiment analysis successful'
            })
        }
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to analyze sentiment',
                'message': str(e)
            })
        }

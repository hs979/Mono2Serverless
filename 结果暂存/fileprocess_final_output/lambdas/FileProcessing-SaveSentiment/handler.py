import os
import json
import boto3
import logging
from datetime import datetime

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Lambda handler for saving sentiment analysis results to DynamoDB
    
    Expected event format (API Gateway REST API GET request):
    {
        "pathParameters": {
            "filename": "example.txt"
        }
    }
    
    OR from AnalyzeSentiment function (direct invocation):
    {
        "filename": "example.txt",
        "sentiment_data": {
            "Sentiment": "POSITIVE",
            "SentimentScore": {
                "Positive": 0.95,
                "Negative": 0.02,
                "Neutral": 0.03,
                "Mixed": 0.00
            }
        }
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "filename": "example.txt",
            "last_modified": "2023-01-01T00:00:00",
            "overall_sentiment": "POSITIVE",
            "scores": {
                "positive": "0.95",
                "negative": "0.02",
                "neutral": "0.03",
                "mixed": "0.00"
            },
            "message": "Sentiment results saved/retrieved successfully"
        }
    }
    """
    try:
        logger.info("Processing sentiment save/retrieve request")
        
        # Get environment variables
        table_name = os.environ.get('SENTIMENT_TABLE')
        if not table_name:
            raise ValueError("SENTIMENT_TABLE environment variable not set")
        
        # Initialize DynamoDB resource
        aws_region = os.getenv('AWS_REGION', 'us-east-1')
        dynamodb = boto3.resource('dynamodb', region_name=aws_region)
        table = dynamodb.Table(table_name)
        
        # Determine if this is a GET request (retrieve) or POST request (save)
        http_method = event.get('httpMethod', '')
        
        if http_method == 'GET':
            # Retrieve sentiment results
            filename = event.get('pathParameters', {}).get('filename')
            if not filename:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Filename parameter is required'})
                }
            
            response = table.get_item(
                Key={'filename': filename}
            )
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'body': json.dumps({'error': f'Sentiment analysis not found for {filename}'})
                }
            
            item = response['Item']
            logger.info(f"Retrieved sentiment results for {filename}: {item.get('overall_sentiment')}")
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'filename': item['filename'],
                    'last_modified': item['last_modified'],
                    'overall_sentiment': item['overall_sentiment'],
                    'scores': {
                        'positive': item['positive'],
                        'negative': item['negative'],
                        'neutral': item['neutral'],
                        'mixed': item['mixed']
                    },
                    'message': 'Sentiment results retrieved successfully'
                })
            }
            
        else:
            # Save sentiment results (POST or direct invocation)
            # Try to get data from different event formats
            filename = None
            sentiment_data = None
            
            # Format 1: Direct invocation from AnalyzeSentiment
            if 'filename' in event and 'sentiment_data' in event:
                filename = event['filename']
                sentiment_data = event['sentiment_data']
            # Format 2: API Gateway POST with body
            elif 'body' in event:
                body = event['body']
                if event.get('isBase64Encoded', False):
                    import base64
                    body = base64.b64decode(body).decode('utf-8')
                body_json = json.loads(body)
                filename = body_json.get('filename')
                sentiment_data = body_json.get('sentiment_data')
                
                # Also check for direct sentiment fields
                if not sentiment_data and 'sentiment' in body_json:
                    sentiment_data = {
                        'Sentiment': body_json.get('sentiment'),
                        'SentimentScore': body_json.get('sentiment_scores', {})
                    }
            
            if not filename or not sentiment_data:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Filename and sentiment_data are required'})
                }
            
            # Validate sentiment_data structure
            if 'Sentiment' not in sentiment_data or 'SentimentScore' not in sentiment_data:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'sentiment_data must contain Sentiment and SentimentScore keys'})
                }
            
            # Save to DynamoDB
            last_modified = datetime.utcnow().isoformat()
            response = table.put_item(
                Item={
                    'filename': filename,
                    'last_modified': last_modified,
                    'overall_sentiment': sentiment_data['Sentiment'],
                    'positive': str(sentiment_data['SentimentScore'].get('Positive', 0.0)),
                    'negative': str(sentiment_data['SentimentScore'].get('Negative', 0.0)),
                    'neutral': str(sentiment_data['SentimentScore'].get('Neutral', 0.0)),
                    'mixed': str(sentiment_data['SentimentScore'].get('Mixed', 0.0))
                }
            )
            
            logger.info(f"Sentiment analysis results saved to DynamoDB: {filename} -> {sentiment_data['Sentiment']}")
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'filename': filename,
                    'last_modified': last_modified,
                    'overall_sentiment': sentiment_data['Sentiment'],
                    'scores': {
                        'positive': str(sentiment_data['SentimentScore'].get('Positive', 0.0)),
                        'negative': str(sentiment_data['SentimentScore'].get('Negative', 0.0)),
                        'neutral': str(sentiment_data['SentimentScore'].get('Neutral', 0.0)),
                        'mixed': str(sentiment_data['SentimentScore'].get('Mixed', 0.0))
                    },
                    'message': 'Sentiment results saved successfully'
                })
            }
            
    except Exception as e:
        logger.error(f"Error saving/retrieving sentiment results: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to save/retrieve sentiment results',
                'message': str(e)
            })
        }

"""
DynamoDB Data Access Layer
Used to save and query sentiment analysis results for file processing

Note: To create the table, please use the init_dynamodb.py script or refer to the README
"""
import boto3
import os
from datetime import datetime

# Get configuration from environment variables, use default values if not set
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'ref-arch-fileprocessing-sentiment')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)

def save_sentiment(filename, sentiment_data):
    """
    Save AWS Comprehend sentiment analysis results to DynamoDB
    
    Parameters
    ----------
    filename: str
        The name of the file being analyzed
    sentiment_data: dict
        Dictionary containing sentiment analysis results, must contain 'Sentiment' and 'SentimentScore' keys
        sentiment_data['Sentiment']: Overall sentiment (POSITIVE/NEGATIVE/NEUTRAL/MIXED)
        sentiment_data['SentimentScore']: Confidence scores for Positive, Negative, Neutral, Mixed
    """
    try:
        table = dynamodb.Table(TABLE_NAME)
        
        last_modified = datetime.utcnow().isoformat()
        response = table.put_item(
            Item={
                'filename': filename,
                'last_modified': last_modified,
                'overall_sentiment': sentiment_data['Sentiment'],
                'positive': str(sentiment_data['SentimentScore']['Positive']),
                'negative': str(sentiment_data['SentimentScore']['Negative']),
                'neutral': str(sentiment_data['SentimentScore']['Neutral']),
                'mixed': str(sentiment_data['SentimentScore']['Mixed'])
            }
        )
        
        print(f"[Database] Sentiment analysis results saved to DynamoDB: {filename} -> {sentiment_data['Sentiment']}")
    except Exception as e:
        print(f"[Database Error] Failed to save sentiment analysis results: {e}")
        raise

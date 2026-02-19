import json
import os
import boto3
from datetime import datetime

def lambda_handler(event, context):
    """
    Saves sentiment analysis results to DynamoDB
    """
    try:
        table_name = os.getenv('SENTIMENT_TABLE', 'ref-arch-fileprocessing-sentiment')
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        # Determine input source
        if 'body' in event:
            # API Gateway trigger (though unlikely)
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            sentiment_data = body
        elif 'Records' in event:
            # SNS or other record-based trigger
            record = event['Records'][0]
            if 'Sns' in record:
                sentiment_data = json.loads(record['Sns']['Message'])
            else:
                sentiment_data = record
        else:
            # Direct invocation or Step Functions
            sentiment_data = event
        
        # Extract required fields
        filename = sentiment_data.get('filename', 'unknown')
        sentiment = sentiment_data.get('Sentiment', 'NEUTRAL')
        sentiment_score = sentiment_data.get('SentimentScore', {
            'Positive': 0.0,
            'Negative': 0.0,
            'Neutral': 1.0,
            'Mixed': 0.0
        })
        
        # Generate ID and timestamp
        import uuid
        item_id = str(uuid.uuid4())
        timestamp = int(datetime.utcnow().timestamp())
        
        # Prepare item
        item = {
            'id': item_id,
            'timestamp': timestamp,
            'filename': filename,
            'sentiment_label': sentiment,
            'sentiment_score': sentiment_score.get('Positive', 0.0),  # Using Positive as numeric sort key for GSI
            'content': sentiment_data.get('text_preview', ''),
            'html_content': sentiment_data.get('html_content', ''),
            'positive': str(sentiment_score.get('Positive', 0.0)),
            'negative': str(sentiment_score.get('Negative', 0.0)),
            'neutral': str(sentiment_score.get('Neutral', 0.0)),
            'mixed': str(sentiment_score.get('Mixed', 0.0))
        }
        
        # Put item
        response = table.put_item(Item=item)
        
        result = {
            'message': 'Sentiment saved successfully',
            'id': item_id,
            'filename': filename,
            'sentiment': sentiment
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

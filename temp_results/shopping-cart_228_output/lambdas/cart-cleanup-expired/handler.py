import os
import json
import boto3
from datetime import datetime
from boto3.dynamodb.conditions import Attr

def cleanup_expired_items():
    """
    Clean up expired cart items.
    Note: DynamoDB TTL will automatically remove expired items; this is a fallback manual cleanup.
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    current_timestamp = int(datetime.now().timestamp())
    
    try:
        # Scan all expired cart items
        response = table.scan(
            FilterExpression=Attr('expirationTime').exists() & Attr('expirationTime').lt(current_timestamp)
        )
        
        deleted_count = 0
        with table.batch_writer() as batch:
            for item in response['Items']:
                batch.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
                deleted_count += 1
        
        return deleted_count
    except Exception as e:
        print(f"Failed to clean up expired items: {e}")
        return 0

def lambda_handler(event, context):
    """
    Internal Lambda handler for cleaning up expired cart items.
    Can be triggered by EventBridge schedule.
    """
    try:
        deleted_count = cleanup_expired_items()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Expired items cleanup completed',
                'deleted_count': deleted_count
            })
        }
        
    except Exception as e:
        print(f"Error in cart-cleanup-expired lambda: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'})
        }

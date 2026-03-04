import os
import json
import boto3
from boto3.dynamodb.conditions import Key

def delete_cart_items(pk):
    """
    Delete all items for a given user/cart.
    
    Args:
        pk: Partition key (user#xxx or cart#xxx)
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        # Query all cart items first
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        # Batch delete
        with table.batch_writer() as batch:
            for item in response['Items']:
                batch.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
        return len(response['Items'])
    except Exception as e:
        print(f"Failed to delete cart items: {e}")
        raise

def lambda_handler(event, context):
    """
    Internal Lambda handler for deleting cart items.
    Called by cart-checkout and cart-migrate functions.
    """
    try:
        # Parse payload from invoking Lambda
        if 'body' in event:
            # If invoked via API Gateway (testing)
            body = json.loads(event['body'])
        else:
            # If invoked directly via Lambda SDK
            body = event
        
        pk = body.get('pk')
        
        if not pk:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Partition key (pk) required'})
            }
        
        deleted_count = delete_cart_items(pk)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Cart items deleted successfully',
                'deleted_count': deleted_count
            })
        }
        
    except Exception as e:
        print(f"Error in cart-delete-items lambda: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal server error'})
        }

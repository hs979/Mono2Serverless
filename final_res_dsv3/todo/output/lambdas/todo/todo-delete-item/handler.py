import json
import os
import boto3
from shared_utils import format_response, get_user_id, get_dynamodb_resource, validate_id

def lambda_handler(event, context):
    """Handler for DELETE /item/{id} - delete a todo item."""
    try:
        # Get user ID from Cognito claims
        username = get_user_id(event)
        if not username:
            return format_response(401, {'message': 'Unauthorized: User not identified'})
        
        # Extract item ID from path parameters
        item_id = event.get('pathParameters', {}).get('id')
        if not validate_id(item_id):
            return format_response(400, {'message': 'Invalid request: Invalid todo item ID'})
        
        # Get DynamoDB resource
        dynamodb = get_dynamodb_resource()
        table_name = os.environ.get('TODO_TABLE')
        if not table_name:
            return format_response(500, {'message': 'Table name not configured'})
        
        table = dynamodb.Table(table_name)
        
        # Delete item
        table.delete_item(
            Key={
                'cognito-username': username,
                'id': item_id
            }
        )
        
        return format_response(200, {
            'message': 'Todo item deleted successfully'
        })
        
    except Exception as e:
        print(f'Failed to delete todo item: {e}')
        return format_response(400, {'message': str(e)})

import json
import os
import boto3
from datetime import datetime
from shared_utils import format_response, get_user_id, get_dynamodb_resource, parse_event_body, validate_id

def lambda_handler(event, context):
    """Handler for PUT /item/{id} - update an existing todo item."""
    try:
        # Get user ID from Cognito claims
        username = get_user_id(event)
        if not username:
            return format_response(401, {'message': 'Unauthorized: User not identified'})
        
        # Extract item ID from path parameters
        item_id = event.get('pathParameters', {}).get('id')
        if not validate_id(item_id):
            return format_response(400, {'message': 'Invalid request: Invalid todo item ID'})
        
        # Parse request body
        body = parse_event_body(event)
        item_content = body.get('item')
        completed = body.get('completed')
        
        if item_content is None or completed is None:
            return format_response(400, {'message': 'Invalid request: Missing required fields'})
        
        # Get DynamoDB resource
        dynamodb = get_dynamodb_resource()
        table_name = os.environ.get('TODO_TABLE')
        if not table_name:
            return format_response(500, {'message': 'Table name not configured'})
        
        table = dynamodb.Table(table_name)
        
        # Update item
        now = datetime.utcnow().isoformat() + 'Z'
        response = table.update_item(
            Key={
                'cognito-username': username,
                'id': item_id
            },
            UpdateExpression='SET completed = :c, lastupdate_date = :lud, #i = :i',
            ExpressionAttributeNames={
                '#i': 'item'
            },
            ExpressionAttributeValues={
                ':c': completed,
                ':lud': now,
                ':i': item_content
            },
            ReturnValues='ALL_NEW'
        )
        
        attributes = response.get('Attributes', {})
        
        return format_response(200, {
            'message': 'Todo item updated successfully',
            'Attributes': attributes
        })
        
    except Exception as e:
        print(f'Failed to update todo item: {e}')
        return format_response(400, {'message': str(e)})

import json
import os
import boto3
import uuid
from datetime import datetime
from shared_utils import format_response, get_user_id, get_dynamodb_resource, parse_event_body

def lambda_handler(event, context):
    """Handler for POST /item - create a new todo item."""
    try:
        # Get user ID from Cognito claims
        username = get_user_id(event)
        if not username:
            return format_response(401, {'message': 'Unauthorized: User not identified'})
        
        # Parse request body
        body = parse_event_body(event)
        item_content = body.get('item')
        completed = body.get('completed', False)
        
        if not item_content:
            return format_response(400, {'message': 'Invalid request: Todo item content cannot be empty'})
        
        # Generate ID and timestamps
        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + 'Z'
        
        todo_item = {
            'cognito-username': username,
            'id': item_id,
            'item': item_content,
            'completed': completed,
            'creation_date': now,
            'lastupdate_date': now
        }
        
        # Get DynamoDB resource
        dynamodb = get_dynamodb_resource()
        table_name = os.environ.get('TODO_TABLE')
        if not table_name:
            return format_response(500, {'message': 'Table name not configured'})
        
        table = dynamodb.Table(table_name)
        
        # Put item
        table.put_item(Item=todo_item)
        
        return format_response(200, {
            'message': 'Todo item created successfully',
            'item': todo_item
        })
        
    except Exception as e:
        print(f'Failed to create todo item: {e}')
        return format_response(400, {'message': str(e)})

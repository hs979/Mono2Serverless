import json
import os
import boto3
from shared_utils import format_response, get_user_id, get_dynamodb_resource

def lambda_handler(event, context):
    """Handler for GET /item - retrieve all todo items for the authenticated user."""
    try:
        # Get user ID from Cognito claims
        username = get_user_id(event)
        if not username:
            return format_response(401, {'message': 'Unauthorized: User not identified'})
        
        # Get DynamoDB resource
        dynamodb = get_dynamodb_resource()
        table_name = os.environ.get('TODO_TABLE')
        if not table_name:
            return format_response(500, {'message': 'Table name not configured'})
        
        table = dynamodb.Table(table_name)
        
        # Query items for the user
        response = table.query(
            KeyConditionExpression='cognito-username = :username',
            ExpressionAttributeValues={
                ':username': username
            }
        )
        
        items = response.get('Items', [])
        count = response.get('Count', 0)
        
        return format_response(200, {
            'Items': items,
            'Count': count
        })
        
    except Exception as e:
        print(f'Failed to fetch todo list: {e}')
        return format_response(400, {'message': str(e)})

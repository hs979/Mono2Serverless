import json
import os
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_dynamodb_client():
    """Return a DynamoDB client."""
    return boto3.client('dynamodb')

def get_dynamodb_resource():
    """Return a DynamoDB resource."""
    return boto3.resource('dynamodb')

def format_response(status_code, body, headers=None):
    """Format API Gateway response."""
    if headers is None:
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        }
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(body)
    }

def get_user_id(event):
    """Extract user ID (Cognito username) from API Gateway event."""
    # Cognito authorizer provides claims in requestContext.authorizer.claims
    # The username is stored in 'cognito:username' or 'username' claim
    try:
        claims = event.get('requestContext', {}).get('authorizer', {}).get('claims', {})
        # Cognito User Pool uses 'cognito:username' for the username attribute
        username = claims.get('cognito:username') or claims.get('username')
        if not username:
            logger.error('No username found in claims')
            return None
        return username
    except Exception as e:
        logger.error(f'Error extracting user ID: {e}')
        return None

def parse_event_body(event):
    """Parse JSON body from API Gateway event."""
    try:
        body = event.get('body', '{}')
        if isinstance(body, str):
            return json.loads(body)
        return body
    except json.JSONDecodeError as e:
        logger.error(f'Invalid JSON body: {e}')
        return {}

def validate_id(item_id):
    """Validate todo item ID format."""
    import re
    if not item_id or not re.match(r'^[\w-]+$', item_id):
        return False
    return True

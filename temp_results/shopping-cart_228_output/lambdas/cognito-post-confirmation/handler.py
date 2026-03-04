import os
import json
import boto3
import uuid
from datetime import datetime

def create_user_profile(user_id, username, email):
    """
    Create a user profile record in DynamoDB.
    
    Args:
        user_id: Cognito user UUID (sub)
        username: Username
        email: Email address
    
    Returns:
        User ID
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    # User record: pk='USER#{username}', sk='PROFILE'
    item = {
        'pk': f'USER#{username}',
        'sk': 'PROFILE',
        'id': user_id,
        'username': username,
        'email': email,
        'created_at': datetime.now().isoformat()
    }
    
    try:
        # Use a conditional expression to ensure username uniqueness
        table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(pk)'
        )
        return user_id
    except Exception as e:
        print(f"Failed to create user profile: {e}")
        # If user already exists (should not happen with Cognito), return existing user ID
        return user_id

def lambda_handler(event, context):
    """
    Cognito Post-Confirmation Trigger Lambda handler.
    Creates a user profile record in DynamoDB after successful registration.
    """
    try:
        # Extract user attributes from Cognito event
        user_attributes = event.get('request', {}).get('userAttributes', {})
        
        user_id = user_attributes.get('sub')  # Cognito UUID
        username = user_attributes.get('preferred_username') or user_attributes.get('email')
        email = user_attributes.get('email')
        
        if not user_id or not username:
            print(f"Missing required user attributes: {user_attributes}")
            # Return event unchanged for Cognito
            return event
        
        # Create user profile in DynamoDB
        create_user_profile(user_id, username, email)
        
        print(f"Created user profile for {username} ({user_id})")
        
        # Return event unchanged for Cognito
        return event
        
    except Exception as e:
        print(f"Error in cognito-post-confirmation lambda: {str(e)}")
        # Don't fail the Cognito flow - return event anyway
        return event

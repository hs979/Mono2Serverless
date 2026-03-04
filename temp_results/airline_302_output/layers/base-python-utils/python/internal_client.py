import os
import json
import boto3
from decimal import Decimal
from typing import Any, Dict, Optional


def invoke_lambda(function_name: str, payload: Dict[str, Any], invocation_type: str = "RequestResponse") -> Optional[Dict[str, Any]]:
    """
    Invoke another Lambda function using AWS SDK.
    
    Args:
        function_name: Target Lambda function name (can be from environment variable)
        payload: Dictionary payload to send
        invocation_type: "RequestResponse" (sync) or "Event" (async)
        
    Returns:
        Parsed response payload for RequestResponse, None for Event
    """
    lambda_client = boto3.client('lambda')
    
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType=invocation_type,
            Payload=json.dumps(payload, cls=DecimalEncoder)
        )
        
        if invocation_type == "RequestResponse":
            response_payload = json.loads(response['Payload'].read())
            return response_payload
        else:
            return None
            
    except Exception as e:
        print(f"Error invoking Lambda {function_name}: {str(e)}")
        raise


def get_user_id_from_event(event: Dict[str, Any]) -> str:
    """
    Extract user_id from Cognito claims in API Gateway event.
    """
    try:
        # Get user_id from pre-validated Cognito claims
        user_id = event['requestContext']['authorizer']['claims']['sub']  # UUID
        return user_id
    except KeyError:
        raise ValueError("User ID not found in event. Ensure Cognito authorizer is configured.")


def get_user_profile(user_id: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    Query UserProfiles table for user profile.
    """
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(Key={'userId': user_id})
        return response.get('Item')
    except Exception as e:
        print(f"Error getting user profile for {user_id}: {str(e)}")
        return None


def python_obj_to_dynamodb(obj: Any) -> Any:
    """Convert Python objects to DynamoDB compatible format (float to Decimal)"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [python_obj_to_dynamodb(item) for item in obj]
    return obj


def dynamodb_to_python_obj(obj: Any) -> Any:
    """Convert DynamoDB objects to Python format (Decimal to int/float)"""
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [dynamodb_to_python_obj(item) for item in obj]
    return obj


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal objects"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            # Convert to int if it's a whole number, otherwise float
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def create_response(status_code: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Create a standard API Gateway response.
    """
    default_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    if headers:
        default_headers.update(headers)
    
    return {
        'statusCode': status_code,
        'headers': default_headers,
        'body': json.dumps(body, cls=DecimalEncoder)
    }


def handle_error(error: Exception) -> Dict[str, Any]:
    """
    Handle errors and return appropriate response.
    """
    error_message = str(error)
    error_type = type(error).__name__
    
    if isinstance(error, ValueError):
        status_code = 400
    else:
        status_code = 500
    
    return create_response(status_code, {
        'error': error_message,
        'type': error_type
    })

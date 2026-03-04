
"""
Shared utilities for Lambda functions
"""
import json
import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional, Union

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO if os.environ.get('STAGE') == 'prod' else logging.DEBUG)


def format_response(status_code: int, body: Any, headers: Optional[Dict] = None) -> Dict:
    """
    Format Lambda response for API Gateway
    
    Args:
        status_code: HTTP status code
        body: Response body (will be JSON serialized)
        headers: Optional custom headers
        
    Returns:
        API Gateway compatible response
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
        'body': json.dumps(body, default=decimal_default)
    }


def decimal_default(obj: Any) -> Any:
    """
    JSON serializer for Decimal objects
    
    Args:
        obj: Object to serialize
        
    Returns:
        Serializable object
    """
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def get_user_id(event: Dict) -> str:
    """
    Extract user ID from Cognito claims in API Gateway event
    
    Args:
        event: Lambda event
        
    Returns:
        User ID (Cognito sub)
        
    Raises:
        ValueError: If user ID not found
    """
    try:
        # Get user_id from pre-validated Cognito claims
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims['sub']  # UUID
        return user_id
    except KeyError as e:
        logger.error(f"Failed to extract user ID from event: {e}")
        raise ValueError("User authentication required")


def get_path_parameter(event: Dict, param_name: str) -> str:
    """
    Get path parameter from event
    
    Args:
        event: Lambda event
        param_name: Parameter name
        
    Returns:
        Parameter value
        
    Raises:
        ValueError: If parameter not found
    """
    try:
        param = event['pathParameters'][param_name]
        if not param:
            raise ValueError(f"Path parameter '{param_name}' is empty")
        return param
    except (KeyError, TypeError):
        raise ValueError(f"Path parameter '{param_name}' is required")


def get_query_parameter(event: Dict, param_name: str, default: Any = None) -> Any:
    """
    Get query parameter from event
    
    Args:
        event: Lambda event
        param_name: Parameter name
        default: Default value if parameter not found
        
    Returns:
        Parameter value or default
    """
    try:
        params = event.get('queryStringParameters', {}) or {}
        return params.get(param_name, default)
    except (KeyError, TypeError):
        return default


def get_body(event: Dict) -> Dict:
    """
    Parse JSON body from event
    
    Args:
        event: Lambda event
        
    Returns:
        Parsed body as dict
        
    Raises:
        ValueError: If body is invalid or missing
    """
    try:
        body = event.get('body', '{}')
        if not body:
            return {}
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON body: {str(e)}")


def log_error(error: Exception, context: Any = None) -> None:
    """
    Log error with context
    
    Args:
        error: Exception to log
        context: Optional Lambda context
    """
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
    }
    
    if context:
        error_info.update({
            'aws_request_id': context.aws_request_id,
            'function_name': context.function_name,
            'function_version': context.function_version,
        })
    
    logger.error(json.dumps(error_info))
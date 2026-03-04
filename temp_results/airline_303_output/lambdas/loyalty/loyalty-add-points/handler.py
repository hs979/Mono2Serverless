"""
Lambda handler for POST /loyalty/{customer_id}/points
"""
import json
import os
import uuid
import boto3
from datetime import datetime
from decimal import Decimal
from shared_utils import format_response, get_user_id, get_path_parameter, get_body, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
LOYALTY_TABLE = os.environ['LOYALTY_TABLE']
loyalty_table = dynamodb.Table(LOYALTY_TABLE)


def _python_obj_to_dynamodb(obj):
    """Convert Python objects to DynamoDB compatible format (float to Decimal)"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_python_obj_to_dynamodb(item) for item in obj]
    return obj


def add_loyalty_points(customer_id: str, points: int) -> dict:
    """
    Add loyalty points for a customer
    
    Args:
        customer_id: Customer identifier
        points: Number of points to add
        
    Returns:
        Success message
        
    Raises:
        ValueError: If points is invalid
    """
    if not isinstance(points, (int, float)) or points <= 0:
        raise ValueError("Points must be a positive number")
    
    loyalty_id = str(uuid.uuid4())
    loyalty_entry = {
        'id': loyalty_id,
        'customerId': customer_id,
        'points': int(points),
        'flag': 'active',
        'date': datetime.now().isoformat()
    }
    
    try:
        loyalty_item = _python_obj_to_dynamodb(loyalty_entry)
        loyalty_table.put_item(Item=loyalty_item)
        
        return {
            'message': 'Loyalty points added successfully',
            'customerId': customer_id,
            'pointsAdded': int(points)
        }
    except Exception as e:
        raise ValueError(f"Failed to add loyalty points: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for POST /loyalty/{customer_id}/points
    """
    try:
        # Get user ID from Cognito
        user_id = get_user_id(event)
        
        # Extract path parameter
        customer_id = get_path_parameter(event, 'customer_id')
        
        # Check authorization: user must be admin
        # In production, you would check Cognito groups here
        # For now, we'll allow any authenticated user (simplified)
        # In real implementation, use API Gateway authorizer with Cognito groups
        
        # Parse request body
        data = get_body(event)
        
        if not data or 'points' not in data:
            return format_response(400, {'error': 'points is required'})
        
        # Add loyalty points
        result = add_loyalty_points(customer_id, data['points'])
        
        return format_response(200, result)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})

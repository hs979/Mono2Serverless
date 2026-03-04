"""
Lambda handler for GET /loyalty/{customer_id}
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Attr
from decimal import Decimal
from shared_utils import format_response, get_user_id, get_path_parameter, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
LOYALTY_TABLE = os.environ['LOYALTY_TABLE']
loyalty_table = dynamodb.Table(LOYALTY_TABLE)


def _dynamodb_to_python_obj(obj):
    """Convert DynamoDB objects to Python format (Decimal to int/float)"""
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_dynamodb_to_python_obj(item) for item in obj]
    return obj


def get_loyalty_points(customer_id: str) -> int:
    """Get total active loyalty points for a customer"""
    try:
        # Use scan with filter
        response = loyalty_table.scan(
            FilterExpression=Attr('customerId').eq(customer_id) &
                            Attr('flag').eq('active')
        )
        
        items = response.get('Items', [])
        total = 0
        for item in items:
            points = item.get('points', 0)
            if isinstance(points, Decimal):
                total += int(points)
            else:
                total += int(points)
        
        return total
    except Exception as e:
        raise ValueError(f"Error getting loyalty points for {customer_id}: {str(e)}")


def get_loyalty_level(points: int) -> str:
    """Calculate loyalty level based on points"""
    if points >= 100000:
        return 'gold'
    elif points >= 50000:
        return 'silver'
    else:
        return 'bronze'


def get_remaining_points_to_next_tier(points: int, level: str) -> int:
    """Calculate points needed for next tier"""
    if level == 'bronze':
        return 50000 - points
    elif level == 'silver':
        return 100000 - points
    else:
        return 0


def get_customer_loyalty(customer_id: str) -> dict:
    """
    Get loyalty information for a customer
    
    Args:
        customer_id: Customer identifier
        
    Returns:
        Dictionary containing:
            - points: Total loyalty points
            - level: Current tier (bronze, silver, gold)
            - remainingPoints: Points needed for next tier
    """
    total_points = get_loyalty_points(customer_id)
    level = get_loyalty_level(total_points)
    remaining_points = get_remaining_points_to_next_tier(total_points, level)
    
    return {
        'points': total_points,
        'level': level,
        'remainingPoints': remaining_points
    }


def lambda_handler(event, context):
    """
    Handler for GET /loyalty/{customer_id}
    """
    try:
        # Get user ID from Cognito
        user_id = get_user_id(event)
        
        # Extract path parameter
        customer_id = get_path_parameter(event, 'customer_id')
        
        # Check authorization: user must be owner or admin
        if customer_id != user_id:
            # In production, you would check Cognito groups here
            # For now, return forbidden
            return format_response(403, {
                'error': 'Access denied. You can only access your own loyalty information.'
            })
        
        # Get loyalty info
        loyalty = get_customer_loyalty(customer_id)
        
        return format_response(200, loyalty)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})

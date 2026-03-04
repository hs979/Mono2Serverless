
"""
Lambda handler for GET /customers/{customer_id}/bookings
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Attr
from decimal import Decimal
from shared_utils import format_response, get_user_id, get_path_parameter, get_query_parameter, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
BOOKING_TABLE = os.environ['BOOKING_TABLE']
booking_table = dynamodb.Table(BOOKING_TABLE)


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


def get_customer_bookings(customer_id: str, status: str = None):
    """
    Get all bookings for a customer, optionally filtered by status
    
    Args:
        customer_id: Customer identifier
        status: Optional status filter (UNCONFIRMED, CONFIRMED, CANCELLED)
        
    Returns:
        List of bookings
    """
    try:
        # Use scan with filter (for small datasets)
        # For production, consider using GSI on customer field
        filter_expr = Attr('customer').eq(customer_id)
        if status:
            filter_expr = filter_expr & Attr('status').eq(status)
        
        response = booking_table.scan(FilterExpression=filter_expr)
        
        items = response.get('Items', [])
        bookings = [_dynamodb_to_python_obj(item) for item in items]
        return bookings
    except Exception as e:
        raise ValueError(f"Error getting bookings for customer {customer_id}: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for GET /customers/{customer_id}/bookings
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
                'error': 'Access denied. You can only access your own bookings.'
            })
        
        # Get optional status filter
        status = get_query_parameter(event, 'status')
        
        # Get bookings
        bookings = get_customer_bookings(customer_id, status)
        
        return format_response(200, {'bookings': bookings})
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
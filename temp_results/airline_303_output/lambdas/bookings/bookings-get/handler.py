
"""
Lambda handler for GET /bookings/{booking_id}
"""
import json
import os
import boto3
from decimal import Decimal
from shared_utils import format_response, get_user_id, get_path_parameter, log_error


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


def get_booking(booking_id: str):
    """
    Get booking details
    
    Args:
        booking_id: Booking identifier
        
    Returns:
        Booking details
        
    Raises:
        ValueError: If booking not found
    """
    try:
        response = booking_table.get_item(Key={'id': booking_id})
        if 'Item' in response:
            return _dynamodb_to_python_obj(response['Item'])
        return None
    except Exception as e:
        raise ValueError(f"Error getting booking {booking_id}: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for GET /bookings/{booking_id}
    """
    try:
        # Get user ID from Cognito
        user_id = get_user_id(event)
        
        # Extract path parameter
        booking_id = get_path_parameter(event, 'booking_id')
        
        # Get booking
        booking = get_booking(booking_id)
        if not booking:
            return format_response(404, {'error': f'Booking {booking_id} not found'})
        
        # Check authorization: user must be owner or admin
        # In Cognito, admin check would be via groups, but for simplicity
        # we'll just check if user is the owner
        # Note: Actual admin check should be done via Cognito groups in API Gateway authorizer
        if booking['customer'] != user_id:
            # In production, you would check Cognito groups here
            # For now, return forbidden
            return format_response(403, {
                'error': 'Access denied. You can only access your own bookings.'
            })
        
        return format_response(200, booking)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
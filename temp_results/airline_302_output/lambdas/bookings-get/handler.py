import json
import os
import sys
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error,
    dynamodb_to_python_obj,
    get_user_id_from_event
)
import boto3


def lambda_handler(event, context):
    """
    Get booking details (requires authentication, owner or admin only)
    """
    try:
        # Get user_id from Cognito claims
        user_id = get_user_id_from_event(event)
        
        # Extract booking_id from path parameters
        booking_id = event.get('pathParameters', {}).get('booking_id')
        
        if not booking_id:
            return create_response(400, {'error': 'booking_id is required in path'})
        
        # Get booking using DynamoDB
        booking = get_booking(booking_id)
        
        if not booking:
            return create_response(404, {'error': f'Booking {booking_id} not found'})
        
        # Check authorization: user must be admin or booking owner
        if not is_authorized(user_id, booking):
            return create_response(403, {
                'error': 'Access denied. You can only access your own bookings.'
            })
        
        return create_response(200, booking)
        
    except Exception as e:
        return handle_error(e)


def get_booking(booking_id: str):
    """Get booking by ID"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('BOOKING_TABLE')
    
    if not table_name:
        raise ValueError("BOOKING_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(Key={'id': booking_id})
        if 'Item' in response:
            return dynamodb_to_python_obj(response['Item'])
        return None
    except Exception as e:
        print(f"Error getting booking {booking_id}: {str(e)}")
        return None


def is_authorized(user_id: str, booking: dict) -> bool:
    """Check if user is authorized to access booking"""
    # User is authorized if they are the booking owner
    if booking.get('customer') == user_id:
        return True
    
    # Check if user is admin (would need to query user profile)
    # For now, we'll implement a simple check - in production, query UserProfiles table
    # This is a simplified implementation
    return False  # Non-admin users can only access their own bookings

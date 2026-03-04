import json
import os
import sys
import secrets
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error,
    invoke_lambda,
    dynamodb_to_python_obj,
    get_user_id_from_event
)
import boto3


def lambda_handler(event, context):
    """
    Confirm a booking (requires authentication, owner or admin only)
    """
    try:
        # Get user_id from Cognito claims
        user_id = get_user_id_from_event(event)
        
        # Extract booking_id from path parameters
        booking_id = event.get('pathParameters', {}).get('booking_id')
        
        if not booking_id:
            return create_response(400, {'error': 'booking_id is required in path'})
        
        # Get booking to check authorization
        booking = get_booking(booking_id)
        if not booking:
            return create_response(404, {'error': f'Booking {booking_id} not found'})
        
        # Check authorization
        if not is_authorized(user_id, booking):
            return create_response(403, {
                'error': 'Access denied. You can only access your own bookings.'
            })
        
        # Confirm booking
        booking_reference = confirm_booking(booking_id)
        
        # Send notification (async)
        try:
            invoke_lambda(
                os.environ.get('NOTIFY_BOOKING_FUNCTION_NAME'),
                {
                    'customerId': booking['customer'],
                    'price': 150,  # Default price
                    'bookingReference': booking_reference
                },
                'Event'
            )
        except Exception as e:
            print(f"Warning: Failed to send notification: {str(e)}")
        
        return create_response(200, {
            'bookingId': booking_id,
            'bookingReference': booking_reference,
            'status': 'CONFIRMED'
        })
        
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
    return booking.get('customer') == user_id  # Simplified - add admin check in production


def confirm_booking(booking_id: str) -> str:
    """Confirm a booking and generate booking reference"""
    booking = get_booking(booking_id)
    if not booking:
        raise ValueError(f"Invalid booking ID: {booking_id}")
    
    # Generate a booking reference
    reference = secrets.token_urlsafe(4)
    
    # Update booking status to CONFIRMED
    update_booking_status(booking_id, 'CONFIRMED', reference)
    
    return reference


def update_booking_status(booking_id: str, status: str, booking_reference: str = None):
    """Update booking status"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('BOOKING_TABLE')
    
    if not table_name:
        raise ValueError("BOOKING_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        update_expr = 'SET #status = :status'
        expr_attr_names = {'#status': 'status'}
        expr_attr_values = {':status': status}
        
        if booking_reference:
            update_expr += ', bookingReference = :ref'
            expr_attr_values[':ref'] = booking_reference
        
        response = table.update_item(
            Key={'id': booking_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
            ConditionExpression='attribute_exists(id)',
            ReturnValues='ALL_NEW'
        )
        
        return dynamodb_to_python_obj(response['Attributes'])
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Booking {booking_id} not found")
    except Exception as e:
        raise ValueError(f"Failed to update booking: {str(e)}")

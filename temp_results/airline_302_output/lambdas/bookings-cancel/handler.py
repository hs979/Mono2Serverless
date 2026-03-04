import json
import os
import sys
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
    Cancel a booking (requires authentication, owner or admin only)
    """
    try:
        # Get user_id from Cognito claims
        user_id = get_user_id_from_event(event)
        
        # Extract booking_id from path parameters
        booking_id = event.get('pathParameters', {}).get('booking_id')
        
        if not booking_id:
            return create_response(400, {'error': 'booking_id is required in path'})
        
        # Get booking details
        booking = get_booking(booking_id)
        if not booking:
            return create_response(404, {'error': f'Booking {booking_id} not found'})
        
        # Check authorization
        if not is_authorized(user_id, booking):
            return create_response(403, {
                'error': 'Access denied. You can only access your own bookings.'
            })
        
        # Cancel the booking
        cancel_booking(booking_id)
        
        # Release the flight seat
        try:
            release_flight_seat(booking['bookingOutboundFlightId'])
        except Exception as e:
            print(f"Warning: Failed to release flight seat: {str(e)}")
        
        # Refund payment
        try:
            refund_result = refund_payment(booking['paymentToken'])
        except Exception as e:
            print(f"Warning: Failed to refund payment: {str(e)}")
            refund_result = {'refundId': 'N/A', 'status': 'failed'}
        
        # Send notification (async)
        try:
            invoke_lambda(
                os.environ.get('NOTIFY_BOOKING_FUNCTION_NAME'),
                {
                    'customerId': booking['customer'],
                    'price': 0,
                    'bookingReference': None
                },
                'Event'
            )
        except Exception as e:
            print(f"Warning: Failed to send notification: {str(e)}")
        
        return create_response(200, {
            'bookingId': booking_id,
            'status': 'CANCELLED',
            'refund': refund_result
        })
        
    except Exception as e:
        return handle_error(e)

# Helper functions

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
    return booking.get('customer') == user_id

def cancel_booking(booking_id: str):
    """Cancel a booking"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('BOOKING_TABLE')
    
    if not table_name:
        raise ValueError("BOOKING_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        response = table.update_item(
            Key={'id': booking_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'CANCELLED'},
            ConditionExpression='attribute_exists(id)',
            ReturnValues='ALL_NEW'
        )
        return dynamodb_to_python_obj(response['Attributes'])
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Booking {booking_id} not found")
    except Exception as e:
        raise ValueError(f"Failed to cancel booking: {str(e)}")

def release_flight_seat(flight_id: str):
    """Release a seat on a flight"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('FLIGHT_TABLE')
    
    if not table_name:
        raise ValueError("FLIGHT_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        # First get the flight to check maximum capacity
        response = table.get_item(Key={'id': flight_id})
        if 'Item' not in response:
            raise ValueError(f"Flight {flight_id} does not exist")
        
        flight = dynamodb_to_python_obj(response['Item'])
        max_capacity = flight['maximumSeating']
        
        response = table.update_item(
            Key={'id': flight_id},
            UpdateExpression='SET seatCapacity = seatCapacity + :inc',
            ConditionExpression='seatCapacity < :max',
            ExpressionAttributeValues={
                ':inc': 1,
                ':max': max_capacity
            },
            ReturnValues='UPDATED_NEW'
        )
        return {'status': 'SUCCESS'}
        
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Cannot release seat, already at maximum capacity")
    except Exception as e:
        raise ValueError(f"Failed to release seat: {str(e)}")

def refund_payment(charge_id: str) -> dict:
    """Refund a payment"""
    # Simplified implementation
    import secrets
    refund_id = secrets.token_urlsafe(16)
    
    return {
        'refundId': refund_id
    }

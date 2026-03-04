
"""
Lambda handler for POST /bookings/{booking_id}/confirm
"""
import json
import os
import secrets
import boto3
from shared_utils import format_response, get_user_id, get_path_parameter, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
BOOKING_TABLE = os.environ['BOOKING_TABLE']
booking_table = dynamodb.Table(BOOKING_TABLE)


def confirm_booking(booking_id: str) -> str:
    """
    Confirm a booking and generate booking reference
    
    Args:
        booking_id: Booking identifier
        
    Returns:
        booking_reference: Generated booking reference code
        
    Raises:
        ValueError: If booking not found
    """
    # Get booking
    response = booking_table.get_item(Key={'id': booking_id})
    if 'Item' not in response:
        raise ValueError(f"Invalid booking ID: {booking_id}")
    
    # Generate a booking reference
    reference = secrets.token_urlsafe(4)
    
    # Update booking status to CONFIRMED
    try:
        booking_table.update_item(
            Key={'id': booking_id},
            UpdateExpression='SET #status = :status, bookingReference = :ref',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'CONFIRMED',
                ':ref': reference
            },
            ConditionExpression='attribute_exists(id)',
            ReturnValues='ALL_NEW'
        )
        return reference
    except Exception as e:
        raise ValueError(f"Failed to confirm booking: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for POST /bookings/{booking_id}/confirm
    """
    try:
        # Get user ID from Cognito
        user_id = get_user_id(event)
        
        # Extract path parameter
        booking_id = get_path_parameter(event, 'booking_id')
        
        # First get booking to check ownership
        response = booking_table.get_item(Key={'id': booking_id})
        if 'Item' not in response:
            return format_response(404, {'error': f'Booking {booking_id} not found'})
        
        booking = response['Item']
        
        # Check authorization: user must be owner or admin
        if booking['customer'] != user_id:
            # In production, you would check Cognito groups here
            # For now, return forbidden
            return format_response(403, {
                'error': 'Access denied. You can only confirm your own bookings.'
            })
        
        # Confirm booking
        booking_reference = confirm_booking(booking_id)
        
        return format_response(200, {
            'bookingId': booking_id,
            'bookingReference': booking_reference,
            'status': 'CONFIRMED'
        })
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
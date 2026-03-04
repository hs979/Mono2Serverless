"""
Internal Lambda for sending booking notifications (invoked by bookings-create and bookings-cancel)
"""
import json
import os
import secrets
from shared_utils import log_error


def notify_booking(customer_id: str, price: float, booking_reference: str = None) -> dict:
    """
    Simulate booking notification
    
    Args:
        customer_id: Customer identifier
        price: Booking price
        booking_reference: Booking reference (if confirmed)
        
    Returns:
        Notification details
    """
    booking_status = 'confirmed' if booking_reference else 'cancelled'
    reference_text = booking_reference or 'most recent booking'
    
    notification = {
        'notificationId': secrets.token_urlsafe(16),
        'customerId': customer_id,
        'price': price,
        'status': booking_status,
        'subject': f"Booking {booking_status} for {reference_text}"
    }
    
    return notification


def lambda_handler(event, context):
    """
    Handler for internal bookings-notify Lambda
    Expected event format: {'customer_id': '...', 'price': 150, 'booking_reference': '...' (optional)}
    """
    try:
        # Extract data from event
        customer_id = event.get('customer_id')
        price = event.get('price', 0)
        booking_reference = event.get('booking_reference')
        
        if not customer_id:
            raise ValueError("customer_id is required")
        
        # Send notification
        notification = notify_booking(customer_id, price, booking_reference)
        
        return {
            'statusCode': 200,
            'body': json.dumps(notification)
        }
        
    except ValueError as e:
        log_error(e, context)
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        log_error(e, context)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Internal server error'})
        }

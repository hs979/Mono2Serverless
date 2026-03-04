"""
Internal Lambda for reserving a booking (invoked by bookings-create)
"""
import json
import os
import uuid
import boto3
from datetime import datetime
from decimal import Decimal
from shared_utils import log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
BOOKING_TABLE = os.environ['BOOKING_TABLE']
booking_table = dynamodb.Table(BOOKING_TABLE)


def _python_obj_to_dynamodb(obj):
    """Convert Python objects to DynamoDB compatible format (float to Decimal)"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_python_obj_to_dynamodb(item) for item in obj]
    return obj


def validate_booking_request(booking_data: dict) -> bool:
    """Validate booking request has required fields"""
    required_fields = ['outboundFlightId', 'customerId', 'chargeId']
    return all(field in booking_data for field in required_fields)


def reserve_booking(booking_data: dict) -> str:
    """
    Create a new booking with UNCONFIRMED status
    
    Args:
        booking_data: Dictionary containing:
            - outboundFlightId: Flight ID
            - customerId: Customer ID
            - chargeId: Payment authorization token
            - name: Optional execution name/ID
            
    Returns:
        booking_id: The newly created booking ID
        
    Raises:
        ValueError: If booking data is invalid
    """
    if not validate_booking_request(booking_data):
        raise ValueError("Invalid booking request: missing required fields")
    
    booking_id = str(uuid.uuid4())
    booking = {
        'id': booking_id,
        'stateExecutionId': booking_data.get('stateExecutionId', ''),
        '__typename': 'Booking',
        'bookingOutboundFlightId': booking_data['outboundFlightId'],
        'checkedIn': False,
        'customer': booking_data['customerId'],
        'paymentToken': booking_data['chargeId'],
        'status': 'UNCONFIRMED',
        'createdAt': datetime.now().isoformat(),
        'bookingReference': None
    }
    
    try:
        booking_item = _python_obj_to_dynamodb(booking)
        booking_table.put_item(Item=booking_item)
        return booking_id
    except Exception as e:
        raise ValueError(f"Failed to create booking: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for internal bookings-reserve Lambda
    Expected event format: {'booking_data': {...}}
    """
    try:
        # Extract booking data from event
        booking_data = event.get('booking_data', {})
        
        # Reserve booking
        booking_id = reserve_booking(booking_data)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'booking_id': booking_id,
                'status': 'UNCONFIRMED'
            })
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

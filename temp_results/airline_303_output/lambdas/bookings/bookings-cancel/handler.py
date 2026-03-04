
"""
Lambda handler for POST /bookings/{booking_id}/cancel
"""
import json
import os
import boto3
from shared_utils import format_response, get_user_id, get_path_parameter, log_error


# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

# Environment variables
BOOKING_TABLE = os.environ['BOOKING_TABLE']
FLIGHT_TABLE = os.environ['FLIGHT_TABLE']
FLIGHTS_RELEASE_SEAT_FUNCTION_NAME = os.environ['FLIGHTS_RELEASE_SEAT_FUNCTION_NAME']
PAYMENTS_REFUND_FUNCTION_NAME = os.environ['PAYMENTS_REFUND_FUNCTION_NAME']
BOOKINGS_NOTIFY_FUNCTION_NAME = os.environ['BOOKINGS_NOTIFY_FUNCTION_NAME']

# DynamoDB tables
booking_table = dynamodb.Table(BOOKING_TABLE)
flight_table = dynamodb.Table(FLIGHT_TABLE)


def invoke_lambda_async(function_name: str, payload: dict):
    """
    Invoke Lambda function asynchronously (fire-and-forget)
    
    Args:
        function_name: Lambda function name
        payload: Payload to send
    """
    try:
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
    except Exception as e:
        print(f"Warning: Failed to invoke {function_name} asynchronously: {str(e)}")


def cancel_booking(booking_id: str) -> bool:
    """
    Cancel a booking
    
    Args:
        booking_id: Booking identifier
        
    Returns:
        True if successful
        
    Raises:
        ValueError: If booking not found
    """
    # Update booking status to CANCELLED
    try:
        booking_table.update_item(
            Key={'id': booking_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'CANCELLED'},
            ConditionExpression='attribute_exists(id)',
            ReturnValues='ALL_NEW'
        )
        return True
    except Exception as e:
        raise ValueError(f"Failed to cancel booking: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for POST /bookings/{booking_id}/cancel
    """
    try:
        # Get user ID from Cognito
        user_id = get_user_id(event)
        
        # Extract path parameter
        booking_id = get_path_parameter(event, 'booking_id')
        
        # Get booking details
        response = booking_table.get_item(Key={'id': booking_id})
        if 'Item' not in response:
            return format_response(404, {'error': f'Booking {booking_id} not found'})
        
        booking = response['Item']
        
        # Check authorization: user must be owner or admin
        if booking['customer'] != user_id:
            # In production, you would check Cognito groups here
            # For now, return forbidden
            return format_response(403, {
                'error': 'Access denied. You can only cancel your own bookings.'
            })
        
        # Cancel the booking
        cancel_booking(booking_id)
        
        # Release the flight seat (async)
        try:
            invoke_lambda_async(
                FLIGHTS_RELEASE_SEAT_FUNCTION_NAME,
                {'flight_id': booking['bookingOutboundFlightId']}
            )
        except Exception as e:
            print(f"Warning: Failed to release flight seat: {str(e)}")
        
        # Refund payment (async)
        try:
            invoke_lambda_async(
                PAYMENTS_REFUND_FUNCTION_NAME,
                {'chargeId': booking['paymentToken']}
            )
            refund_result = {'refundId': 'processing', 'status': 'initiated'}
        except Exception as e:
            print(f"Warning: Failed to refund payment: {str(e)}")
            refund_result = {'refundId': 'N/A', 'status': 'failed'}
        
        # Send notification (async)
        try:
            invoke_lambda_async(
                BOOKINGS_NOTIFY_FUNCTION_NAME,
                {
                    'customer_id': booking['customer'],
                    'price': 0,
                    'booking_reference': None
                }
            )
            notification = {'status': 'sent'}
        except Exception as e:
            print(f"Warning: Failed to send notification: {str(e)}")
            notification = {'status': 'failed'}
        
        return format_response(200, {
            'bookingId': booking_id,
            'status': 'CANCELLED',
            'refund': refund_result,
            'notification': notification
        })
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
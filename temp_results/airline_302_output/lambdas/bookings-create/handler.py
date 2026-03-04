import json
import os
import sys
import uuid
from datetime import datetime
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error,
    invoke_lambda,
    python_obj_to_dynamodb,
    dynamodb_to_python_obj,
    get_user_id_from_event
)
import boto3
from boto3.dynamodb.conditions import Attr


def lambda_handler(event, context):
    """
    Create a new booking (requires authentication)
    """
    try:
        # Get user_id from Cognito claims
        user_id = get_user_id_from_event(event)
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        
        if not body:
            return create_response(400, {'error': 'Request body is required'})
        
        # Set customerId from authenticated user
        body['customerId'] = user_id
        
        # Validate required fields
        required_fields = ['outboundFlightId', 'chargeId']
        for field in required_fields:
            if field not in body:
                return create_response(400, {'error': f'{field} is required'})
        
        # Variables to track rollback state
        booking_id = None
        payment_result = None
        flight_reserved = False
        
        try:
            # Step 1: Reserve Flight Seat
            try:
                reserve_flight_seat(body['outboundFlightId'])
                flight_reserved = True
            except ValueError as e:
                # No seat available or flight doesn't exist
                return create_response(400, {
                    'error': f'Flight reservation failed: {str(e)}',
                    'step': 'Reserve Flight'
                })
            
            # Step 2: Reserve Booking
            try:
                booking_id = reserve_booking(body)
            except ValueError as e:
                # Rollback: Release the flight seat
                if flight_reserved:
                    try:
                        release_flight_seat(body['outboundFlightId'])
                    except Exception as rollback_error:
                        print(f"Error during flight seat release rollback: {rollback_error}")
                
                return create_response(400, {
                    'error': f'Booking reservation failed: {str(e)}',
                    'step': 'Reserve Booking'
                })
            
            # Step 3: Collect Payment
            try:
                payment_result = collect_payment(body['chargeId'])
            except ValueError as e:
                # Rollback: Cancel booking and release flight seat
                if booking_id:
                    try:
                        cancel_booking(booking_id)
                    except Exception as rollback_error:
                        print(f"Error during booking cancellation rollback: {rollback_error}")
                
                if flight_reserved:
                    try:
                        release_flight_seat(body['outboundFlightId'])
                    except Exception as rollback_error:
                        print(f"Error during flight seat release rollback: {rollback_error}")
                
                return create_response(400, {
                    'error': f'Payment failed: {str(e)}',
                    'step': 'Collect Payment',
                    'bookingId': booking_id
                })
            
            # Step 4: Confirm Booking
            try:
                booking_reference = confirm_booking(booking_id)
            except Exception as e:
                # CRITICAL: Payment succeeded but confirmation failed
                # Rollback: Refund payment, cancel booking, release flight seat
                print(f"CRITICAL: Booking confirmation failed after payment: {str(e)}")
                
                # Refund the payment
                try:
                    refund_payment(body['chargeId'])
                except Exception as rollback_error:
                    print(f"CRITICAL: Payment refund failed during rollback: {rollback_error}")
                
                # Cancel the booking
                try:
                    cancel_booking(booking_id)
                except Exception as rollback_error:
                    print(f"Error during booking cancellation rollback: {rollback_error}")
                
                # Release the flight seat
                try:
                    release_flight_seat(body['outboundFlightId'])
                except Exception as rollback_error:
                    print(f"Error during flight seat release rollback: {rollback_error}")
                
                return create_response(500, {
                    'error': f'Booking confirmation failed: {str(e)}',
                    'step': 'Confirm Booking',
                    'bookingId': booking_id,
                    'message': 'Payment has been refunded'
                })
            
            # Step 5: Add Loyalty Points (optional - should not fail the booking)
            try:
                process_booking_loyalty_result = invoke_lambda(
                    os.environ.get('PROCESS_BOOKING_LOYALTY_FUNCTION_NAME'),
                    {
                        'customerId': body['customerId'],
                        'price': payment_result['price']
                    },
                    'Event'  # Async fire-and-forget
                )
            except Exception as e:
                # Log but don't fail the booking if loyalty points fail
                print(f"Warning: Failed to add loyalty points: {str(e)}")
            
            # Step 6: Send Notification (optional - should not fail the booking)
            try:
                notification_result = invoke_lambda(
                    os.environ.get('NOTIFY_BOOKING_FUNCTION_NAME'),
                    {
                        'customerId': body['customerId'],
                        'price': payment_result['price'],
                        'bookingReference': booking_reference
                    },
                    'Event'  # Async fire-and-forget
                )
            except Exception as e:
                # Log but don't fail the booking if notification fails
                print(f"Warning: Failed to send notification: {str(e)}")
                notification_result = {'status': 'failed', 'error': str(e)}
            
            # Success! Return the complete booking information
            return create_response(201, {
                'bookingId': booking_id,
                'bookingReference': booking_reference,
                'status': 'CONFIRMED',
                'payment': payment_result,
                'notification': notification_result if 'notification_result' in locals() else {'status': 'queued'}
            })
            
        except Exception as e:
            # Catch-all for any unexpected errors
            print(f"UNEXPECTED ERROR in booking workflow: {str(e)}")
            
            # Attempt to rollback everything
            if 'payment_result' in locals() and payment_result:
                try:
                    refund_payment(body['chargeId'])
                except Exception as rollback_error:
                    print(f"Error during payment refund: {rollback_error}")
            
            if booking_id:
                try:
                    cancel_booking(booking_id)
                except Exception as rollback_error:
                    print(f"Error during booking cancellation: {rollback_error}")
            
            if flight_reserved:
                try:
                    release_flight_seat(body['outboundFlightId'])
                except Exception as rollback_error:
                    print(f"Error during flight seat release: {rollback_error}")
            
            return create_response(500, {
                'error': f'Unexpected error during booking: {str(e)}',
                'message': 'The booking has been rolled back. Please try again.'
            })
        
    except Exception as e:
        return handle_error(e)

# Helper functions

def reserve_flight_seat(flight_id: str):
    """Reserve a seat on a flight"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('FLIGHT_TABLE')
    
    if not table_name:
        raise ValueError("FLIGHT_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        response = table.update_item(
            Key={'id': flight_id},
            UpdateExpression='SET seatCapacity = seatCapacity - :dec',
            ConditionExpression='seatCapacity > :zero AND attribute_exists(id)',
            ExpressionAttributeValues={
                ':dec': 1,
                ':zero': 0
            },
            ReturnValues='UPDATED_NEW'
        )
        return {'status': 'SUCCESS'}
        
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Flight {flight_id} is fully booked or does not exist")
    except Exception as e:
        raise ValueError(f"Failed to reserve seat: {str(e)}")


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


def reserve_booking(booking_data: dict) -> str:
    """Create a new booking with UNCONFIRMED status"""
    required_fields = ['outboundFlightId', 'customerId', 'chargeId']
    for field in required_fields:
        if field not in booking_data:
            raise ValueError(f"Invalid booking request: missing {field}")
    
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
    
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('BOOKING_TABLE')
    
    if not table_name:
        raise ValueError("BOOKING_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        booking_item = python_obj_to_dynamodb(booking)
        table.put_item(Item=booking_item)
        return booking_id
    except Exception as e:
        raise ValueError(f"Failed to create booking: {str(e)}")


def collect_payment(charge_id: str) -> dict:
    """Collect payment from a pre-authorized charge"""
    # This is a simplified version - in production, integrate with Stripe
    # For now, simulate successful payment
    if not charge_id:
        raise ValueError("Invalid Charge ID")
    
    # Simulate payment collection
    receipt_url = f"https://payment.example.com/receipts/{charge_id}"
    price = 150  # Simulated price
    
    return {
        'receiptUrl': receipt_url,
        'price': price
    }


def refund_payment(charge_id: str) -> dict:
    """Refund a payment"""
    # This is a simplified version - in production, integrate with Stripe
    if not charge_id:
        raise ValueError("Invalid Charge ID")
    
    # Simulate refund processing
    import secrets
    refund_id = secrets.token_urlsafe(16)
    
    return {
        'refundId': refund_id
    }


def confirm_booking(booking_id: str) -> str:
    """Confirm a booking and generate booking reference"""
    booking = get_booking(booking_id)
    if not booking:
        raise ValueError(f"Invalid booking ID: {booking_id}")
    
    # Generate a booking reference
    import secrets
    reference = secrets.token_urlsafe(4)
    
    # Update booking status to CONFIRMED
    update_booking_status(booking_id, 'CONFIRMED', reference)
    
    return reference


def cancel_booking(booking_id: str) -> bool:
    """Cancel a booking"""
    booking = get_booking(booking_id)
    if not booking:
        raise ValueError(f"Invalid booking ID: {booking_id}")
    
    # Update booking status to CANCELLED
    update_booking_status(booking_id, 'CANCELLED')
    
    return True


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


"""
Lambda handler for POST /bookings
"""
import json
import os
import boto3
from shared_utils import format_response, get_user_id, get_body, log_error


# Initialize AWS clients
lambda_client = boto3.client('lambda')

# Environment variables
FLIGHTS_RESERVE_SEAT_FUNCTION_NAME = os.environ['FLIGHTS_RESERVE_SEAT_FUNCTION_NAME']
FLIGHTS_RELEASE_SEAT_FUNCTION_NAME = os.environ['FLIGHTS_RELEASE_SEAT_FUNCTION_NAME']
BOOKINGS_RESERVE_FUNCTION_NAME = os.environ['BOOKINGS_RESERVE_FUNCTION_NAME']
BOOKINGS_CONFIRM_FUNCTION_NAME = os.environ['BOOKINGS_CONFIRM_FUNCTION_NAME']
BOOKINGS_CANCEL_FUNCTION_NAME = os.environ['BOOKINGS_CANCEL_FUNCTION_NAME']
BOOKINGS_NOTIFY_FUNCTION_NAME = os.environ['BOOKINGS_NOTIFY_FUNCTION_NAME']
PAYMENTS_COLLECT_FUNCTION_NAME = os.environ['PAYMENTS_COLLECT_FUNCTION_NAME']
PAYMENTS_REFUND_FUNCTION_NAME = os.environ['PAYMENTS_REFUND_FUNCTION_NAME']
LOYALTY_ADD_POINTS_FUNCTION_NAME = os.environ['LOYALTY_ADD_POINTS_FUNCTION_NAME']


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


def invoke_lambda_sync(function_name: str, payload: dict) -> dict:
    """
    Invoke Lambda function synchronously (wait for result)
    
    Args:
        function_name: Lambda function name
        payload: Payload to send
        
    Returns:
        Response from Lambda
    """
    try:
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )
        result = json.loads(response['Payload'].read())
        return result
    except Exception as e:
        raise ValueError(f"Failed to invoke {function_name}: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for POST /bookings
    """
    try:
        # Get user ID from Cognito
        user_id = get_user_id(event)
        
        # Parse request body
        data = get_body(event)
        
        if not data:
            return format_response(400, {'error': 'Request body is required'})
        
        # Set customerId from authenticated user
        data['customerId'] = user_id
        
        # Variables to track rollback state
        booking_id = None
        payment_result = None
        flight_reserved = False
        
        try:
            # Step 1: Reserve Flight Seat (synchronous)
            try:
                flight_result = invoke_lambda_sync(
                    FLIGHTS_RESERVE_SEAT_FUNCTION_NAME,
                    {'flight_id': data['outboundFlightId']}
                )
                flight_reserved = True
            except ValueError as e:
                # No seat available or flight doesn't exist
                # No rollback needed - nothing was changed
                return format_response(400, {
                    'error': f'Flight reservation failed: {str(e)}',
                    'step': 'Reserve Flight'
                })
            
            # Step 2: Reserve Booking (synchronous)
            try:
                booking_result = invoke_lambda_sync(
                    BOOKINGS_RESERVE_FUNCTION_NAME,
                    {'booking_data': data}
                )
                booking_id = booking_result.get('booking_id')
                if not booking_id:
                    raise ValueError("Booking reservation failed: no booking ID returned")
            except ValueError as e:
                # Rollback: Release the flight seat
                if flight_reserved:
                    try:
                        invoke_lambda_async(
                            FLIGHTS_RELEASE_SEAT_FUNCTION_NAME,
                            {'flight_id': data['outboundFlightId']}
                        )
                    except Exception as rollback_error:
                        print(f"Error during flight seat release rollback: {rollback_error}")
                
                return format_response(400, {
                    'error': f'Booking reservation failed: {str(e)}',
                    'step': 'Reserve Booking'
                })
            
            # Step 3: Collect Payment (synchronous)
            try:
                payment_result = invoke_lambda_sync(
                    PAYMENTS_COLLECT_FUNCTION_NAME,
                    {'chargeId': data['chargeId']}
                )
            except ValueError as e:
                # Rollback: Cancel booking and release flight seat
                if booking_id:
                    try:
                        invoke_lambda_async(
                            BOOKINGS_CANCEL_FUNCTION_NAME,
                            {'booking_id': booking_id}
                        )
                    except Exception as rollback_error:
                        print(f"Error during booking cancellation rollback: {rollback_error}")
                
                if flight_reserved:
                    try:
                        invoke_lambda_async(
                            FLIGHTS_RELEASE_SEAT_FUNCTION_NAME,
                            {'flight_id': data['outboundFlightId']}
                        )
                    except Exception as rollback_error:
                        print(f"Error during flight seat release rollback: {rollback_error}")
                
                return format_response(400, {
                    'error': f'Payment failed: {str(e)}',
                    'step': 'Collect Payment',
                    'bookingId': booking_id
                })
            
            # Step 4: Confirm Booking (synchronous)
            try:
                confirm_result = invoke_lambda_sync(
                    BOOKINGS_CONFIRM_FUNCTION_NAME,
                    {'booking_id': booking_id}
                )
                booking_reference = confirm_result.get('booking_reference')
            except Exception as e:
                # CRITICAL: Payment succeeded but confirmation failed
                # Rollback: Refund payment, cancel booking, release flight seat
                print(f"CRITICAL: Booking confirmation failed after payment: {str(e)}")
                
                # Refund the payment
                try:
                    invoke_lambda_async(
                        PAYMENTS_REFUND_FUNCTION_NAME,
                        {'chargeId': data['chargeId']}
                    )
                except Exception as rollback_error:
                    print(f"CRITICAL: Payment refund failed during rollback: {rollback_error}")
                
                # Cancel the booking
                if booking_id:
                    try:
                        invoke_lambda_async(
                            BOOKINGS_CANCEL_FUNCTION_NAME,
                            {'booking_id': booking_id}
                        )
                    except Exception as rollback_error:
                        print(f"Error during booking cancellation rollback: {rollback_error}")
                
                # Release the flight seat
                if flight_reserved:
                    try:
                        invoke_lambda_async(
                            FLIGHTS_RELEASE_SEAT_FUNCTION_NAME,
                            {'flight_id': data['outboundFlightId']}
                        )
                    except Exception as rollback_error:
                        print(f"Error during flight seat release rollback: {rollback_error}")
                
                return format_response(500, {
                    'error': f'Booking confirmation failed: {str(e)}',
                    'step': 'Confirm Booking',
                    'bookingId': booking_id,
                    'message': 'Payment has been refunded'
                })
            
            # Step 5: Add Loyalty Points (async - should not fail the booking)
            try:
                invoke_lambda_async(
                    LOYALTY_ADD_POINTS_FUNCTION_NAME,
                    {
                        'customer_id': data['customerId'],
                        'points': payment_result.get('price', 0)
                    }
                )
            except Exception as e:
                # Log but don't fail the booking if loyalty points fail
                print(f"Warning: Failed to add loyalty points: {str(e)}")
            
            # Step 6: Send Notification (async - should not fail the booking)
            try:
                invoke_lambda_async(
                    BOOKINGS_NOTIFY_FUNCTION_NAME,
                    {
                        'customer_id': data['customerId'],
                        'price': payment_result.get('price', 0),
                        'booking_reference': booking_reference
                    }
                )
            except Exception as e:
                # Log but don't fail the booking if notification fails
                print(f"Warning: Failed to send notification: {str(e)}")
            
            # Success! Return the complete booking information
            return format_response(201, {
                'bookingId': booking_id,
                'bookingReference': booking_reference,
                'status': 'CONFIRMED',
                'payment': payment_result
            })
            
        except Exception as e:
            # Catch-all for any unexpected errors
            # Attempt to rollback everything if we have the necessary information
            print(f"UNEXPECTED ERROR in booking workflow: {str(e)}")
            
            if payment_result:
                # Payment was collected, need to refund
                try:
                    invoke_lambda_async(
                        PAYMENTS_REFUND_FUNCTION_NAME,
                        {'chargeId': data['chargeId']}
                    )
                except Exception as rollback_error:
                    print(f"Error during payment refund: {rollback_error}")
            
            if booking_id:
                # Booking was created, need to cancel
                try:
                    invoke_lambda_async(
                        BOOKINGS_CANCEL_FUNCTION_NAME,
                        {'booking_id': booking_id}
                    )
                except Exception as rollback_error:
                    print(f"Error during booking cancellation: {rollback_error}")
            
            if flight_reserved:
                # Flight seat was reserved, need to release
                try:
                    invoke_lambda_async(
                        FLIGHTS_RELEASE_SEAT_FUNCTION_NAME,
                        {'flight_id': data['outboundFlightId']}
                    )
                except Exception as rollback_error:
                    print(f"Error during flight seat release: {rollback_error}")
            
            return format_response(500, {
                'error': f'Unexpected error during booking: {str(e)}',
                'message': 'The booking has been rolled back. Please try again.'
            })
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
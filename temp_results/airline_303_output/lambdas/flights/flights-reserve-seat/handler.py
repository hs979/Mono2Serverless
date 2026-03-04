
"""
Lambda handler for POST /flights/{flight_id}/reserve
"""
import json
import os
import boto3
from shared_utils import format_response, get_path_parameter, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
FLIGHT_TABLE = os.environ['FLIGHT_TABLE']
flight_table = dynamodb.Table(FLIGHT_TABLE)


def reserve_flight_seat(flight_id: str):
    """
    Reserve a seat on a flight (decrease seat capacity)
    
    Args:
        flight_id: Flight identifier
        
    Returns:
        Success status
        
    Raises:
        ValueError: If flight is fully booked or doesn't exist
    """
    try:
        # Use atomic counter decrement with condition
        response = flight_table.update_item(
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
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Flight {flight_id} is fully booked or does not exist")
    except Exception as e:
        raise ValueError(f"Failed to reserve seat: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for POST /flights/{flight_id}/reserve
    """
    try:
        # Extract path parameter
        flight_id = get_path_parameter(event, 'flight_id')
        
        # Reserve seat
        result = reserve_flight_seat(flight_id)
        
        return format_response(200, result)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
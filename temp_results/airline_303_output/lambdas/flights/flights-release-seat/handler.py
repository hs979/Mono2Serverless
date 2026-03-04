
"""
Lambda handler for POST /flights/{flight_id}/release
"""
import json
import os
import boto3
from decimal import Decimal
from shared_utils import format_response, get_path_parameter, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
FLIGHT_TABLE = os.environ['FLIGHT_TABLE']
flight_table = dynamodb.Table(FLIGHT_TABLE)


def _dynamodb_to_python_obj(obj):
    """Convert DynamoDB objects to Python format (Decimal to int/float)"""
    if isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: _dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_dynamodb_to_python_obj(item) for item in obj]
    return obj


def get_flight(flight_id: str):
    """
    Get flight details by ID
    """
    try:
        response = flight_table.get_item(Key={'id': flight_id})
        if 'Item' in response:
            return _dynamodb_to_python_obj(response['Item'])
        return None
    except Exception as e:
        raise ValueError(f"Error getting flight {flight_id}: {str(e)}")


def release_flight_seat(flight_id: str):
    """
    Release a seat on a flight (increase seat capacity)
    
    Args:
        flight_id: Flight identifier
        
    Returns:
        Success status
        
    Raises:
        ValueError: If flight doesn't exist or at maximum capacity
    """
    try:
        # First get the flight to check maximum capacity
        flight = get_flight(flight_id)
        if not flight:
            raise ValueError(f"Flight {flight_id} does not exist")
        
        # Use atomic counter increment with condition
        response = flight_table.update_item(
            Key={'id': flight_id},
            UpdateExpression='SET seatCapacity = seatCapacity + :inc',
            ConditionExpression='seatCapacity < :max',
            ExpressionAttributeValues={
                ':inc': 1,
                ':max': flight['maximumSeating']
            },
            ReturnValues='UPDATED_NEW'
        )
        return {'status': 'SUCCESS'}
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Cannot release seat, already at maximum capacity")
    except Exception as e:
        raise ValueError(f"Failed to release seat: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for POST /flights/{flight_id}/release
    """
    try:
        # Extract path parameter
        flight_id = get_path_parameter(event, 'flight_id')
        
        # Release seat
        result = release_flight_seat(flight_id)
        
        return format_response(200, result)
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
import json
import os
import sys
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error,
    dynamodb_to_python_obj
)
import boto3


def lambda_handler(event, context):
    """
    Reserve a seat on a flight
    """
    try:
        # Extract flight_id from path parameters
        flight_id = event.get('pathParameters', {}).get('flight_id')
        
        if not flight_id:
            return create_response(400, {'error': 'flight_id is required in path'})
        
        # Reserve seat using DynamoDB
        result = reserve_flight_seat(flight_id)
        
        return create_response(200, result)
        
    except Exception as e:
        return handle_error(e)


def reserve_flight_seat(flight_id: str):
    """
    Reserve a seat on a flight (decrease seat capacity)
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('FLIGHT_TABLE')
    
    if not table_name:
        raise ValueError("FLIGHT_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        # Use atomic counter decrement with condition
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

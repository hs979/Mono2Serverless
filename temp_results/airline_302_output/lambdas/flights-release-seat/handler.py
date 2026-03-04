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
    Release a seat on a flight
    """
    try:
        # Extract flight_id from path parameters
        flight_id = event.get('pathParameters', {}).get('flight_id')
        
        if not flight_id:
            return create_response(400, {'error': 'flight_id is required in path'})
        
        # Release seat using DynamoDB
        result = release_flight_seat(flight_id)
        
        return create_response(200, result)
        
    except Exception as e:
        return handle_error(e)


def release_flight_seat(flight_id: str):
    """
    Release a seat on a flight (increase seat capacity)
    """
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
        
        # Use atomic counter increment with condition
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

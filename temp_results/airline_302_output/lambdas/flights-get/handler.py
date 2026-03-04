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
    Get flight details by ID
    """
    try:
        # Extract flight_id from path parameters
        flight_id = event.get('pathParameters', {}).get('flight_id')
        
        if not flight_id:
            return create_response(400, {'error': 'flight_id is required in path'})
        
        # Get flight using DynamoDB
        flight = get_flight(flight_id)
        
        if not flight:
            return create_response(404, {'error': f'Flight with ID {flight_id} not found'})
        
        return create_response(200, flight)
        
    except Exception as e:
        return handle_error(e)


def get_flight(flight_id: str):
    """
    Get flight details by ID
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('FLIGHT_TABLE')
    
    if not table_name:
        raise ValueError("FLIGHT_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        response = table.get_item(Key={'id': flight_id})
        if 'Item' in response:
            return dynamodb_to_python_obj(response['Item'])
        return None
    except Exception as e:
        print(f"Error getting flight {flight_id}: {str(e)}")
        return None

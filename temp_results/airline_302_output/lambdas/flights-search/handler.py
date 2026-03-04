import json
import os
import sys
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error,
    python_obj_to_dynamodb,
    dynamodb_to_python_obj
)
import boto3
from boto3.dynamodb.conditions import Attr


def lambda_handler(event, context):
    """
    Search for flights
    Query params: departureCode, arrivalCode, departureDate
    """
    try:
        # Extract query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        departure_code = query_params.get('departureCode')
        arrival_code = query_params.get('arrivalCode')
        departure_date = query_params.get('departureDate')
        
        if not all([departure_code, arrival_code, departure_date]):
            return create_response(400, {'error': 'Missing required parameters'})
        
        # Search flights using DynamoDB
        flights = search_flights(departure_code, arrival_code, departure_date)
        
        return create_response(200, {'flights': flights})
        
    except Exception as e:
        return handle_error(e)


def search_flights(departure_code: str, arrival_code: str, departure_date: str):
    """
    Search for flights by schedule
    """
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('FLIGHT_TABLE')
    
    if not table_name:
        raise ValueError("FLIGHT_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        # Use scan with filter expression
        response = table.scan(
            FilterExpression=Attr('departureAirportCode').eq(departure_code) &
                            Attr('arrivalAirportCode').eq(arrival_code) &
                            Attr('departureDate').eq(departure_date)
        )
        
        items = response.get('Items', [])
        return [dynamodb_to_python_obj(item) for item in items]
        
    except Exception as e:
        print(f"Error searching flights: {str(e)}")
        return []

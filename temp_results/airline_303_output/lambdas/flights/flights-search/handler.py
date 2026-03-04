
"""
Lambda handler for GET /flights/search
"""
import json
import os
import boto3
from boto3.dynamodb.conditions import Attr
from decimal import Decimal
from shared_utils import format_response, get_query_parameter, log_error


# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
FLIGHT_TABLE = os.environ['FLIGHT_TABLE']
flight_table = dynamodb.Table(FLIGHT_TABLE)


def _python_obj_to_dynamodb(obj):
    """Convert Python objects to DynamoDB compatible format (float to Decimal)"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: _python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_python_obj_to_dynamodb(item) for item in obj]
    return obj


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


def search_flights(departure_code: str, arrival_code: str, departure_date: str):
    """
    Search for flights by schedule
    
    Args:
        departure_code: Departure airport code
        arrival_code: Arrival airport code
        departure_date: Departure date (YYYY-MM-DD)
        
    Returns:
        List of matching flights
    """
    try:
        # Use scan with filter expression
        response = flight_table.scan(
            FilterExpression=Attr('departureAirportCode').eq(departure_code) &
                            Attr('arrivalAirportCode').eq(arrival_code) &
                            Attr('departureDate').eq(departure_date)
        )
        
        items = response.get('Items', [])
        flights = [_dynamodb_to_python_obj(item) for item in items]
        return flights
    except Exception as e:
        raise ValueError(f"Error searching flights: {str(e)}")


def lambda_handler(event, context):
    """
    Handler for GET /flights/search
    Query params: departureCode, arrivalCode, departureDate
    """
    try:
        # Extract query parameters
        departure_code = get_query_parameter(event, 'departureCode')
        arrival_code = get_query_parameter(event, 'arrivalCode')
        departure_date = get_query_parameter(event, 'departureDate')
        
        # Validate required parameters
        if not all([departure_code, arrival_code, departure_date]):
            return format_response(400, {
                'error': 'Missing required parameters',
                'required': ['departureCode', 'arrivalCode', 'departureDate']
            })
        
        # Search flights
        flights = search_flights(departure_code, arrival_code, departure_date)
        
        return format_response(200, {'flights': flights})
        
    except ValueError as e:
        log_error(e, context)
        return format_response(400, {'error': str(e)})
    except Exception as e:
        log_error(e, context)
        return format_response(500, {'error': 'Internal server error'})
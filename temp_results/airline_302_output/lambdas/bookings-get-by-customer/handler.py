import json
import os
import sys
sys.path.append('/opt/python')

from internal_client import (
    create_response,
    handle_error,
    dynamodb_to_python_obj,
    get_user_id_from_event
)
import boto3
from boto3.dynamodb.conditions import Attr


def lambda_handler(event, context):
    """
    Get all bookings for a customer (requires authentication, owner or admin only)
    """
    try:
        # Get user_id from Cognito claims
        user_id = get_user_id_from_event(event)
        
        # Extract customer_id from path parameters
        customer_id = event.get('pathParameters', {}).get('customer_id')
        
        if not customer_id:
            return create_response(400, {'error': 'customer_id is required in path'})
        
        # Check authorization: user must be admin or the customer
        if user_id != customer_id:
            # In production, check if user is admin via UserProfiles table
            return create_response(403, {
                'error': 'Access denied. You can only access your own bookings.'
            })
        
        # Get status filter from query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        status = query_params.get('status')
        
        # Get bookings
        bookings = get_bookings_by_customer(customer_id, status)
        
        return create_response(200, {'bookings': bookings})
        
    except Exception as e:
        return handle_error(e)


def get_bookings_by_customer(customer_id: str, status: str = None):
    """Get bookings for a customer, optionally filtered by status"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('BOOKING_TABLE')
    
    if not table_name:
        raise ValueError("BOOKING_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        # Use scan with filter
        filter_expr = Attr('customer').eq(customer_id)
        if status:
            filter_expr = filter_expr & Attr('status').eq(status)
        
        response = table.scan(FilterExpression=filter_expr)
        
        items = response.get('Items', [])
        return [dynamodb_to_python_obj(item) for item in items]
    except Exception as e:
        print(f"Error getting bookings for customer {customer_id}: {str(e)}")
        return []

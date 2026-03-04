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
    Get customer loyalty information (requires authentication, owner or admin only)
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
                'error': 'Access denied. You can only access your own loyalty information.'
            })
        
        # Get loyalty information
        loyalty = get_customer_loyalty(customer_id)
        
        return create_response(200, loyalty)
        
    except Exception as e:
        return handle_error(e)


def get_customer_loyalty(customer_id: str) -> dict:
    """
    Get loyalty information for a customer
    """
    total_points = get_loyalty_points(customer_id)
    level = get_loyalty_level(total_points)
    remaining_points = get_remaining_points_to_next_tier(total_points, level)
    
    return {
        'points': total_points,
        'level': level,
        'remainingPoints': remaining_points
    }

def get_loyalty_points(customer_id: str) -> int:
    """Get total active loyalty points for a customer"""
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ.get('LOYALTY_TABLE')
    
    if not table_name:
        raise ValueError("LOYALTY_TABLE environment variable not set")
        
    table = dynamodb.Table(table_name)
    
    try:
        # Use scan with filter
        response = table.scan(
            FilterExpression=Attr('customerId').eq(customer_id) &
                            Attr('flag').eq('active')
        )
        
        items = response.get('Items', [])
        total = 0
        for item in items:
            points = item.get('points', 0)
            if isinstance(points, (int, float)):
                total += int(points)
            else:
                total += int(points)
        
        return total
    except Exception as e:
        print(f"Error getting loyalty points for {customer_id}: {str(e)}")
        return 0

def get_loyalty_level(points: int) -> str:
    """Calculate loyalty level based on points"""
    if points >= 100000:
        return 'gold'
    elif points >= 50000:
        return 'silver'
    else:
        return 'bronze'

def get_remaining_points_to_next_tier(points: int, level: str) -> int:
    """Calculate points needed for next tier"""
    if level == 'bronze':
        return 50000 - points
    elif level == 'silver':
        return 100000 - points
    else:
        return 0

import json
import os
import boto3
import uuid
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from datetime import datetime

# Initialize DynamoDB client
def get_table():
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    return dynamodb.Table(table_name)

def _dynamodb_to_python_obj(obj):
    """
    Convert DynamoDB objects to standard Python objects.
    Mainly handles Decimal -> int/float conversion.
    """
    if isinstance(obj, dict):
        return {k: _dynamodb_to_python_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_dynamodb_to_python_obj(item) for item in obj]
    elif isinstance(obj, Decimal):
        # If it's an integer, return int; otherwise return float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj

def get_cart_items(pk):
    """
    Get all items in a cart.
    
    Args:
        pk: Partition key (user#xxx or cart#xxx)
    
    Returns:
        List of items
    """
    table = get_table()
    
    try:
        # Query cart items: only items with sk beginning with product#
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        items = []
        current_time = datetime.now()
        
        for item in response['Items']:
            # Filter out zero-quantity and expired items
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                continue
            
            # Check expiration
            expiration_time = item.get('expirationTime')
            if expiration_time:
                # DynamoDB TTL is a Unix timestamp (seconds)
                # Convert Decimal to int if needed
                if isinstance(expiration_time, Decimal):
                    expiration_time = int(expiration_time)
                exp_datetime = datetime.fromtimestamp(expiration_time)
                if exp_datetime < current_time:
                    continue
            
            # Parse product_detail
            product_detail = item.get('product_detail')
            if product_detail and isinstance(product_detail, str):
                product_detail = json.loads(product_detail)
            
            items.append({
                'sk': item['sk'],
                'quantity': int(quantity) if isinstance(quantity, Decimal) else quantity,
                'productDetail': _dynamodb_to_python_obj(product_detail)
            })
        
        return items
    except Exception as e:
        print(f"Failed to get cart: {e}")
        return []

def lambda_handler(event, context):
    """
    Lambda handler for GET /cart endpoint.
    Returns the current user's cart contents.
    """
    try:
        # Determine user identifier
        # Check if user is authenticated via Cognito
        pk = None
        is_authenticated = False
        cart_id = None
        
        # Check for Cognito user ID in the event (from API Gateway Authorizer)
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer']['claims']
            user_id = claims['sub']  # Cognito UUID
            pk = f"user#{user_id}"
            is_authenticated = True
        else:
            # Anonymous user: get cart ID from header or generate
            headers = event.get('headers', {})
            cart_id = headers.get('x-cart-id')
            if not cart_id:
                # Generate a new cart ID
                cart_id = str(uuid.uuid4())
            pk = f"cart#{cart_id}"
        
        # Get cart items
        product_list = get_cart_items(pk)
        
        # Normalize response data
        for product in product_list:
            if 'sk' in product:
                product['sk'] = product['sk'].replace('product#', '')
        
        response_body = {
            'products': product_list
        }
        
        # Set headers including cart ID cookie for anonymous users
        headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True
        }
        
        # If anonymous user, include cart ID in response header
        if not is_authenticated:
            headers['X-Cart-ID'] = cart_id
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': f'Internal server error: {str(e)}'})
        }
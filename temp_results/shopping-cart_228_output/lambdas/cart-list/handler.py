import os
import json
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

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
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
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
        # Determine if user is authenticated via Cognito
        user_id = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')  # Cognito user UUID
        
        # Get cart ID from headers or generate new one
        cart_id = None
        headers = event.get('headers', {})
        if 'x-cart-id' in headers:
            cart_id = headers['x-cart-id']
        
        generated = False
        if not cart_id:
            cart_id = str(uuid.uuid4())
            generated = True
        
        # Determine partition key
        if user_id:
            pk = f"user#{user_id}"
            is_authenticated = True
        else:
            pk = f"cart#{cart_id}"
            is_authenticated = False
        
        # If cart_id was just generated for an anonymous user, skip DB query
        if generated and not is_authenticated:
            product_list = []
        else:
            product_list = get_cart_items(pk)
        
        # Normalize response data
        for product in product_list:
            if 'sk' in product:
                product['sk'] = product['sk'].replace('product#', '')
        
        response_body = {
            'products': product_list
        }
        
        # Return response with cart ID in headers for anonymous users
        response_headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
        
        if not user_id:
            # For anonymous users, return cart ID in header
            response_headers['X-Cart-ID'] = cart_id
        
        return {
            'statusCode': 200,
            'headers': response_headers,
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error in cart-list lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }

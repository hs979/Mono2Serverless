import json
import os
import boto3
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
    """
    table = get_table()
    
    try:
        # Query cart items: only items with sk beginning with product#
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        items = []
        
        for item in response['Items']:
            # Filter out zero-quantity items
            quantity = item.get('quantity', 0)
            if quantity <= 0:
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

def update_product_total_quantity(product_id, quantity_change):
    """
    Update product total quantity (incremental update).
    """
    table = get_table()
    pk = f'PRODUCT#{product_id}'
    sk = 'TOTAL'
    
    try:
        # Use atomic ADD
        response = table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression='ADD total_quantity :change SET updated_at = :now',
            ExpressionAttributeValues={
                ':change': quantity_change,
                ':now': datetime.now().isoformat()
            },
            ReturnValues='ALL_NEW'
        )
        
        # If the total becomes < 0, reset to 0
        new_total = response['Attributes'].get('total_quantity', 0)
        if new_total < 0:
            table.update_item(
                Key={'pk': pk, 'sk': sk},
                UpdateExpression='SET total_quantity = :zero',
                ExpressionAttributeValues={':zero': 0}
            )
    except Exception as e:
        # If the record doesn't exist, create it
        initial_total = max(0, quantity_change)
        table.put_item(
            Item={
                'pk': pk,
                'sk': sk,
                'total_quantity': initial_total,
                'updated_at': datetime.now().isoformat()
            }
        )

def delete_cart_items(pk):
    """
    Delete all items for a given user/cart.
    """
    table = get_table()
    
    try:
        # Query all cart items first
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        # Batch delete
        with table.batch_writer() as batch:
            for item in response['Items']:
                batch.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
    except Exception as e:
        print(f"Failed to delete cart items: {e}")
        raise

def lambda_handler(event, context):
    """
    Lambda handler for POST /cart/checkout endpoint.
    Checkout the cart (clears the cart).
    Requires authentication via Cognito.
    """
    try:
        # Check for Cognito user ID in the event (from API Gateway Authorizer)
        if 'requestContext' not in event or 'authorizer' not in event['requestContext']:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({'message': 'Authentication required'})
            }
        
        claims = event['requestContext']['authorizer']['claims']
        user_id = claims['sub']  # Cognito UUID
        user_pk = f"user#{user_id}"
        
        # Fetch cart items
        cart_items = get_cart_items(user_pk)
        
        # Before clearing, update product aggregate counters (decrease quantities)
        for item in cart_items:
            product_id = item['sk'].replace('product#', '')
            quantity = -item['quantity']  # Negative means decrement
            update_product_total_quantity(product_id, quantity)
        
        # Delete cart items
        delete_cart_items(user_pk)
        
        response_body = {
            'products': cart_items,
            'message': 'Checkout successful'
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
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
            'body': json.dumps({'message': f'Failed to checkout: {str(e)}'})
        }
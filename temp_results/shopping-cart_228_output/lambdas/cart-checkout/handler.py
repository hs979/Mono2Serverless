import os
import json
import boto3
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Import internal client from layer
try:
    from internal_client import invoke_lambda
except ImportError:
    # Fallback for local testing
    def invoke_lambda(function_name, payload, invocation_type="RequestResponse"):
        print(f"Mock invoke_lambda: {function_name}, payload: {payload}")
        return None

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
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        
        items = []
        current_time = datetime.now()
        
        for item in response['Items']:
            quantity = item.get('quantity', 0)
            if quantity <= 0:
                continue
            
            expiration_time = item.get('expirationTime')
            if expiration_time:
                if isinstance(expiration_time, Decimal):
                    expiration_time = int(expiration_time)
                exp_datetime = datetime.fromtimestamp(expiration_time)
                if exp_datetime < current_time:
                    continue
            
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
    Lambda handler for POST /cart/checkout endpoint.
    Checkout the cart (clears the cart).
    """
    try:
        # User must be authenticated via Cognito
        user_id = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')
        
        if not user_id:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Authentication required'})
            }
        
        user_pk = f"user#{user_id}"
        
        # Fetch cart items
        cart_items = get_cart_items(user_pk)
        
        # Before clearing, update product aggregate counters (decrease quantities)
        for item in cart_items:
            product_id = item['sk'].replace('product#', '')
            quantity = -item['quantity']  # Negative means decrement
            
            try:
                # Call internal product-aggregate-update function
                function_name = os.environ.get('PRODUCT_AGGREGATE_UPDATE_FUNCTION_NAME')
                if function_name:
                    invoke_lambda(
                        function_name=function_name,
                        payload={
                            'product_id': product_id,
                            'quantity_change': quantity
                        },
                        invocation_type="Event"
                    )
            except Exception as e:
                print(f"Failed to update product aggregate for {product_id}: {e}")
        
        # Delete cart items by calling internal cart-delete-items function
        try:
            delete_function_name = os.environ.get('CART_DELETE_FUNCTION_NAME')
            if delete_function_name:
                invoke_lambda(
                    function_name=delete_function_name,
                    payload={
                        'pk': user_pk
                    },
                    invocation_type="Event"
                )
        except Exception as e:
            print(f"Failed to invoke cart-delete-items: {e}")
            # Continue execution
        
        response_body = {
            'products': cart_items,
            'message': 'Checkout successful'
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error in cart-checkout lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }

import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

# Import internal client from layer
try:
    from internal_client import invoke_lambda
except ImportError:
    # Fallback for local testing
    def invoke_lambda(function_name, payload, invocation_type="RequestResponse"):
        print(f"Mock invoke_lambda: {function_name}, payload: {payload}")
        return None

def _python_obj_to_dynamodb(obj):
    """
    Convert Python objects to DynamoDB-compatible structures.
    Mainly handles float -> Decimal conversion.
    """
    if isinstance(obj, dict):
        return {k: _python_obj_to_dynamodb(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_python_obj_to_dynamodb(item) for item in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj

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

def get_product_by_id(product_id):
    """
    Get product detail by product ID from DynamoDB.

    Args:
        product_id: Product ID

    Returns:
        Product dict or None
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    try:
        response = table.get_item(
            Key={
                'pk': f'PRODUCT#{product_id}',
                'sk': 'DETAIL'
            }
        )
        item = response.get('Item')
        if not item:
            return None

        product = _dynamodb_to_python_obj(item)
        product.pop('pk', None)
        product.pop('sk', None)
        return product
    except Exception as e:
        print(f"Failed to get product {product_id}: {e}")
        return None

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
            KeyConditionExpression=boto3.dynamodb.conditions.Key('pk').eq(pk) & boto3.dynamodb.conditions.Key('sk').begins_with('product#')
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

def update_cart_item_quantity(pk, product_id, quantity, product_detail, expiration_time):
    """
    Update cart item quantity (idempotent, set to an absolute value).
    
    Args:
        pk: Partition key (user#xxx or cart#xxx)
        product_id: Product ID
        quantity: Quantity
        product_detail: Product detail dict
        expiration_time: Expiration time (datetime)
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    sk = f"product#{product_id}"
    
    # Convert expiration time to Unix timestamp
    ttl = int(expiration_time.timestamp()) if expiration_time else None
    
    # Serialize product_detail as JSON string
    product_detail_json = json.dumps(_python_obj_to_dynamodb(product_detail))
    
    try:
        if quantity <= 0:
            # Quantity is 0 or negative: delete the item
            table.delete_item(Key={'pk': pk, 'sk': sk})
        else:
            # Set absolute quantity
            table.put_item(
                Item={
                    'pk': pk,
                    'sk': sk,
                    'quantity': quantity,
                    'product_detail': product_detail_json,
                    'expirationTime': ttl,
                    'updated_at': datetime.now().isoformat()
                }
            )
    except Exception as e:
        print(f"Failed to update cart item: {e}")
        raise

def lambda_handler(event, context):
    """
    Lambda handler for PUT /cart/{product_id} endpoint.
    Updates quantity for a product in the cart.
    """
    try:
        # Extract product_id from path parameters
        product_id = event.get('pathParameters', {}).get('product_id')
        
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        quantity = int(body.get('quantity', 0))
        
        if not product_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Product ID required'})
            }
        
        if quantity < 0:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'productId': product_id,
                    'message': 'Quantity must not be lower than 0'
                })
            }
        
        # Validate that the product exists
        product = get_product_by_id(product_id)
        if not product:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Product not found'})
            }
        
        # Determine if user is authenticated via Cognito
        user_id = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')  # Cognito user UUID
        
        # Get cart ID from headers
        cart_id = None
        headers = event.get('headers', {})
        if 'x-cart-id' in headers:
            cart_id = headers['x-cart-id']
        
        if not cart_id and not user_id:
            cart_id = str(uuid.uuid4())
        
        # Determine partition key
        if user_id:
            pk = f"user#{user_id}"
            is_authenticated = True
        else:
            pk = f"cart#{cart_id}"
            is_authenticated = False
        
        # Set expiration time
        if is_authenticated:
            ttl = datetime.now() + timedelta(days=7)
        else:
            ttl = datetime.now() + timedelta(days=1)
        
        # Get old quantity to compute delta
        old_quantity = 0
        items = get_cart_items(pk)
        for item in items:
            if item['sk'] == f"product#{product_id}":
                old_quantity = item['quantity']
                break
        
        # Update cart item
        update_cart_item_quantity(pk, product_id, quantity, product, ttl)
        
        # Update product aggregate counters (delta)
        quantity_diff = quantity - old_quantity
        if quantity_diff != 0:
            try:
                # Get function name from environment variable
                function_name = os.environ.get('PRODUCT_AGGREGATE_UPDATE_FUNCTION_NAME')
                if function_name:
                    invoke_lambda(
                        function_name=function_name,
                        payload={
                            'product_id': product_id,
                            'quantity_change': quantity_diff
                        },
                        invocation_type="Event"  # Async fire-and-forget
                    )
            except Exception as e:
                print(f"Failed to invoke product-aggregate-update: {e}")
                # Continue execution - this is a non-critical operation
        
        response_body = {
            'productId': product_id,
            'quantity': quantity,
            'message': 'cart updated'
        }
        
        # Return response with cart ID in headers for anonymous users
        response_headers = {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
        
        if not user_id and cart_id:
            # For anonymous users, return cart ID in header
            response_headers['X-Cart-ID'] = cart_id
        
        return {
            'statusCode': 200,
            'headers': response_headers,
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error in cart-update lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }

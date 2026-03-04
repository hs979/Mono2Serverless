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

def add_cart_item(pk, product_id, quantity, product_detail, expiration_time):
    """
    Add or update a cart item (increment quantity).
    
    Args:
        pk: Partition key (user#xxx or cart#xxx)
        product_id: Product ID
        quantity: Quantity change (can be negative)
        product_detail: Product detail dict
        expiration_time: Expiration time (datetime)
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    sk = f"product#{product_id}"
    
    # Convert expiration time to Unix timestamp (DynamoDB TTL format)
    ttl = int(expiration_time.timestamp()) if expiration_time else None
    
    # Serialize product_detail as JSON string
    product_detail_json = json.dumps(_python_obj_to_dynamodb(product_detail))
    
    try:
        # Use UpdateItem for atomic increment
        response = table.update_item(
            Key={'pk': pk, 'sk': sk},
            UpdateExpression='ADD quantity :qty SET product_detail = :detail, expirationTime = :ttl, updated_at = :now',
            ExpressionAttributeValues={
                ':qty': quantity,
                ':detail': product_detail_json,
                ':ttl': ttl,
                ':now': datetime.now().isoformat()
            },
            ReturnValues='ALL_NEW'
        )
        
        # If the quantity becomes <= 0 after update, delete the item
        new_quantity = response['Attributes'].get('quantity', 0)
        if new_quantity <= 0:
            table.delete_item(Key={'pk': pk, 'sk': sk})
            
    except Exception as e:
        print(f"Failed to add cart item: {e}")
        raise

def lambda_handler(event, context):
    """
    Lambda handler for POST /cart endpoint.
    Adds a product to the cart.
    """
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        product_id = body.get('productId')
        quantity = body.get('quantity', 1)
        
        if not product_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Product ID required'})
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
        
        # Get cart ID from headers or generate new one
        cart_id = None
        headers = event.get('headers', {})
        if 'x-cart-id' in headers:
            cart_id = headers['x-cart-id']
        
        if not cart_id:
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
        
        # Add or update cart item
        add_cart_item(pk, product_id, quantity, product, ttl)
        
        # Call internal product-aggregate-update function asynchronously
        try:
            # Get function name from environment variable
            function_name = os.environ.get('PRODUCT_AGGREGATE_UPDATE_FUNCTION_NAME')
            if function_name:
                invoke_lambda(
                    function_name=function_name,
                    payload={
                        'product_id': product_id,
                        'quantity_change': quantity
                    },
                    invocation_type="Event"  # Async fire-and-forget
                )
        except Exception as e:
            print(f"Failed to invoke product-aggregate-update: {e}")
            # Continue execution - this is a non-critical operation
        
        response_body = {
            'productId': product_id,
            'message': 'product added to cart'
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
        print(f"Error in cart-add lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }

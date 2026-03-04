import json
import os
import boto3
import uuid
from decimal import Decimal
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta

# Initialize DynamoDB client
def get_table():
    dynamodb = boto3.resource('dynamodb')
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    return dynamodb.Table(table_name)

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
    """
    table = get_table()
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
    """
    table = get_table()
    try:
        response = table.query(
            KeyConditionExpression=Key('pk').eq(pk) & Key('sk').begins_with('product#')
        )
        return response['Items']
    except Exception as e:
        print(f"Failed to get cart: {e}")
        return []

def update_cart_item_quantity(pk, product_id, quantity, product_detail, expiration_time):
    """
    Update cart item quantity (idempotent, set to an absolute value).
    """
    table = get_table()
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

def lambda_handler(event, context):
    """
    Lambda handler for PUT /cart/{product_id} endpoint.
    Updates quantity for a product in the cart (idempotent).
    """
    try:
        # Extract product_id from path parameters
        product_id = event['pathParameters']['product_id']
        
        # Parse request body
        body = json.loads(event['body'])
        quantity = int(body.get('quantity', 0))
        
        if quantity < 0:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
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
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
                },
                'body': json.dumps({'message': 'Product not found'})
            }
        
        # Determine user identifier
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
                old_quantity = item.get('quantity', 0)
                if isinstance(old_quantity, Decimal):
                    old_quantity = int(old_quantity)
                break
        
        # Update cart item
        update_cart_item_quantity(pk, product_id, quantity, product, ttl)
        
        # Update product aggregate counters (delta)
        quantity_diff = quantity - old_quantity
        if quantity_diff != 0:
            update_product_total_quantity(product_id, quantity_diff)
        
        response_body = {
            'productId': product_id,
            'quantity': quantity,
            'message': 'cart updated'
        }
        
        # Set headers including cart ID for anonymous users
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
        
    except KeyError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': 'Missing product_id in path or quantity in body'})
        }
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': 'Invalid JSON in request body'})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Credentials': True
            },
            'body': json.dumps({'message': f'Failed to update cart: {str(e)}'})
        }
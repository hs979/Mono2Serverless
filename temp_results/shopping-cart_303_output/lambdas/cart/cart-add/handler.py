import json
import os
import boto3
import uuid
from decimal import Decimal
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

def add_cart_item(pk, product_id, quantity, product_detail, expiration_time):
    """
    Add or update a cart item (increment quantity).
    """
    table = get_table()
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
    Lambda handler for POST /cart endpoint.
    Adds a product to the cart.
    """
    try:
        # Parse request body
        body = json.loads(event['body'])
        product_id = body.get('productId')
        quantity = body.get('quantity', 1)
        
        if not product_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Credentials': True
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
        
        # Add or update cart item
        add_cart_item(pk, product_id, quantity, product, ttl)
        # Update product aggregate counters
        update_product_total_quantity(product_id, quantity)
        
        response_body = {
            'productId': product_id,
            'message': 'product added to cart'
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
            'body': json.dumps({'message': f'Failed to add to cart: {str(e)}'})
        }
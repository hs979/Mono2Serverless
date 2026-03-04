import os
import json
import boto3
import uuid
from datetime import datetime, timedelta
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

def migrate_cart_items(anonymous_pk, user_pk):
    """
    Migrate an anonymous cart to the user account.
    
    Args:
        anonymous_pk: Anonymous cart partition key (cart#xxx)
        user_pk: User partition key (user#xxx)
    
    Returns:
        List of migrated items
    """
    table_name = os.environ['DYNAMODB_TABLE_NAME']
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    
    try:
        # Fetch all items in the anonymous cart
        response = table.query(
            KeyConditionExpression=Key('pk').eq(anonymous_pk) & Key('sk').begins_with('product#')
        )
        
        anonymous_items = response['Items']
        migrated_items = []
        
        # Migrate to the user cart
        for item in anonymous_items:
            sk = item['sk']
            quantity = item.get('quantity', 0)
            if isinstance(quantity, Decimal):
                quantity = int(quantity)
            product_detail = item.get('product_detail')
            
            if quantity <= 0:
                continue
            
            # Set new expiration time (authenticated users keep items for 30 days)
            expiration_time = datetime.now() + timedelta(days=30)
            ttl = int(expiration_time.timestamp())
            
            # Check if the user cart already has this product
            try:
                user_response = table.get_item(Key={'pk': user_pk, 'sk': sk})
                
                if 'Item' in user_response:
                    # Exists: increment quantity (atomic ADD)
                    table.update_item(
                        Key={'pk': user_pk, 'sk': sk},
                        UpdateExpression='ADD quantity :qty SET product_detail = :detail, expirationTime = :ttl, updated_at = :now',
                        ExpressionAttributeValues={
                            ':qty': quantity,
                            ':detail': product_detail,
                            ':ttl': ttl,
                            ':now': datetime.now().isoformat()
                        }
                    )
                else:
                    # Not exists: insert
                    table.put_item(
                        Item={
                            'pk': user_pk,
                            'sk': sk,
                            'quantity': quantity,
                            'product_detail': product_detail,
                            'expirationTime': ttl,
                            'updated_at': datetime.now().isoformat()
                        }
                    )
            except Exception as e:
                print(f"Failed to migrate item {sk}: {e}")
                continue
            
            migrated_items.append({
                'sk': sk,
                'quantity': quantity,
                'product_detail': product_detail
            })
        
        # Delete items from the anonymous cart
        with table.batch_writer() as batch:
            for item in anonymous_items:
                batch.delete_item(
                    Key={
                        'pk': item['pk'],
                        'sk': item['sk']
                    }
                )
        
        return migrated_items
        
    except Exception as e:
        print(f"Failed to migrate cart: {e}")
        raise

def lambda_handler(event, context):
    """
    Lambda handler for POST /cart/migrate endpoint.
    Migrates an anonymous cart to the authenticated user account.
    """
    try:
        # User must be authenticated via Cognito
        user_id = None
        if 'requestContext' in event and 'authorizer' in event['requestContext']:
            claims = event['requestContext']['authorizer'].get('claims', {})
            user_id = claims.get('sub')  # Cognito user UUID
        
        if not user_id:
            return {
                'statusCode': 401,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Authentication required'})
            }
        
        # Get cart ID from headers
        cart_id = None
        headers = event.get('headers', {})
        if 'x-cart-id' in headers:
            cart_id = headers['x-cart-id']
        
        if not cart_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({'message': 'Cart ID required'})
            }
        
        anonymous_pk = f"cart#{cart_id}"
        user_pk = f"user#{user_id}"
        
        # Migrate cart items
        migrated_items = migrate_cart_items(anonymous_pk, user_pk)
        
        # Fetch migrated cart
        product_list = get_cart_items(user_pk)
        
        # Normalize response data
        for product in product_list:
            if 'sk' in product:
                product['sk'] = product['sk'].replace('product#', '')
        
        response_body = {
            'products': product_list
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'X-Cart-ID': cart_id  # Return same cart ID for consistency
            },
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        print(f"Error in cart-migrate lambda: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Internal server error'})
        }
